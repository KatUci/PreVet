"""Datos del usuario que necesitan todas las páginas (el menú lateral)."""

from .permisos import es_administrador


def usuario_actual(request):
    user = request.user
    if not user.is_authenticated:
        return {}

    perfil = getattr(user, 'perfil', None)
    if perfil is not None:
        rol = perfil.get_rol_display()
    elif user.is_superuser:
        rol = 'Superusuario'
    else:
        rol = 'Usuario'

    return {
        'es_admin': es_administrador(user),
        'rol_usuario': rol,
    }
