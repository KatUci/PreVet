"""Vistas para registrar clientes y sus mascotas."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import ClienteForm, MascotaForm
from .models import Cliente, Tenencia


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
        'seccion': 'citas',
        'form': form,
        'next': _volver_a(request, ''),
    })


@login_required
@permission_required('mascotas.add_mascota', raise_exception=True)
def mascota_nueva(request, cliente_pk):
    cliente = get_object_or_404(Cliente, pk=cliente_pk)
    form = MascotaForm(request.POST or None)

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
        messages.success(request, f'{mascota.nombre} quedó registrada a nombre de {cliente.nombre_completo}.')
        return redirect(_volver_a(request, f'/citas/nueva/?rut={cliente.rut}'))

    return render(request, 'mascotas/mascota_form.html', {
        'seccion': 'citas',
        'form': form,
        'cliente': cliente,
        'next': _volver_a(request, ''),
    })
