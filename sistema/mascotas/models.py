from datetime import date

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

    activo = models.BooleanField(default=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Se guarda siempre igual, escriba como se escriba: 12345678-5.
        self.rut = limpiar_rut(self.rut)
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

    # Un cliente puede tener muchas mascotas, y una mascota puede tener
    # varios clientes (una familia, una pareja, quien la cuida). La tabla
    # intermedia Tenencia guarda qué relación tiene cada uno con ella.
    tutores = models.ManyToManyField(
        Cliente,
        through='Tenencia',
        related_name='mascotas',
    )

    activo = models.BooleanField(default=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

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

