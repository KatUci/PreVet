"""Carnet de vacunas (PV-FIC-04).

El veterinario registra la vacuna que aplicó y, si corresponde, la fecha de
la próxima dosis. Recepción ve en "Vacunas por vencer" a quién hay que
recordarle la siguiente vacuna y le puede escribir por WhatsApp.
"""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from citas.contacto import armar_mensaje, enlace_whatsapp

from .forms import VacunaForm
from .models import Mascota, Vacuna

# Cuántos días hacia adelante (y hacia atrás, las atrasadas) muestra la lista.
DIAS_AVISO = 30


@login_required
@permission_required('mascotas.add_vacuna', raise_exception=True)
def registrar(request, pk):
    """Agrega una vacuna al carnet de la mascota."""
    mascota = get_object_or_404(Mascota, pk=pk)
    form = VacunaForm(request.POST or None, initial={'fecha_aplicacion': timezone.localdate()})

    if request.method == 'POST' and form.is_valid():
        vacuna = form.save(commit=False)
        vacuna.mascota = mascota
        vacuna.registrada_por = request.user
        vacuna.save()
        messages.success(request, f'La vacuna {vacuna.nombre} quedó en el carnet de {mascota.nombre}.')
        return redirect('mascota_ficha', pk=mascota.pk)

    return render(request, 'mascotas/vacuna_form.html', {
        'seccion': 'mascotas',
        'mascota': mascota,
        'form': form,
    })


@login_required
@permission_required('mascotas.view_vacuna', raise_exception=True)
def por_vencer(request):
    """Próximas dosis de los siguientes 30 días y las que ya se atrasaron."""
    hoy = timezone.localdate()
    candidatas = (Vacuna.objects
                  .filter(proxima_dosis__gte=hoy - timedelta(days=DIAS_AVISO),
                          proxima_dosis__lte=hoy + timedelta(days=DIAS_AVISO),
                          mascota__activo=True)
                  .select_related('mascota__especie')
                  .prefetch_related('mascota__tenencias__cliente')
                  .order_by('proxima_dosis'))

    filas = []
    for vacuna in candidatas:
        # Si después ya se puso la misma vacuna, esta dosis ya está cubierta.
        if vacuna.mascota.vacunas.filter(nombre__iexact=vacuna.nombre,
                                         fecha_aplicacion__gt=vacuna.fecha_aplicacion).exists():
            continue
        tutor = vacuna.mascota.responsable
        whatsapp = None
        if tutor:
            mensaje = armar_mensaje('vacuna', {
                'tutor': tutor.nombres, 'mascota': vacuna.mascota.nombre,
                'vacuna': vacuna.nombre, 'fecha': vacuna.proxima_dosis.strftime('%d/%m/%Y')})
            whatsapp = enlace_whatsapp(tutor.telefono, mensaje)
        filas.append({
            'vacuna': vacuna,
            'tutor': tutor,
            'whatsapp': whatsapp,
            'atrasada': vacuna.proxima_dosis < hoy,
        })

    return render(request, 'mascotas/vacunas_por_vencer.html', {
        'seccion': 'vacunas',
        'filas': filas,
        'dias': DIAS_AVISO,
    })
