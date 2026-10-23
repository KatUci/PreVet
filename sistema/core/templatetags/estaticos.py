"""{% static_v %}: como {% static %}, pero agrega la versión del archivo.

El navegador guarda los CSS y JS para no descargarlos cada vez. Si el archivo
cambia, igual seguiría usando el viejo. Con ?v=<fecha de modificación> la
dirección cambia sola cuando el archivo cambia, y el navegador baja el nuevo.
"""

import os

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def static_v(ruta):
    url = static(ruta)
    archivo = finders.find(ruta)
    if archivo:
        url += f'?v={int(os.path.getmtime(archivo))}'
    return url
