"""Sección Clientes: directorio con buscador y ficha de cada cliente.

Se arma con los datos que ya existen (clientes, tenencias y citas). El
historial del tutor es el factor que más pesa en el riesgo de inasistencia,
por eso la ficha lo muestra completo.
"""
import re

from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Count, Min, Q, Sum
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from citas.contacto import enlace_whatsapp

from .models import Cliente, Etiqueta
from .rut import limpiar_rut

# Faltas anteriores desde las que el cliente se marca como reincidente.
FALTAS_REINCIDENTE = 2

ORDENES = {
    'nombre': ('apellidos', 'nombres'),
    'faltas': ('-n_faltas', 'apellidos'),
    'recientes': ('-fecha_registro',),
}


def filtrar_clientes(clientes, q):
    """Cada palabra debe aparecer en el nombre, el teléfono, el correo, el RUT
    (con o sin puntos) o el nombre de alguna de sus mascotas."""
    for palabra in q.split():
        condicion = (Q(nombres__icontains=palabra) | Q(apellidos__icontains=palabra)
                     | Q(telefono__icontains=palabra) | Q(email__icontains=palabra)
                     | Q(mascotas__nombre__icontains=palabra))
        digitos = re.sub(r'[^0-9kK]', '', palabra)
        if len(digitos) >= 4 and digitos[:-1].isdigit():
            condicion |= Q(rut__startswith=limpiar_rut(digitos)) | Q(rut__startswith=digitos)
        clientes = clientes.filter(condicion)
    return clientes.distinct()


def _tasa(faltas, resueltas):
    return round(faltas / resueltas * 100) if resueltas else None


@login_required
@permission_required('mascotas.view_cliente', raise_exception=True)
def clientes_listado(request):
    """Directorio de clientes con sus mascotas, citas e inasistencias."""

    hoy = timezone.localdate()
    q = request.GET.get('q', '').strip()
    filtro = request.GET.get('filtro', '')
    orden = request.GET.get('orden', 'nombre')
    if orden not in ORDENES:
        orden = 'nombre'

    clientes = Cliente.objects.filter(activo=(filtro != 'inactivos')).annotate(
        n_mascotas=Count('tenencias', distinct=True),
        n_citas=Count('citas', filter=~Q(citas__estado='cancelada'), distinct=True),
        n_faltas=Count('citas', filter=Q(citas__estado='no_asistio'), distinct=True),
        n_resueltas=Count('citas', filter=Q(citas__estado__in=['completada', 'no_asistio']), distinct=True),
        proxima=Min('citas__fecha', filter=Q(citas__estado='pendiente', citas__fecha__gte=hoy)),
    )

    clientes = filtrar_clientes(clientes, q)

    if filtro == 'reincidentes':
        clientes = clientes.filter(n_faltas__gte=FALTAS_REINCIDENTE)
    elif filtro == 'proxima':
        clientes = clientes.filter(proxima__isnull=False)
    elif filtro == 'sin_telefono':
        clientes = clientes.filter(telefono='')
    elif filtro == 'inactivos':
        pass
    else:
        filtro = ''

    pagina = Paginator(clientes.order_by(*ORDENES[orden]), 20).get_page(request.GET.get('pagina'))
    for c in pagina:
        c.tasa = _tasa(c.n_faltas, c.n_resueltas)
        c.reincidente = c.n_faltas >= FALTAS_REINCIDENTE

    parametros = request.GET.copy()
    parametros.pop('pagina', None)
    return render(request, 'mascotas/clientes_listado.html', {
        'seccion': 'clientes',
        'pagina': pagina,
        'rango_paginas': pagina.paginator.get_elided_page_range(pagina.number, on_each_side=2, on_ends=1),
        'q': q,
        'filtro': filtro,
        'orden': orden,
        'qs': parametros.urlencode(),
        'total_activos': Cliente.objects.filter(activo=True).count(),
        'filtros': [('', 'Todos'), ('reincidentes', 'Reincidentes'), ('proxima', 'Con cita próxima'),
                    ('sin_telefono', 'Sin teléfono'), ('inactivos', 'Inactivos')],
    })


@login_required
@permission_required('mascotas.view_cliente', raise_exception=True)
def cliente_ficha(request, pk):
    """Ficha del cliente: datos, mascotas, próximas citas e historial."""

    cliente = get_object_or_404(Cliente, pk=pk)
    hoy = timezone.localdate()

    tenencias = (cliente.tenencias.select_related('mascota__especie', 'mascota__raza')
                 .prefetch_related('mascota__etiquetas')
                 .order_by('-es_principal', 'mascota__nombre'))
    citas = (cliente.citas.select_related('mascota__especie', 'veterinario', 'tipo_atencion')
             .order_by('-fecha', '-hora'))

    resumen = citas.aggregate(
        total=Count('id', filter=~Q(estado='cancelada')),
        atendidas=Count('id', filter=Q(estado='completada')),
        faltas=Count('id', filter=Q(estado='no_asistio')),
        canceladas=Count('id', filter=Q(estado='cancelada')),
        perdido=Sum('tipo_atencion__precio', filter=Q(estado='no_asistio')),
    )
    resumen['tasa'] = _tasa(resumen['faltas'], resumen['atendidas'] + resumen['faltas'])
    resumen['perdido_txt'] = f"{resumen['perdido'] or 0:,}".replace(',', '.')

    proximas = list(citas.filter(estado='pendiente', fecha__gte=hoy).order_by('fecha', 'hora'))
    if proximas and request.user.has_perm('citas.ver_riesgo'):
        from citas.riesgo import estadisticas, puntuar
        stats = estadisticas()
        for cita in proximas:
            cita.puntaje, cita.nivel, cita.accion, _ = puntuar(cita, stats)

    historial = Paginator(citas.exclude(estado='pendiente', fecha__gte=hoy), 10).get_page(request.GET.get('pagina'))

    mensaje = (f'Hola {cliente.nombres}, te escribimos de la clínica veterinaria. '
               f'¿Tienes un momento para conversar sobre la próxima atención de tu mascota?')
    return render(request, 'mascotas/cliente_ficha.html', {
        'seccion': 'clientes',
        'cliente': cliente,
        'tenencias': tenencias,
        'resumen': resumen,
        'reincidente': resumen['faltas'] >= FALTAS_REINCIDENTE,
        'proximas': proximas,
        'historial': historial,
        'whatsapp': enlace_whatsapp(cliente.telefono, mensaje),
        'hoy': hoy,
        'etiquetas_disponibles': Etiqueta.objects.filter(para=Etiqueta.Para.CLIENTE, activo=True),
        'etiquetas_actuales': list(cliente.etiquetas.values_list('pk', flat=True)),
    })
