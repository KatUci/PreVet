"""Fotos de las mascotas: subir, ver y quitar.

Las fotos se guardan en la base de datos compartida (tabla FotoMascota), así
ambas integrantes y la clínica ven las mismas sin configurar otro servicio.
Antes de guardarlas se achican a un tamaño web y se convierten a JPEG: una
foto de 4 MB del celular queda en unos 100 KB.
"""
from io import BytesIO

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.db.models import F
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from PIL import Image, ImageOps

from .models import FotoMascota, Mascota

PESO_MAXIMO = 10 * 1024 * 1024     # 10 MB, lo que pesa una foto grande de celular
LADO_MAXIMO = 900                  # píxeles del lado más largo, de sobra para la web


class FotoForm(forms.Form):
    foto = forms.ImageField(
        label='Foto de la mascota',
        help_text='JPG, PNG o WEBP de hasta 10 MB. Se achica automáticamente.',
        # La vista previa reemplaza la foto actual de la pantalla (ver prevet.js).
        widget=forms.FileInput(attrs={'data-vista-previa': 'fotoActual'}))

    def clean_foto(self):
        foto = self.cleaned_data['foto']
        if foto.size > PESO_MAXIMO:
            raise forms.ValidationError('La foto pesa más de 10 MB. Elige una más liviana.')
        return foto


def procesar_foto(archivo):
    """Gira según la cámara, achica y convierte a JPEG. Devuelve los bytes."""
    imagen = ImageOps.exif_transpose(Image.open(archivo))
    if imagen.mode in ('RGBA', 'LA', 'P'):
        # Las partes transparentes de un PNG quedan en blanco.
        imagen = imagen.convert('RGBA')
        fondo = Image.new('RGB', imagen.size, (255, 255, 255))
        fondo.paste(imagen, mask=imagen.split()[-1])
        imagen = fondo
    else:
        imagen = imagen.convert('RGB')
    imagen.thumbnail((LADO_MAXIMO, LADO_MAXIMO), Image.LANCZOS)
    salida = BytesIO()
    imagen.save(salida, 'JPEG', quality=82, optimize=True, progressive=True)
    return salida.getvalue()


def guardar_foto(mascota, archivo, usuario):
    """Reemplaza la foto de la mascota y cambia su versión."""
    with transaction.atomic():
        FotoMascota.objects.update_or_create(
            mascota=mascota,
            defaults={'imagen': procesar_foto(archivo), 'tipo': 'image/jpeg', 'subida_por': usuario})
        Mascota.objects.filter(pk=mascota.pk).update(foto_version=F('foto_version') + 1)


def _volver(request, mascota):
    destino = request.POST.get('next') or request.GET.get('next')
    if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        return destino
    return '/mascotas/'


@login_required
@permission_required('mascotas.view_mascota', raise_exception=True)
def ver_foto(request, pk):
    """Entrega la imagen. La dirección lleva ?v=versión, así se puede guardar en caché."""
    foto = FotoMascota.objects.filter(mascota_id=pk).only('imagen', 'tipo').first()
    if foto is None:
        raise Http404('La mascota no tiene foto.')
    respuesta = HttpResponse(bytes(foto.imagen), content_type=foto.tipo)
    respuesta['Cache-Control'] = 'private, max-age=31536000'
    return respuesta


@login_required
@permission_required('mascotas.change_mascota', raise_exception=True)
def subir_foto(request, pk):
    mascota = get_object_or_404(Mascota.objects.select_related('especie'), pk=pk)
    form = FotoForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        guardar_foto(mascota, form.cleaned_data['foto'], request.user)
        messages.success(request, f'Se guardó la foto de {mascota.nombre}.')
        return redirect(_volver(request, mascota))
    return render(request, 'mascotas/foto_form.html', {
        'seccion': 'mascotas',
        'mascota': mascota,
        'form': form,
        'next': _volver(request, mascota),
    })


@require_POST
@login_required
@permission_required('mascotas.change_mascota', raise_exception=True)
def quitar_foto(request, pk):
    mascota = get_object_or_404(Mascota, pk=pk)
    FotoMascota.objects.filter(mascota=mascota).delete()
    Mascota.objects.filter(pk=pk).update(foto_version=0)
    messages.success(request, f'Se quitó la foto de {mascota.nombre}.')
    return redirect(_volver(request, mascota))
