"""Vistas para registrar clientes y sus mascotas."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .fotos import guardar_foto
from .forms import ClienteForm, MascotaEditarForm, MascotaForm
from .models import Cliente, Mascota, Tenencia


def _volver_a(request, por_defecto):
    """La página a la que volver después de guardar (por ejemplo, agendar hora).

    Solo se aceptan direcciones del propio sistema, para que nadie pueda
    armar un enlace que mande a otro sitio después de guardar.
    """
    destino = request.POST.get('next') or request.GET.get('next')
    if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        return destino
    return por_defecto


@login_required
@permission_required('mascotas.add_cliente', raise_exception=True)
def cliente_nuevo(request):
    form = ClienteForm(request.POST or None, initial={'rut': request.GET.get('rut', '')})

    if request.method == 'POST' and form.is_valid():
        cliente = form.save()
        messages.success(request, f'{cliente.nombre_completo} quedó registrado como cliente.')
        return redirect(_volver_a(request, f'/citas/nueva/?rut={cliente.rut}'))

    return render(request, 'mascotas/cliente_form.html', {
        'seccion': 'clientes',
        'form': form,
        'next': _volver_a(request, ''),
    })


@login_required
@permission_required('mascotas.add_mascota', raise_exception=True)
def mascota_nueva(request, cliente_pk):
    cliente = get_object_or_404(Cliente, pk=cliente_pk)
    form = MascotaForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        # La mascota y su vínculo con el cliente se guardan juntos: si algo
        # falla a mitad de camino, no queda una mascota sin cliente.
        with transaction.atomic():
            mascota = form.save()
            Tenencia.objects.create(
                cliente=cliente, mascota=mascota,
                relacion=form.cleaned_data['relacion'],
                es_principal=True,
            )
            if form.cleaned_data.get('foto'):
                guardar_foto(mascota, form.cleaned_data['foto'], request.user)
        messages.success(request, f'{mascota.nombre} quedó registrada a nombre de {cliente.nombre_completo}.')
        return redirect(_volver_a(request, f'/citas/nueva/?rut={cliente.rut}'))

    return render(request, 'mascotas/mascota_form.html', {
        'seccion': 'clientes',
        'form': form,
        'cliente': cliente,
        'next': _volver_a(request, ''),
    })


@login_required
@permission_required('mascotas.change_cliente', raise_exception=True)
def cliente_editar(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    form = ClienteForm(request.POST or None, instance=cliente)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Se guardaron los datos de {cliente.nombre_completo}.')
        return redirect('cliente_ficha', pk=cliente.pk)
    return render(request, 'mascotas/cliente_form.html', {
        'seccion': 'clientes', 'form': form, 'cliente': cliente, 'editando': True,
        'next': reverse('cliente_ficha', args=[cliente.pk]),
    })


@require_POST
@login_required
@permission_required('mascotas.change_cliente', raise_exception=True)
def cliente_estado(request, pk):
    """Desactiva o reactiva al cliente. No se borra: sus citas alimentan el modelo de riesgo."""
    cliente = get_object_or_404(Cliente, pk=pk)
    cliente.activo = not cliente.activo
    cliente.save(update_fields=['activo'])
    if cliente.activo:
        messages.success(request, f'{cliente.nombre_completo} volvió a quedar activo.')
    else:
        messages.success(request, f'{cliente.nombre_completo} quedó inactivo: ya no aparece al agendar, '
                                  f'pero se conserva su historial.')
    return redirect('cliente_ficha', pk=cliente.pk)


@login_required
@permission_required('mascotas.change_mascota', raise_exception=True)
def mascota_editar(request, pk):
    mascota = get_object_or_404(Mascota, pk=pk)
    form = MascotaEditarForm(request.POST or None, instance=mascota)
    volver = _volver_a(request, '/mascotas/')
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Se guardaron los datos de {mascota.nombre}.')
        return redirect(volver)
    return render(request, 'mascotas/mascota_editar.html', {
        'seccion': 'mascotas', 'form': form, 'mascota': mascota, 'next': volver,
    })


@require_POST
@login_required
@permission_required('mascotas.change_mascota', raise_exception=True)
def mascota_estado(request, pk):
    """Desactiva (por ejemplo, si falleció o se cambió de clínica) o reactiva a la mascota."""
    mascota = get_object_or_404(Mascota, pk=pk)
    mascota.activo = not mascota.activo
    mascota.save(update_fields=['activo'])
    estado = 'volvió a quedar activa' if mascota.activo else 'quedó inactiva: se conserva su historial'
    messages.success(request, f'{mascota.nombre} {estado}.')
    return redirect(_volver_a(request, '/mascotas/'))
