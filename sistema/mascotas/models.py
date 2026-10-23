from datetime import date

from django.contrib.auth.models import User
from django.db import models

from .rut import formatear_rut, limpiar_rut, validar_rut


class Especie(models.Model):
    """Tipo de mascota: canino, felino, ave, roedor, etc."""

    # Ícono que se muestra en las fichas según el tipo.
    EMOJIS = {
        'canino': '🐶', 'felino': '🐱', 'ave': '🦜', 'roedor': '🐹',
        'conejo': '🐰', 'reptil': '🦎',
    }

    nombre = models.CharField(max_length=50, unique=True)

    @property
    def emoji(self):
        return self.EMOJIS.get(self.nombre.lower(), '🐾')

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "tipo de mascota"
        verbose_name_plural = "tipos de mascota"
        ordering = ['nombre']


class Raza(models.Model):
    """Cada raza pertenece a un tipo de mascota."""

    especie = models.ForeignKey(
        Especie,
        on_delete=models.CASCADE,
        related_name='razas',
        verbose_name='tipo de mascota',
    )
    nombre = models.CharField(max_length=80)

    def __str__(self):
        return f"{self.nombre} ({self.especie.nombre})"

    class Meta:
        verbose_name_plural = "Razas"
        ordering = ['especie__nombre', 'nombre']
        unique_together = ('especie', 'nombre')


REGIONES = [(r, r) for r in (
    'Arica y Parinacota', 'Tarapacá', 'Antofagasta', 'Atacama', 'Coquimbo', 'Valparaíso', 'Metropolitana',
    "O'Higgins", 'Maule', 'Ñuble', 'Biobío', 'La Araucanía', 'Los Ríos', 'Los Lagos', 'Aysén', 'Magallanes')]

CANALES = [('whatsapp', 'WhatsApp'), ('llamada', 'Llamada'), ('correo', 'Correo')]


class Etiqueta(models.Model):
    """Alerta corta que se pega a un cliente o a una mascota (PV-CLI-04).

    Avisa al equipo de algo que conviene saber antes de atender: que la
    mascota muerde, que el cliente tiene una deuda, que hay que confirmar por
    teléfono, etc. Administración mantiene el catálogo.
    """

    class Para(models.TextChoices):
        CLIENTE = 'cliente', 'Clientes'
        MASCOTA = 'mascota', 'Mascotas'

    class Tono(models.TextChoices):
        MAL = 'mal', 'Rojo (cuidado)'
        WARN = 'warn', 'Ámbar (atención)'
        NEUTRO = 'neutro', 'Gris (informativa)'

    nombre = models.CharField(max_length=40, unique=True)
    para = models.CharField('se usa en', max_length=10, choices=Para.choices)
    tono = models.CharField('color', max_length=10, choices=Tono.choices, default=Tono.WARN)
    activo = models.BooleanField('disponible', default=True,
                                 help_text='Si la desmarcas, ya no se puede asignar, pero se conserva donde ya está.')

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = 'etiqueta de alerta'
        verbose_name_plural = 'etiquetas de alerta'
        ordering = ['para', 'nombre']


