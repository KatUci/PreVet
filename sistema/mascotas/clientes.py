"""Vistas para registrar clientes y sus mascotas."""
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .fotos import guardar_foto
from .forms import ClienteForm, MascotaEditarForm, MascotaForm
from .models import Cliente, Etiqueta, Mascota, Tenencia
from .rut import limpiar_rut


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


def _guardar_etiquetas(request, objeto, para):
    """Deja en el cliente o la mascota exactamente las etiquetas marcadas.

    Solo se aceptan etiquetas disponibles y del tipo que corresponde. Las que
    ya tenía y luego se desactivaron en el catálogo se conservan.
    """
    elegidas = Etiqueta.objects.filter(pk__in=request.POST.getlist('etiquetas'), para=para, activo=True)
    no_disponibles = objeto.etiquetas.filter(activo=False)
    objeto.etiquetas.set([*elegidas, *no_disponibles])


@require_POST
@login_required
@permission_required('mascotas.change_cliente', raise_exception=True)
def cliente_etiquetas(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    _guardar_etiquetas(request, cliente, Etiqueta.Para.CLIENTE)
    messages.success(request, f'Se actualizaron las etiquetas de {cliente.nombre_completo}.')
    return redirect(_volver_a(request, reverse('cliente_ficha', args=[cliente.pk])))


@require_POST
@login_required
@permission_required('mascotas.change_mascota', raise_exception=True)
def mascota_etiquetas(request, pk):
    mascota = get_object_or_404(Mascota, pk=pk)
    _guardar_etiquetas(request, mascota, Etiqueta.Para.MASCOTA)
    messages.success(request, f'Se actualizaron las etiquetas de {mascota.nombre}.')
    return redirect(_volver_a(request, reverse('mascota_ficha', args=[mascota.pk])))


@login_required
@permission_required('mascotas.add_tenencia', raise_exception=True)
def asociar_mascota(request, pk):
    """Asocia a este cliente una mascota que ya está registrada con otro tutor (PV-CLI-06).

    Sirve cuando otra persona de la familia empieza a traer a la mascota: en
    vez de registrarla de nuevo (y partir su historial en dos), se agrega
    este cliente como tutor de la misma ficha.
    """
    from django.db.models import Q

    cliente = get_object_or_404(Cliente, pk=pk)
    ficha = reverse('cliente_ficha', args=[cliente.pk])

    if request.method == 'POST':
        mascota = get_object_or_404(Mascota, pk=request.POST.get('mascota'), activo=True)
        relacion = request.POST.get('relacion', '')
        if relacion not in Tenencia.Relacion.values:
            messages.error(request, 'Elige qué relación tiene el cliente con la mascota.')
            return redirect(f"{reverse('asociar_mascota', args=[cliente.pk])}?q={mascota.nombre}")
        if Tenencia.objects.filter(cliente=cliente, mascota=mascota).exists():
            messages.info(request, f'{mascota.nombre} ya estaba asociada a {cliente.nombre_completo}.')
            return redirect(ficha)
        Tenencia.objects.create(
            cliente=cliente, mascota=mascota, relacion=relacion,
            # Si la mascota no tenía responsable principal, este cliente pasa a serlo.
            es_principal=not mascota.tenencias.filter(es_principal=True).exists(),
        )
        messages.success(request, f'{mascota.nombre} quedó asociada a {cliente.nombre_completo} '
                                  f'({Tenencia.Relacion(relacion).label.lower()}).')
        return redirect(ficha)

    q = request.GET.get('q', '').strip()
    resultados = []
    if len(q) >= 2:
        condicion = (Q(nombre__icontains=q) | Q(tutores__nombres__icontains=q)
                     | Q(tutores__apellidos__icontains=q))
        # El RUT del tutor, escrito con o sin puntos, completo o solo el comienzo.
        digitos = re.sub(r'[^0-9kK]', '', q)
        if len(digitos) >= 4 and digitos[:-1].isdigit():
            condicion |= Q(tutores__rut__startswith=limpiar_rut(digitos)) | Q(tutores__rut__startswith=digitos)
        resultados = (Mascota.objects.filter(condicion, activo=True)
                      .exclude(tenencias__cliente=cliente)
                      .select_related('especie', 'raza')
                      .prefetch_related('tenencias__cliente')
                      .distinct().order_by('nombre')[:20])

    return render(request, 'mascotas/asociar_mascota.html', {
        'seccion': 'clientes',
        'cliente': cliente,
        'q': q,
        'resultados': resultados,
        'relaciones': Tenencia.Relacion.choices,
    })
