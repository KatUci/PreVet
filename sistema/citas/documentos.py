"""Documentos adjuntos a la atención (PV-FIC-03): PDF o Word de hasta 5 MB.

Solo los veterinarios y administración (permiso citas.add_atencion) los suben
o quitan, y solo quien puede ver el historial clínico los descarga.
"""
import os

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_POST

from .models import Atencion, DocumentoAtencion

TAMANO_MAXIMO = 5 * 1024 * 1024     # 5 MB

# Tipo de cada extensión permitida y cómo empiezan esos archivos por dentro.
# Se revisa el contenido y no solo el nombre: un archivo renombrado a .pdf
# no pasa.
TIPOS = {
    '.pdf': 'application/pdf',
    '.doc': 'application/msword',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}
FIRMAS = {
    '.pdf': b'%PDF',
    '.doc': b'\xd0\xcf\x11\xe0',
    '.docx': b'PK\x03\x04',
}


def validar_documento(archivo):
    """Revisa que sea un PDF o Word de verdad y que no pase de 5 MB."""
    extension = os.path.splitext(archivo.name)[1].lower()
    if extension not in TIPOS:
        raise forms.ValidationError('Solo se pueden adjuntar archivos PDF o Word (.pdf, .doc, .docx).')
    if archivo.size > TAMANO_MAXIMO:
        raise forms.ValidationError('El archivo pesa más de 5 MB. Prueba con uno más liviano.')
    inicio = archivo.read(4)
    archivo.seek(0)
    if not inicio.startswith(FIRMAS[extension]):
        raise forms.ValidationError('El archivo no parece ser un PDF o Word válido.')
    return archivo


def guardar(atencion, archivo, usuario):
    return DocumentoAtencion.objects.create(
        atencion=atencion, nombre=os.path.basename(archivo.name)[:150],
        archivo=archivo.read(), tamano=archivo.size, subido_por=usuario)


class AdjuntarForm(forms.Form):
    documento = forms.FileField(validators=[validar_documento])


@require_POST
@login_required
@permission_required('citas.add_atencion', raise_exception=True)
def adjuntar(request, pk):
    """Adjunta un documento a una atención ya registrada, desde la ficha de la mascota."""
    atencion = get_object_or_404(Atencion.objects.select_related('cita'), pk=pk)
    form = AdjuntarForm(request.POST, request.FILES)
    if form.is_valid():
        documento = guardar(atencion, form.cleaned_data['documento'], request.user)
        messages.success(request, f'Se adjuntó «{documento.nombre}» a la atención.')
    else:
        messages.error(request, ' '.join(form.errors.get('documento', ['Elige un archivo.'])))
    return redirect('mascota_ficha', atencion.cita.mascota_id)


@login_required
@permission_required('citas.view_atencion', raise_exception=True)
def descargar(request, pk):
    documento = get_object_or_404(DocumentoAtencion, pk=pk)
    extension = os.path.splitext(documento.nombre)[1].lower()
    respuesta = HttpResponse(bytes(documento.archivo),
                             content_type=TIPOS.get(extension, 'application/octet-stream'))
    respuesta['Content-Disposition'] = content_disposition_header(True, documento.nombre)
    return respuesta


@require_POST
@login_required
@permission_required('citas.add_atencion', raise_exception=True)
def quitar(request, pk):
    documento = get_object_or_404(DocumentoAtencion.objects.select_related('atencion__cita'), pk=pk)
    mascota = documento.atencion.cita.mascota_id
    documento.delete()
    messages.success(request, f'Se quitó «{documento.nombre}».')
    return redirect('mascota_ficha', mascota)
