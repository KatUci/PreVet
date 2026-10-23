"""Inicio de sesión con usuario o con RUT.

El personal entra con su nombre de usuario. Los clientes entran con su RUT,
que pueden escribir con o sin puntos y guion: 15.234.871-1, 15234871-1 o
152348711 llevan a la misma cuenta.
"""
from django.contrib.auth.backends import ModelBackend

from mascotas.rut import limpiar_rut, validar_rut


class UsuarioORutBackend(ModelBackend):

    def authenticate(self, request, username=None, password=None, **kwargs):
        usuario = super().authenticate(request, username=username, password=password, **kwargs)
        if usuario is None and username and any(c.isdigit() for c in username):
            try:
                validar_rut(username)
            except Exception:
                return None
            usuario = super().authenticate(request, username=limpiar_rut(username), password=password, **kwargs)
        return usuario
