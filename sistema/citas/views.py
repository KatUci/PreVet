from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import Cita


@login_required
def listado(request):
    """Listado de citas con filtro por estado."""

    estado = request.GET.get('estado', '')

    citas = (Cita.objects
                 .select_related('mascota', 'cliente', 'veterinario', 'tipo_atencion')
                 .order_by('-fecha', '-hora'))

    if estado:
        citas = citas.filter(estado=estado)

    hoy = timezone.localdate()

    # Cada filtro con su propio conteo, listo para la plantilla.
    filtros = [
        {
            'valor': valor,
            'etiqueta': etiqueta,
            'conteo': Cita.objects.filter(estado=valor).count(),
        }
        for valor, etiqueta in Cita.ESTADOS
    ]

    return render(request, 'citas/listado.html', {
        'seccion': 'citas',
        'citas': citas[:120],
        'total': citas.count(),
        'total_general': Cita.objects.count(),
        'estado_activo': estado,
        'filtros': filtros,
        'hoy': hoy,
    })


@login_required
def marcar_no_asistio(request, pk):
    """Registra que el tutor no se presentó a su hora."""

    if request.method != 'POST':
        return redirect('citas')

    cita = Cita.objects.get(pk=pk)
    cita.estado = 'no_asistio'
    cita.fecha_marcada_no_asistio = timezone.now()
    cita.save()

    messages.success(
        request,
        f'{cita.mascota.nombre} quedó registrada como inasistencia. '
        f'Se perdieron ${cita.tipo_atencion.precio:,}'.replace(',', '.')
    )
    return redirect(request.META.get('HTTP_REFERER', '/citas/'))