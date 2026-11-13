from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import datetime

from mascotas.models import Cliente, Mascota


DIAS_SEMANA = (
    (0, 'Lunes'),
    (1, 'Martes'),
    (2, 'Miércoles'),
    (3, 'Jueves'),
    (4, 'Viernes'),
    (5, 'Sábado'),
    (6, 'Domingo'),
)


class TipoAtencion(models.Model):
    """Qué se viene a hacer, cuánto dura y cuánto cuesta."""

    nombre = models.CharField(max_length=80, unique=True)
    duracion_minutos = models.IntegerField(default=30)
    precio = models.IntegerField(help_text="Valor en pesos")
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre} (${self.precio:,})".replace(",", ".")

    class Meta:
        verbose_name = "Tipo de atención"
        verbose_name_plural = "Tipos de atención"
        ordering = ['nombre']


class HorarioAtencion(models.Model):
    """Tramo en que un veterinario atiende un día de la semana."""

    veterinario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='horarios',
    )
    dia_semana = models.IntegerField(choices=DIAS_SEMANA)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    activo = models.BooleanField(default=True)

    def __str__(self):
        return (f"{self.veterinario.get_full_name()} · "
                f"{self.get_dia_semana_display()} "
                f"{self.hora_inicio:%H:%M}-{self.hora_fin:%H:%M}")

    class Meta:
        verbose_name = "Horario de atención"
        verbose_name_plural = "Horarios de atención"
        ordering = ['veterinario', 'dia_semana', 'hora_inicio']
        unique_together = ('veterinario', 'dia_semana', 'hora_inicio')


class Cita(models.Model):
    """Una hora agendada."""

    ESTADOS = (
        ('pendiente', 'Pendiente'),
        ('completada', 'Completada'),
        ('cancelada', 'Cancelada'),
        ('no_asistio', 'No asistió'),
    )

    veterinario = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='citas_atendidas',
        # Solo puede atender quien tiene el rol de veterinario.
        limit_choices_to={'perfil__rol': 'veterinario'},
    )
    mascota = models.ForeignKey(
        Mascota,
        on_delete=models.CASCADE,
        related_name='citas',
    )

    # Quién pidió la hora. Una mascota puede tener varios clientes, y el
    # historial de inasistencia se mide por persona, no por mascota.
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name='citas',
        verbose_name='cliente que agenda',
    )
    tipo_atencion = models.ForeignKey(
        TipoAtencion,
        on_delete=models.PROTECT,
        related_name='citas',
    )

    fecha = models.DateField()
    hora = models.TimeField()
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    notas = models.TextField(blank=True)

    # Cuándo se hizo la reserva. De acá sale la anticipación,
    # que es una de las variables que predicen la inasistencia.
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    cancelada_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='citas_canceladas',
    )
    fecha_cancelacion = models.DateTimeField(null=True, blank=True)
    motivo_cancelacion = models.CharField('motivo de la cancelación', max_length=200, blank=True)
    fecha_marcada_no_asistio = models.DateTimeField(null=True, blank=True)

    # Cuándo llegó de verdad el paciente. Con esto se miden también los atrasos.
    hora_llegada = models.DateTimeField('hora de llegada', null=True, blank=True)

    # Etapas del flujo de atención (PV-REC-05): cuándo pasó al box y cuándo
    # se fue de la clínica. Entre "atendida" y "salió" está lista para salir
    # (esperando pagar o que la retiren).
    inicio_atencion = models.DateTimeField('inicio de la atención', null=True, blank=True)
    hora_salida = models.DateTimeField('hora de salida', null=True, blank=True)

    # Atención sin hora (PV-CIT-07): una urgencia o un sobrecupo que llega
    # sin reserva y entra directo a la sala de espera.
    sin_hora = models.BooleanField('sin hora (urgencia o sobrecupo)', default=False, db_default=False)

    # Resultado del contacto previo con el tutor (PV-CIT-05). Vacío mientras
    # nadie lo haya contactado. Se guarda quién y cuándo, para medir después
    # si confirmar reduce las inasistencias.
    CONFIRMACIONES = (
        ('confirmada', 'Confirmó'),
        ('no_contesta', 'No contesta'),
        ('pidio_cambio', 'Pidió cambio'),
    )
    confirmacion = models.CharField('confirmación', max_length=20, choices=CONFIRMACIONES,
                                    blank=True, default='', db_default='')
    confirmacion_fecha = models.DateTimeField('fecha de la confirmación', null=True, blank=True)
    confirmacion_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='citas_confirmadas',
                                         verbose_name='registrada por')

    @property
    def dias_anticipacion(self):
        """Cuántos días antes se reservó esta hora."""
        return (self.fecha - self.fecha_creacion.date()).days

    def clean(self):
        """La cita debe quedar a nombre de alguien vinculado a la mascota."""
        super().clean()
        if self.mascota_id and self.cliente_id:
            if not self.mascota.tutores.filter(pk=self.cliente_id).exists():
                raise ValidationError({
                    'cliente': 'Este cliente no está asociado a la mascota elegida.'})

    @property
    def hora_termino(self):
        """Hora en que termina, según la duración del tipo de atención."""
        inicio = datetime.datetime.combine(self.fecha, self.hora)
        return (inicio + datetime.timedelta(minutes=self.tipo_atencion.duracion_minutos)).time()

    @property
    def valor_perdido(self):
        """Lo que la clínica dejó de percibir si el tutor no llegó."""
        if self.estado == 'no_asistio':
            return self.tipo_atencion.precio
        return 0

    def __str__(self):
        return f"{self.mascota.nombre} · {self.fecha} {self.hora:%H:%M}"

    class Meta:
        verbose_name = "Cita"
        verbose_name_plural = "Citas"
        ordering = ['-fecha', '-hora']
        constraints = [
            # Un profesional no puede tener dos citas a la misma hora... salvo
            # que una esté cancelada: al cancelar, el bloque queda libre.
            models.UniqueConstraint(
                fields=['veterinario', 'fecha', 'hora'],
                condition=~models.Q(estado='cancelada'),
                name='una_cita_activa_por_bloque',
            ),
        ]
        # Además de ver, agregar, modificar y eliminar citas (que Django crea
        # solo), estas dos pantallas de análisis tienen su propio permiso.
        permissions = [
            ('ver_riesgo', 'Ver las horas en riesgo'),
            ('ver_indicadores', 'Ver los indicadores'),
        ]


