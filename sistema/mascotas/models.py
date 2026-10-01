from django.db import models
from django.contrib.auth.models import User


class Especie(models.Model):
    """Perro, gato, conejo, etc."""

    nombre = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name_plural = "Especies"
        ordering = ['nombre']


class Raza(models.Model):
    """Cada raza pertenece a una especie."""

    especie = models.ForeignKey(
        Especie,
        on_delete=models.CASCADE,
        related_name='razas',
    )
    nombre = models.CharField(max_length=80)

    def __str__(self):
        return f"{self.nombre} ({self.especie.nombre})"

    class Meta:
        verbose_name_plural = "Razas"
        ordering = ['especie__nombre', 'nombre']
        unique_together = ('especie', 'nombre')


class Mascota(models.Model):
    """Un paciente de la clínica."""

    SEXOS = (
        ('macho', 'Macho'),
        ('hembra', 'Hembra'),
    )

    nombre = models.CharField(max_length=80)
    especie = models.ForeignKey(Especie, on_delete=models.PROTECT)
    raza = models.ForeignKey(Raza, on_delete=models.PROTECT, null=True, blank=True)
    sexo = models.CharField(max_length=10, choices=SEXOS)
    fecha_nacimiento = models.DateField(null=True, blank=True)

    dueno = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='mascotas',
    )

    activo = models.BooleanField(default=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} · {self.especie.nombre}"

    class Meta:
        verbose_name_plural = "Mascotas"
        ordering = ['nombre']