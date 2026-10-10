from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render

from .models import Mascota


@login_required
def listado(request):
    """Fichas de los pacientes de la clínica."""

    buscar = request.GET.get('buscar', '')

    mascotas = (Mascota.objects
                .select_related('especie', 'raza', 'dueno')
                .filter(activo=True)
                .annotate(
                    total_citas=Count('citas'),
                    inasistencias=Count('citas', filter=Q(citas__estado='no_asistio')),
                ))

    if buscar:
        mascotas = mascotas.filter(nombre__icontains=buscar)

    return render(request, 'mascotas/listado.html', {
        'seccion': 'mascotas',
        'mascotas': mascotas,
        'total': mascotas.count(),
        'buscar': buscar,
    })