class Atencion(models.Model):
    """Lo que el veterinario registra al atender: la ficha clínica de la cita.

    Se pide al cerrar la cita, de modo que cada atención completada deja
    constancia de por qué vino el paciente, qué se encontró y qué se indicó.
    """

    cita = models.OneToOneField(Cita, on_delete=models.CASCADE, related_name='atencion')
    motivo = models.CharField('motivo de consulta', max_length=200)
    diagnostico = models.TextField('diagnóstico')
    tratamiento = models.TextField('tratamiento e indicaciones', blank=True)
    peso_kg = models.DecimalField('peso (kg)', max_digits=5, decimal_places=2, null=True, blank=True,
                                  help_text='Si lo registras, se actualiza también en la ficha de la mascota.')

    registrada_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='atenciones_registradas')
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Atención de {self.cita.mascota.nombre} · {self.cita.fecha:%d/%m/%Y}"

    class Meta:
        verbose_name = "atención"
        verbose_name_plural = "atenciones"
        ordering = ['-cita__fecha', '-cita__hora']


class DocumentoAtencion(models.Model):
    """Un PDF o Word adjunto a la atención: recetas, exámenes, indicaciones (PV-FIC-03).

    Se guarda dentro de la base de datos, igual que las fotos, para que todo
    el equipo lo vea aunque cada una corra el sistema en su computador. No
    queda en una carpeta pública: solo se descarga desde PreVet y con permiso.
    """

    atencion = models.ForeignKey(Atencion, on_delete=models.CASCADE, related_name='documentos')
    nombre = models.CharField('nombre del archivo', max_length=150)
    archivo = models.BinaryField()
    tamano = models.IntegerField('tamaño (bytes)')
    subido_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    fecha_subida = models.DateTimeField(auto_now_add=True)

    @property
    def tamano_txt(self):
        """1234567 -> '1,2 MB'; 45000 -> '44 KB'."""
        if self.tamano >= 1024 * 1024:
            return f'{self.tamano / 1024 / 1024:.1f} MB'.replace('.', ',')
        return f'{max(self.tamano // 1024, 1)} KB'

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "documento de la atención"
        verbose_name_plural = "documentos de las atenciones"
        ordering = ['fecha_subida']


