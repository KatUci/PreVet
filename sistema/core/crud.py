"""Piezas comunes para las pantallas de mantención (listar, crear, editar, eliminar).

Las usan los catálogos de configuración: tipos de atención, horarios, tipos
de mascota y razas. Cada pantalla define sus columnas y su formulario; el
resto (plantillas, mensajes, protección al eliminar) es igual para todas.
"""
from django.contrib import messages
from django.db.models import ProtectedError
from django.shortcuts import redirect, render


def listado(request, *, seccion, titulo, subtitulo, columnas, filas, url_nuevo=None,
            texto_nuevo='Agregar', vacio='Todavía no hay registros.', migas=None):
    """Tabla genérica. `filas` es una lista de dicts con 'celdas', 'editar' y 'eliminar'."""
    return render(request, 'core/catalogo.html', {
        'seccion': seccion,
        'titulo': titulo,
        'subtitulo': subtitulo,
        'columnas': columnas,
        'filas': filas,
        'url_nuevo': url_nuevo,
        'texto_nuevo': texto_nuevo,
        'vacio': vacio,
        'migas': migas or [],
    })


def formulario(request, *, form, seccion, titulo, volver, mensaje, migas=None, ayuda=None):
    """Formulario genérico de crear o editar. Guarda y vuelve al listado."""
    if request.method == 'POST' and form.is_valid():
        objeto = form.save()
        messages.success(request, mensaje.format(objeto=objeto))
        return redirect(volver)
    return render(request, 'core/catalogo_form.html', {
        'seccion': seccion,
        'titulo': titulo,
        'form': form,
        'volver': volver,
        'migas': migas or [],
        'ayuda': ayuda,
    })


def eliminar(request, objeto, *, volver, en_uso='No se puede eliminar porque está en uso.'):
    """Elimina si nadie lo usa; si está en uso, avisa y no borra nada."""
    nombre = str(objeto)
    try:
        objeto.delete()
    except ProtectedError:
        messages.error(request, f'«{nombre}»: {en_uso}')
    else:
        messages.success(request, f'Se eliminó «{nombre}».')
    return redirect(volver)
