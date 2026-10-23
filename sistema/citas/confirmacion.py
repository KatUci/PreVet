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


@login_required
@permission_required('citas.ver_riesgo', raise_exception=True)
def llamadas(request):
    """Lista de llamadas (PV-REC-02): citas de un día ordenadas por riesgo.

    Por defecto muestra las de mañana, que es cuando conviene confirmar. Cada
    fila trae el teléfono, el WhatsApp con el mensaje según el riesgo, el
    guion de la llamada y los botones para registrar el resultado.
    """
    import datetime

    from django.shortcuts import render

    from .calendario import _enlace_whatsapp
    from .contacto import guion_llamada
    from .riesgo import estadisticas, puntuar

    hoy = timezone.localdate()
    manana = hoy + datetime.timedelta(days=1)
    try:
        fecha = datetime.date.fromisoformat(request.GET.get('fecha', ''))
    except ValueError:
        fecha = manana
    fecha = max(fecha, hoy)
    solo_pendientes = request.GET.get('filtro') == 'pendientes'

    citas = list(Cita.objects.filter(fecha=fecha, estado='pendiente')
                 .select_related('mascota__especie', 'cliente', 'veterinario', 'tipo_atencion',
                                 'confirmacion_por'))
    filas = []
    if citas:
        stats = estadisticas()
        for cita in citas:
            puntaje, nivel, accion, detalle = puntuar(cita, stats)
            filas.append({'cita': cita, 'puntaje': puntaje, 'nivel': nivel, 'accion': accion,
                          'detalle': detalle, 'whatsapp': _enlace_whatsapp(cita, nivel),
                          'guion': guion_llamada(cita, nivel, stats)})
    # Primero las de mayor riesgo; a igual riesgo, la que es más temprano.
    filas.sort(key=lambda f: (-f['puntaje'], f['cita'].hora))

    avance = {valor: sum(1 for f in filas if f['cita'].confirmacion == valor) for valor in RESULTADOS}
    avance['total'] = len(filas)
    avance['contactadas'] = sum(1 for f in filas if f['cita'].confirmacion in ('confirmada', 'pidio_cambio'))
    avance['por_llamar'] = avance['total'] - avance['contactadas']
    avance['pct'] = round(avance['contactadas'] / avance['total'] * 100) if avance['total'] else 0

    if solo_pendientes:
        # "No contesta" sigue pendiente: hay que volver a intentar.
        filas = [f for f in filas if f['cita'].confirmacion not in ('confirmada', 'pidio_cambio')]

    return render(request, 'citas/llamadas.html', {
        'seccion': 'llamadas',
        'fecha': fecha,
        'hoy': hoy,
        'manana': manana,
        'dias': [hoy + datetime.timedelta(days=n) for n in range(4)],
        'filas': filas,
        'avance': avance,
        'solo_pendientes': solo_pendientes,
        'resultados': Cita.CONFIRMACIONES,
    })
