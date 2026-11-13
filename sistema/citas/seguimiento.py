"""Seguimiento tras una inasistencia (PV-REC-07).

Cuando un tutor no llega, recepción tiene 24 horas para llamarlo y tratar de
recuperar la atención. Apenas se marca la inasistencia aparece la tarea en la
lista de llamadas, con su plazo, y se cierra registrando el resultado.
"""
import datetime
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .contacto import armar_mensaje, datos_de_cita, enlace_whatsapp
from .models import Cita

PLAZO = datetime.timedelta(hours=24)
# Las inasistencias más antiguas ya no se recuperan llamando: salen de la lista.
VENTANA = datetime.timedelta(days=7)
RESULTADOS = dict(Cita.SEGUIMIENTOS)


def pendientes():
    """Inasistencias de la última semana a las que todavía nadie ha llamado, con su plazo."""
    ahora = timezone.now()
    citas = (Cita.objects.filter(estado='no_asistio', seguimiento='',
                                 fecha_marcada_no_asistio__gte=ahora - VENTANA)
             .select_related('mascota__especie', 'cliente', 'veterinario', 'tipo_atencion')
             .order_by('fecha_marcada_no_asistio'))
    tareas = []
    for cita in citas:
        vence = cita.fecha_marcada_no_asistio + PLAZO
        quedan = vence - ahora
        tareas.append({
            'cita': cita,
            'vence': vence,
            'atrasada': quedan.total_seconds() < 0,
            # Horas que quedan o, si ya venció, horas de atraso (siempre hacia abajo).
            'horas': int(abs(quedan.total_seconds()) // 3600),
            'whatsapp': enlace_whatsapp(cita.cliente.telefono, armar_mensaje('inasistencia', datos_de_cita(cita))),
        })
    return tareas


@require_POST
@login_required
@permission_required('citas.change_cita', raise_exception=True)
def registrar(request, pk):
    """Cierra la tarea de llamar con su resultado. Si reagendó, sigue directo a agendar."""
    cita = get_object_or_404(Cita.objects.select_related('mascota', 'cliente'), pk=pk, estado='no_asistio')
    resultado = request.POST.get('resultado', '')
    if resultado not in RESULTADOS:
        messages.error(request, 'Elige el resultado de la llamada.')
        return redirect('llamadas')

    cita.seguimiento, cita.seguimiento_fecha, cita.seguimiento_por = resultado, timezone.now(), request.user
    cita.save(update_fields=['seguimiento', 'seguimiento_fecha', 'seguimiento_por'])

    if resultado == 'reagendo':
        messages.success(request, f'Agenda la nueva hora de {cita.mascota.nombre}.')
        return redirect(reverse('agendar') + '?' + urlencode({'rut': cita.cliente.rut, 'mascota': cita.mascota_id}))
    messages.success(request, f'Seguimiento de {cita.mascota.nombre}: {RESULTADOS[resultado].lower()}.')
    return redirect('llamadas')