class Cliente(models.Model):
    """Persona que trae mascotas a la clínica.

    No es un usuario del sistema: no inicia sesión. Se identifica por su RUT.
    """

    rut = models.CharField(
        'RUT', max_length=12, unique=True, validators=[validar_rut],
        help_text='Con dígito verificador. Ej: 12.345.678-5',
    )
    nombres = models.CharField(max_length=80)
    apellidos = models.CharField(max_length=80)
    telefono = models.CharField('teléfono', max_length=20, blank=True)
    email = models.EmailField('correo', blank=True)
    direccion = models.CharField('dirección', max_length=200, blank=True)
    comuna = models.CharField(max_length=60, blank=True, db_default='')
    region = models.CharField('región', max_length=60, blank=True, db_default='', choices=REGIONES)

    contacto_emergencia = models.CharField('contacto de emergencia', max_length=120, blank=True, db_default='',
                                           help_text='Nombre de otra persona a quien llamar.')
    telefono_emergencia = models.CharField('teléfono de emergencia', max_length=20, blank=True, db_default='')
    canal_preferido = models.CharField('canal preferido', max_length=10, choices=CANALES,
                                       default='whatsapp', db_default='whatsapp',
                                       help_text='Por dónde prefiere que le confirmen las citas.')

    # Ley 19.628: el cliente autoriza el tratamiento de sus datos personales.
    consentimiento_datos = models.BooleanField('acepta el tratamiento de sus datos', default=False,
                                               db_default=False)
    fecha_consentimiento = models.DateTimeField('fecha del consentimiento', null=True, blank=True)

    # Cuenta del portal del tutor (Mi PreVet), si el cliente creó una.
    usuario = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='cliente', verbose_name='cuenta en Mi PreVet')

    etiquetas = models.ManyToManyField(Etiqueta, blank=True, related_name='clientes',
                                       limit_choices_to={'para': 'cliente'},
                                       verbose_name='etiquetas de alerta')

    activo = models.BooleanField(default=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Se guarda siempre igual, escriba como se escriba: 12345678-5.
        self.rut = limpiar_rut(self.rut)
        # La fecha del consentimiento se registra sola la primera vez que se marca.
        if self.consentimiento_datos and not self.fecha_consentimiento:
            from django.utils import timezone
            self.fecha_consentimiento = timezone.now()
        elif not self.consentimiento_datos:
            self.fecha_consentimiento = None
        super().save(*args, **kwargs)

    @property
    def rut_formateado(self):
        return formatear_rut(self.rut)

    @property
    def nombre_completo(self):
        return f"{self.nombres} {self.apellidos}"

    def __str__(self):
        return f"{self.nombre_completo} ({self.rut_formateado})"

    class Meta:
        verbose_name = "cliente"
        verbose_name_plural = "clientes"
        ordering = ['apellidos', 'nombres']


class Mascota(models.Model):
    """Un paciente de la clínica."""

    SEXOS = (
        ('macho', 'Macho'),
        ('hembra', 'Hembra'),
    )

    nombre = models.CharField(max_length=80)
    especie = models.ForeignKey(Especie, on_delete=models.PROTECT,
                                verbose_name='tipo de mascota')
    raza = models.ForeignKey(Raza, on_delete=models.PROTECT, null=True, blank=True)
    sexo = models.CharField(max_length=10, choices=SEXOS)
    fecha_nacimiento = models.DateField(null=True, blank=True)

    # Identificación y datos clínicos básicos.
    tiene_microchip = models.BooleanField('¿tiene microchip?', null=True, blank=True)
    microchip = models.CharField('número de microchip', max_length=15, blank=True, db_default='',
                                 help_text='Opcional: 15 dígitos.')
    color = models.CharField('color o señas', max_length=80, blank=True, db_default='')
    peso_kg = models.DecimalField('peso (kg)', max_digits=5, decimal_places=2, null=True, blank=True)
    esterilizada = models.BooleanField('esterilizada', null=True, blank=True,
                                       help_text='Déjalo sin marcar si no se sabe.')
    alergias = models.TextField(blank=True, db_default='')
    condiciones = models.TextField('enfermedades crónicas y medicamentos', blank=True, db_default='')
    observaciones = models.TextField('observaciones de manejo', blank=True, db_default='',
                                     help_text='Carácter, si muerde, si necesita bozal, etc.')

    # Un cliente puede tener muchas mascotas, y una mascota puede tener
    # varios clientes (una familia, una pareja, quien la cuida). La tabla
    # intermedia Tenencia guarda qué relación tiene cada uno con ella.
    tutores = models.ManyToManyField(
        Cliente,
        through='Tenencia',
        related_name='mascotas',
    )

    etiquetas = models.ManyToManyField(Etiqueta, blank=True, related_name='mascotas',
                                       limit_choices_to={'para': 'mascota'},
                                       verbose_name='etiquetas de alerta')

    activo = models.BooleanField(default=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    # Cambia cada vez que se sube una foto (0 = sin foto). Sirve para saber si
    # hay foto sin leer la imagen y para que el navegador no muestre una vieja.
    foto_version = models.PositiveIntegerField(default=0, db_default=0, editable=False)

    @property
    def responsable(self):
        """El cliente principal de la mascota, o None si no tiene."""
        for tenencia in self.tenencias.all():
            if tenencia.es_principal:
                return tenencia.cliente
        return None

    @property
    def edad(self):
        """Edad en años y meses, calculada desde la fecha de nacimiento."""
        if not self.fecha_nacimiento:
            return None

        hoy = date.today()
        meses = ((hoy.year - self.fecha_nacimiento.year) * 12
                 + hoy.month - self.fecha_nacimiento.month)
        if hoy.day < self.fecha_nacimiento.day:
            meses -= 1

        anos, resto = divmod(max(meses, 0), 12)

        if anos and resto:
            return f"{anos} año{'s' if anos > 1 else ''} y {resto} mes{'es' if resto > 1 else ''}"
        if anos:
            return f"{anos} año{'s' if anos > 1 else ''}"
        return f"{resto} mes{'es' if resto != 1 else ''}"

    def __str__(self):
        return f"{self.nombre} · {self.especie.nombre}"

    class Meta:
        verbose_name_plural = "Mascotas"
        ordering = ['nombre']
        constraints = [
            models.UniqueConstraint(fields=['microchip'], condition=~models.Q(microchip=''),
                                    name='microchip_unico'),
        ]


class Tenencia(models.Model):
    """La relación entre un cliente y una mascota."""

    class Relacion(models.TextChoices):
        DUENO = 'dueno', 'Dueño'
        FAMILIAR = 'familiar', 'Familiar'
        CUIDADOR = 'cuidador', 'Cuidador'

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='tenencias')
    mascota = models.ForeignKey(Mascota, on_delete=models.CASCADE, related_name='tenencias')
    relacion = models.CharField('relación', max_length=20,
                                choices=Relacion.choices, default=Relacion.DUENO)
    es_principal = models.BooleanField(
        'responsable principal', default=False,
        help_text='A quien se contacta primero. Solo uno por mascota.',
    )
    desde = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.cliente.nombre_completo} → {self.mascota.nombre} ({self.get_relacion_display()})"

    class Meta:
        verbose_name = "relación cliente-mascota"
        verbose_name_plural = "relaciones cliente-mascota"
        constraints = [
            models.UniqueConstraint(fields=['cliente', 'mascota'],
                                    name='un_vinculo_por_cliente_y_mascota'),
            # La base de datos misma impide dos responsables principales.
            models.UniqueConstraint(fields=['mascota'], condition=models.Q(es_principal=True),
                                    name='un_responsable_principal_por_mascota'),
        ]


class FotoMascota(models.Model):
    """La foto de una mascota, guardada en la base de datos compartida.

    Va en una tabla aparte para que las consultas de mascotas y citas no
    carguen la imagen cuando no la necesitan. Se guarda ya achicada (ver
    fotos.py), por eso cabe sin problemas en la base.
    """

    mascota = models.OneToOneField(Mascota, on_delete=models.CASCADE, primary_key=True,
                                   related_name='foto')
    imagen = models.BinaryField()
    tipo = models.CharField(max_length=30, default='image/jpeg')
    actualizada = models.DateTimeField(auto_now=True)
    subida_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+')

    def __str__(self):
        return f"Foto de {self.mascota.nombre}"

    class Meta:
        verbose_name = "foto de mascota"
        verbose_name_plural = "fotos de mascotas"
