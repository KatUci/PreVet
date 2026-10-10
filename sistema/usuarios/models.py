from django.db import models
from django.contrib.auth.models import User


class Perfil(models.Model):
    """Datos propios de cada persona que usa el sistema."""

    ROLES = (
        ('veterinario', 'Veterinario'),
        ('recepcionista', 'Recepcionista'),
        ('dueno', 'Dueño de mascota'),
        ('admin', 'Administrador'),
    )

    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='perfil',
    )
    rol = models.CharField(max_length=20, choices=ROLES, default='dueno')

    # Va aparte del rol a propósito: alguien puede ser veterinaria
    # y administradora al mismo tiempo.
    es_administrador = models.BooleanField(default=False)

    telefono = models.CharField(max_length=20, blank=True)
    direccion = models.CharField(max_length=200, blank=True)

    def __str__(self):
        nombre = self.usuario.get_full_name() or self.usuario.username
        return f"{nombre} · {self.get_rol_display()}"

    class Meta:
        verbose_name = "Perfil"
        verbose_name_plural = "Perfiles"


# Django muestra a los usuarios por su nombre de cuenta: dmunoz, paz.herrera.
# Acá le decimos que use el nombre completo, y que recurra al nombre de cuenta
# solo si la persona no lo tiene registrado.
def _mostrar_nombre_completo(self):
    return self.get_full_name() or self.username


User.add_to_class('__str__', _mostrar_nombre_completo)
