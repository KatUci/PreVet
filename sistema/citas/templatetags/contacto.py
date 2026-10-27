"""{{ telefono|enlace_tel }}: el enlace tel: con el número completo (+56...)."""

from django import template

from citas.contacto import enlace_llamada

register = template.Library()


@register.filter
def enlace_tel(telefono):
    return enlace_llamada(telefono) or ''
