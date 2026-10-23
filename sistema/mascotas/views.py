from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .models import Especie, Etiqueta, Mascota, Tenencia
from .rut import limpiar_rut


@login_required
@permission_required('mascotas.view_mascota', raise_exception=True)
def listado(request):
    """Fichas de los pacientes de la clínica, filtrables por tipo de mascota."""

    buscar = request.GET.get('buscar', '').strip()
    tipo = request.GET.get('tipo', '')

    mascotas = (Mascota.objects
                .select_related('especie', 'raza')
                .prefetch_related('tenencias__cliente', 'etiquetas')
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


@login_required
@permission_required('mascotas.view_mascota', raise_exception=True)
def ficha(request, pk):
    """Ficha de la mascota: sus datos, sus tutores, su historial clínico y sus citas.

    El historial clínico (diagnósticos y tratamientos) solo lo ve quien tiene
    el permiso citas.view_atencion: veterinarios y administración.
    """
    from citas.models import Atencion

    mascota = get_object_or_404(Mascota.objects.select_related('especie', 'raza'), pk=pk)
    tenencias = mascota.tenencias.select_related('cliente').order_by('-es_principal', 'cliente__apellidos')

    atenciones = None
    if request.user.has_perm('citas.view_atencion'):
        # Ordenadas por fecha de la atención, de la más reciente a la más antigua.
        atenciones = (Atencion.objects.filter(cita__mascota=mascota)
                      .select_related('cita__veterinario', 'cita__tipo_atencion', 'registrada_por')
                      .order_by('-cita__fecha', '-cita__hora'))

    citas = (mascota.citas.select_related('veterinario', 'tipo_atencion', 'cliente')
             .order_by('-fecha', '-hora'))
    resumen = citas.aggregate(
        total=Count('id', filter=~Q(estado='cancelada')),
        atendidas=Count('id', filter=Q(estado='completada')),
        faltas=Count('id', filter=Q(estado='no_asistio')),
    )

    return render(request, 'mascotas/ficha.html', {
        'seccion': 'mascotas',
        'mascota': mascota,
        'tenencias': tenencias,
        'atenciones': atenciones,
        'citas': Paginator(citas, 10).get_page(request.GET.get('pagina')),
        'resumen': resumen,
        'etiquetas_disponibles': Etiqueta.objects.filter(para=Etiqueta.Para.MASCOTA, activo=True),
        'etiquetas_actuales': list(mascota.etiquetas.values_list('pk', flat=True)),
    })
