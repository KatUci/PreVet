from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone

from citas.models import Cita


@login_required
def inicio(request):
    """Tablero con los indicadores de inasistencia."""

    hoy = timezone.localdate()

    # Solo las citas que ya ocurrieron: de las futuras todavía
    # no se sabe si van a concretarse.
    ocurridas = Cita.objects.filter(fecha__lt=hoy).exclude(estado='pendiente')

    total = ocurridas.count()
    faltas = ocurridas.filter(estado='no_asistio')
    n_faltas = faltas.count()

    tasa = (n_faltas / total * 100) if total else 0
    perdido = faltas.aggregate(t=Sum('tipo_atencion__precio'))['t'] or 0

    # Inasistencias por día de la semana, para ver si hay patrón.
    nombres = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    por_dia = []
    for numero, nombre in enumerate(nombres):
        del_dia = [c for c in ocurridas if c.fecha.weekday() == numero]
        n = len(del_dia)
        f = len([c for c in del_dia if c.estado == 'no_asistio'])
        if n:
            por_dia.append({
                'dia': nombre,
                'total': n,
                'faltas': f,
                'tasa': round(f / n * 100),
            })

    tope = max([d['tasa'] for d in por_dia] + [1])
    for d in por_dia:
        d['alto'] = round(d['tasa'] / tope * 100)

    contexto = {
        'seccion': 'inicio',
        'total_ocurridas': total,
        'total_faltas': n_faltas,
        'tasa': round(tasa, 1),
        'perdido': perdido,
        'por_dia': por_dia,
        'proximas': Cita.objects.filter(fecha__gte=hoy, estado='pendiente')
                                .select_related('mascota', 'veterinario', 'tipo_atencion')
                                .order_by('fecha', 'hora')[:8],
    }
    return render(request, 'core/inicio.html', contexto)