class Pago(models.Model):
    """Lo que el cliente pagó por una atención (PV-PAG-01).

    Recepción lo registra al cobrar, antes de que la mascota se vaya. Es un
    comprobante interno de la clínica, no una boleta electrónica del SII.
    """

    MEDIOS = (
        ('efectivo', 'Efectivo'),
        ('debito', 'Débito'),
        ('credito', 'Crédito'),
        ('transferencia', 'Transferencia'),
    )

    cita = models.OneToOneField(Cita, on_delete=models.PROTECT, related_name='pago')
    monto = models.IntegerField('monto ($)')
    medio = models.CharField('medio de pago', max_length=15, choices=MEDIOS)
    detalle = models.CharField('detalle', max_length=200, blank=True,
                               help_text='Opcional: lo que se cobró además de la atención (vacuna, remedios…).')
    cobrado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    fecha = models.DateTimeField('fecha del pago', auto_now_add=True)

    @property
    def numero(self):
        """Número del comprobante: 000123."""
        return f'{self.pk:06d}'

    @property
    def monto_txt(self):
        return f'${self.monto:,}'.replace(',', '.')

    def __str__(self):
        return f"Comprobante N° {self.numero} · {self.monto_txt}"

    class Meta:
        verbose_name = "pago"
        verbose_name_plural = "pagos"
        ordering = ['-fecha']


class PlantillaMensaje(models.Model):
    """Texto editable de un mensaje de WhatsApp (PV-REC-06).

    Mientras administración no edite una plantilla, se usa el texto original
    que está en contacto.py. El texto lleva variables entre llaves, como
    {tutor} o {mascota}, que se reemplazan por los datos de cada cita.
    """

    CLAVES = (
        ('riesgo_alto', 'Recordatorio para riesgo alto'),
        ('riesgo_medio', 'Recordatorio para riesgo medio'),
        ('riesgo_bajo', 'Recordatorio para riesgo bajo'),
        ('recordatorio', 'Recordatorio general'),
        ('vacuna', 'Aviso de vacuna por vencer'),
    )

    clave = models.CharField(max_length=20, choices=CLAVES, unique=True)
    texto = models.TextField()
    fecha_modificacion = models.DateTimeField('última modificación', auto_now=True)

    def __str__(self):
        return self.get_clave_display()

    class Meta:
        verbose_name = "plantilla de mensaje"
        verbose_name_plural = "plantillas de mensajes"
        ordering = ['clave']


class PesosModelo(models.Model):
    """Cuánto pesa cada factor en el puntaje de riesgo (PV-RIE-04).

    Hay una sola fila. Mientras administración no ajuste los pesos, el modelo
    usa los originales de riesgo.py (40, 20, 20 y 20). Deben sumar 100.
    """

    peso_tutor = models.PositiveSmallIntegerField('historial de faltas del tutor')
    peso_anticipacion = models.PositiveSmallIntegerField('días de anticipación de la reserva')
    peso_dia = models.PositiveSmallIntegerField('día de la semana')
    peso_tipo = models.PositiveSmallIntegerField('tipo de atención')

    modificado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    fecha_modificacion = models.DateTimeField('última modificación', auto_now=True)

    def como_dict(self):
        return {'tutor': self.peso_tutor, 'anticipacion': self.peso_anticipacion,
                'dia': self.peso_dia, 'tipo': self.peso_tipo}

    def __str__(self):
        return 'Pesos del modelo de riesgo'

    class Meta:
        verbose_name = "pesos del modelo de riesgo"
        verbose_name_plural = "pesos del modelo de riesgo"


class CambioCita(models.Model):
    """Una línea del historial de una cita: quién la cambió, qué cambió y cuándo (PV-ADM-05).

    Se registra solo, cada vez que se guarda una cita (ver auditoria.py), así
    que cubre todas las pantallas: agendar, reagendar, cancelar, llegó,
    atendida, confirmación, importar y el panel /admin/.
    """

    cita = models.ForeignKey(Cita, on_delete=models.CASCADE, related_name='cambios')
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
                                help_text='Vacío si el cambio no lo hizo una persona (por ejemplo, los datos de prueba).')
    fecha = models.DateTimeField(auto_now_add=True)
    accion = models.CharField('acción', max_length=40)
    detalle = models.TextField(blank=True)

    def __str__(self):
        return f"{self.accion} · {self.cita}"

    class Meta:
        verbose_name = "cambio de una cita"
        verbose_name_plural = "historial de cambios de las citas"
        ordering = ['-fecha', '-pk']
