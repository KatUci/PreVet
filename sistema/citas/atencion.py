"""Ficha clínica: el veterinario registra la atención al cerrar la cita.

Antes, marcar una cita como atendida solo cambiaba su estado. Ahora se pide
lo mínimo que una clínica necesita guardar de cada consulta: el motivo, el
diagnóstico, el tratamiento y el peso. Solo lo registran los veterinarios
(permiso citas.add_atencion), porque es información clínica.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import AtencionForm
from .models import Atencion, Cita


def _destino(request, cita):
    destino = request.POST.get('next') or request.GET.get('next')
    if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        return destino
    return f'/citas/calendario/?fecha={cita.fecha.isoformat()}'


@login_required
@permission_required('citas.add_atencion', raise_exception=True)
def atender(request, pk):
    """Registra la atención y deja la cita como completada."""
    cita = get_object_or_404(Cita.objects.select_related('mascota__especie', 'mascota__raza', 'cliente',
                                                         'veterinario', 'tipo_atencion'), pk=pk)
    volver = _destino(request, cita)

    if cita.estado != 'pendiente':
        messages.error(request, 'Esa cita ya no está pendiente: no se puede registrar la atención.')
        return redirect(volver)
    if cita.fecha > timezone.localdate():
        messages.error(request, 'Una cita futura todavía no se puede marcar como atendida.')
        return redirect(volver)

    form = AtencionForm(request.POST or None, initial={
        'motivo': cita.notas[:200] or cita.tipo_atencion.nombre,
        'peso_kg': cita.mascota.peso_kg,
    })
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            # Se bloquea la cita para que dos personas no la cierren a la vez.
            cita = Cita.objects.select_for_update().get(pk=cita.pk)
            if cita.estado != 'pendiente' or Atencion.objects.filter(cita=cita).exists():
                messages.error(request, 'Otra persona ya cerró esta atención.')
                return redirect(volver)
            atencion = form.save(commit=False)
            atencion.cita = cita
            atencion.registrada_por = request.user
            atencion.save()
            cita.estado = 'completada'
            cita.save(update_fields=['estado'])
            if atencion.peso_kg:
                mascota = cita.mascota
                mascota.peso_kg = atencion.peso_kg
                mascota.save(update_fields=['peso_kg'])
        messages.success(request, f'La atención de {cita.mascota.nombre} quedó registrada y la cita cerrada.')
        return redirect(volver)

    return render(request, 'citas/atender.html', {
        'seccion': 'calendario',
        'cita': cita,
        'form': form,
        'next': volver,
        'anteriores': (Atencion.objects.filter(cita__mascota=cita.mascota)
                       .select_related('cita__veterinario', 'cita__tipo_atencion')[:3]),
    })
