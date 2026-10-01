from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import datetime

from mascotas.models import Mascota


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
    )
    mascota = models.ForeignKey(
        Mascota,
        on_delete=models.CASCADE,
        related_name='citas',
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
    fecha_marcada_no_asistio = models.DateTimeField(null=True, blank=True)

    @property
    def dias_anticipacion(self):
        """Cuántos días antes se reservó esta hora."""
        return (self.fecha - self.fecha_creacion.date()).days

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
        unique_together = ('veterinario', 'fecha', 'hora')
        ordering = ['-fecha', '-hora']