from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render

from .models import Especie, Mascota, Tenencia
from .rut import limpiar_rut


@login_required
def listado(request):
    """Fichas de los pacientes de la clínica, filtrables por tipo de mascota."""

    buscar = request.GET.get('buscar', '').strip()
    tipo = request.GET.get('tipo', '')

    mascotas = (Mascota.objects
                .select_related('especie', 'raza')
                .prefetch_related('tenencias__cliente')
                .filter(activo=True)
                .annotate(
                    total_citas=Count('citas'),
                    inasistencias=Count('citas', filter=Q(citas__estado='no_asistio')),
                ))

    if tipo:
        mascotas = mascotas.filter(especie_id=tipo)

    if buscar:
        # Se busca por nombre de la mascota, o por nombre o RUT de sus clientes.
        # Lo de los clientes va en una subconsulta para no duplicar filas ni
        # inflar los conteos de citas.
        de_clientes = Tenencia.objects.filter(
            Q(cliente__nombres__icontains=buscar)
            | Q(cliente__apellidos__icontains=buscar)
            | Q(cliente__rut__icontains=limpiar_rut(buscar) or buscar)
        ).values('mascota')
        mascotas = mascotas.filter(Q(nombre__icontains=buscar) | Q(pk__in=de_clientes))

    tipos = (Especie.objects
             .annotate(cantidad=Count('mascota', filter=Q(mascota__activo=True)))
             .filter(cantidad__gt=0))

    return render(request, 'mascotas/listado.html', {
        'seccion': 'mascotas',
        'mascotas': mascotas,
        'total': mascotas.count(),
        'buscar': buscar,
        'tipos': tipos,
        'tipo_activo': tipo,
    })
