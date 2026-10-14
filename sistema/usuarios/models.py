from django.contrib.auth.models import Group, User, UserManager
from django.db import models


class Perfil(models.Model):
    """Datos propios de cada persona que usa el sistema."""

    class Rol(models.TextChoices):
        VETERINARIO = 'veterinario', 'Veterinario'
        RECEPCIONISTA = 'recepcionista', 'Recepcionista'
        ADMINISTRADOR = 'admin', 'Administrador'
        DUENO = 'dueno', 'Dueño de mascota'

    # Quienes trabajan en la clínica. Los dueños son clientes, no personal.
    ROLES_PERSONAL = (Rol.VETERINARIO, Rol.RECEPCIONISTA, Rol.ADMINISTRADOR)

    # Grupo de permisos que recibe por defecto cada rol del personal.
    GRUPO_POR_ROL = {
        Rol.VETERINARIO: 'Veterinarios',
        Rol.RECEPCIONISTA: 'Recepción',
        Rol.ADMINISTRADOR: 'Administración',
    }

    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='perfil',
    )
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.DUENO)

    # Va aparte del rol a propósito: alguien puede ser veterinaria
    # y administradora al mismo tiempo.
    es_administrador = models.BooleanField(default=False)

    telefono = models.CharField(max_length=20, blank=True)
    direccion = models.CharField(max_length=200, blank=True)

    @property
    def es_personal(self):
        """True si trabaja en la clínica; False si es dueño de mascota."""
        return self.rol in self.ROLES_PERSONAL

    def __str__(self):
        nombre = self.usuario.get_full_name() or self.usuario.username
        return f"{nombre} · {self.get_rol_display()}"

    class Meta:
        verbose_name = "Perfil"
        verbose_name_plural = "Perfiles"


class PersonalManager(UserManager):
    """Devuelve solo a quienes tienen un rol del personal de la clínica."""

    def get_queryset(self):
        return (super().get_queryset()
                .filter(perfil__rol__in=Perfil.ROLES_PERSONAL)
                .select_related('perfil'))


class Personal(User):
    """Una persona que trabaja en la clínica.

    Es un modelo proxy: no crea una tabla nueva, usa la misma de los
    usuarios de Django. Sirve para tener un apartado propio en el panel,
    con solo el personal y no los dueños de mascotas.
    """

    objects = PersonalManager()

    class Meta:
        proxy = True
        verbose_name = "integrante del personal"
        verbose_name_plural = "personal de la clínica"
        ordering = ['first_name', 'last_name']


class GrupoPermisos(Group):
    """Un grupo de permisos de Django con nombre en español en el panel."""

    class Meta:
        proxy = True
        verbose_name = "grupo de permisos"
        verbose_name_plural = "grupos de permisos"
        ordering = ['name']
