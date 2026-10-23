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

    # Los clientes con cuenta en Mi PreVet ven solo su portal.
    es_tutor = hasattr(user, 'cliente') and not (perfil and perfil.es_personal)
    if es_tutor:
        rol = 'Cliente'
    return {
        'es_admin': es_administrador(user),
        'rol_usuario': rol,
        'es_tutor': es_tutor,
    }
