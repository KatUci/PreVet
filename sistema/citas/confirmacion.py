"""Confirmación de citas (PV-CIT-05).

Recepción registra el resultado de contactar al tutor antes de la cita:
confirmó, no contesta o pidió cambio. Se guarda quién lo registró y cuándo,
y se muestra en el calendario, en el detalle de la cita y en Horas en riesgo.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import Cita

RESULTADOS = dict(Cita.CONFIRMACIONES)


def _destino(request, cita):
    destino = request.POST.get('next')
    if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        return destino
    return f'/citas/calendario/?fecha={cita.fecha.isoformat()}'


@require_POST
@login_required
@permission_required('citas.change_cita', raise_exception=True)
def registrar(request, pk):
    cita = get_object_or_404(Cita.objects.select_related('mascota'), pk=pk)
    volver = _destino(request, cita)
    resultado = request.POST.get('resultado', '')

    if cita.estado != 'pendiente':
        messages.error(request, 'Esa cita ya no está pendiente: no se registra la confirmación.')
        return redirect(volver)
    if resultado not in RESULTADOS:
        messages.error(request, 'Elige el resultado del contacto.')
        return redirect(volver)

    cita.confirmacion = resultado
    cita.confirmacion_fecha = timezone.now()
    cita.confirmacion_por = request.user
    cita.save(update_fields=['confirmacion', 'confirmacion_fecha', 'confirmacion_por'])

    if resultado == 'pidio_cambio':
        # El siguiente paso natural es moverla: se ofrece el enlace directo.
        messages.warning(request, f'El tutor de {cita.mascota.nombre} pidió cambiar la hora: '
                                  f'reagéndala para dejar libre el bloque.')
        return redirect(reverse('cita_reagendar', args=[cita.pk]))
    else:
        messages.success(request, f'Cita de {cita.mascota.nombre}: {RESULTADOS[resultado].lower()}.')
    return redirect(volver)
