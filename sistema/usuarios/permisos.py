"""Quién puede entrar al apartado de Administración de PreVet."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import Perfil


def es_administrador(user):
    """Superusuarios, y personal con rol o marca de administrador."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    # Si el usuario no tiene perfil, getattr devuelve None en vez de fallar.
    perfil = getattr(user, 'perfil', None)
    if perfil is None:
        return False
    return perfil.es_administrador or perfil.rol == Perfil.Rol.ADMINISTRADOR


def solo_administradores(vista):
    """Decorador: pide iniciar sesión, y si no es administrador responde 403."""

    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not es_administrador(request.user):
            raise PermissionDenied
        return vista(request, *args, **kwargs)

    return login_required(envoltura)
