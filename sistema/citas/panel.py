"""Panel del día para recepción: qué pasa hoy en la clínica y qué hay que hacer.

Todo se arma con los datos que ya existen (citas, horarios y riesgo), sin
tablas nuevas. Las consultas se hacen de una vez y el resto se calcula en
Python, porque la base está en la nube y cada consulta suma tiempo.
"""
import datetime

from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from .calendario import _enlace_whatsapp, _veterinarios
from .contacto import guion_llamada
from .forms import BLOQUES
from .models import Cita, HorarioAtencion

# Minutos de espera desde los que la tarjeta se marca en ámbar.
ESPERA_LARGA = 15
# Minutos de atraso desde los que una cita sin llegada se marca como atrasada.
ATRASO = 10
# Inasistencias anteriores desde las que el tutor se marca como reincidente.
FALTAS_REINCIDENTE = 2


def _minutos(desde, hasta):
    return max(int((hasta - desde).total_seconds() // 60), 0)


def _duracion(minutos):
    """68 -> '1 h 8 min'; 25 -> '25 min'."""
    horas, resto = divmod(minutos, 60)
    if not horas:
        return f'{resto} min'
    return f'{horas} h {resto} min' if resto else f'{horas} h'


def _huecos(fecha, desde_hora, vets, horarios, ocupadas, maximo=5):
    """Próximas horas libres de un día, con los profesionales disponibles en cada una."""
    libres = []
    for bloque in BLOQUES:
        if desde_hora and bloque <= desde_hora:
            continue
        disponibles = [vet for vet in vets
                       if (vet.pk, fecha, bloque) not in ocupadas
                       and any(h.veterinario_id == vet.pk and h.dia_semana == fecha.weekday()
                               and h.hora_inicio <= bloque < h.hora_fin for h in horarios)]
        if disponibles:
            libres.append({'hora': bloque, 'vets': disponibles})
            if len(libres) >= maximo:
                break
    return libres


@login_required
@permission_required('citas.view_cita', raise_exception=True)
def panel_dia(request):
    """Tablero "Hoy en la clínica": por llegar, en sala de espera y atendidas."""

    ahora = timezone.localtime()
    hoy = ahora.date()
    manana = hoy + datetime.timedelta(days=1)

    # Cada veterinario parte viendo solo sus citas, igual que en el calendario.
    perfil = getattr(request.user, 'perfil', None)
    es_vet = bool(perfil and perfil.rol == 'veterinario')

    base = Cita.objects.select_related('mascota__especie', 'cliente', 'veterinario', 'tipo_atencion')
    del_dia = base.filter(fecha=hoy).order_by('hora')
    if es_vet:
        del_dia = del_dia.filter(veterinario=request.user)
    del_dia = list(del_dia)

    # Tutores con inasistencias anteriores, para marcarlos en las tarjetas.
    clientes = {c.cliente_id for c in del_dia}
    faltas = dict(Cita.objects.filter(cliente_id__in=clientes, estado='no_asistio', fecha__lt=hoy)
                  .order_by().values_list('cliente_id').annotate(n=Count('id')))

    por_llegar, en_sala, en_atencion, listas, atendidas = [], [], [], [], []
    for cita in del_dia:
        tarjeta = {
            'cita': cita,
            'faltas': faltas.get(cita.cliente_id, 0),
            'sin_telefono': not cita.cliente.telefono,
        }
        if cita.estado == 'pendiente' and not cita.hora_llegada:
            inicio = timezone.make_aware(datetime.datetime.combine(hoy, cita.hora))
            tarjeta['atraso'] = _minutos(inicio, ahora) if ahora > inicio else 0
            tarjeta['atrasada'] = tarjeta['atraso'] >= ATRASO
            tarjeta['atraso_txt'] = _duracion(tarjeta['atraso'])
            por_llegar.append(tarjeta)
        elif cita.estado == 'pendiente' and not cita.inicio_atencion:
            tarjeta['espera'] = _minutos(cita.hora_llegada, ahora)
            tarjeta['espera_larga'] = tarjeta['espera'] >= ESPERA_LARGA
            tarjeta['espera_txt'] = _duracion(tarjeta['espera'])
            en_sala.append(tarjeta)
        elif cita.estado == 'pendiente':
            tarjeta['en_box_txt'] = _duracion(_minutos(cita.inicio_atencion, ahora))
            en_atencion.append(tarjeta)
        elif cita.estado == 'completada':
            atendidas.append(tarjeta)
            if not cita.hora_salida:
                listas.append(tarjeta)

    esperas = [t['espera'] for t in en_sala]
    no_llegaron = sum(1 for c in del_dia if c.estado == 'no_asistio')
    canceladas_hoy = sum(1 for c in del_dia if c.estado == 'cancelada')
    activas = [c for c in del_dia if c.estado != 'cancelada']

    # ---------- Bloques libres y ocupación ----------
    vets = list(_veterinarios())
    if es_vet:
        vets = [v for v in vets if v.pk == request.user.pk]
    horarios = list(HorarioAtencion.objects.filter(
        activo=True, dia_semana__in=[hoy.weekday(), manana.weekday()]))
    ocupadas = set(Cita.objects.filter(fecha__in=[hoy, manana])
                   .exclude(estado='cancelada')
                   .values_list('veterinario_id', 'fecha', 'hora'))

    bloques_hoy = sum(1 for b in BLOQUES for v in vets for h in horarios
                      if h.veterinario_id == v.pk and h.dia_semana == hoy.weekday()
                      and h.hora_inicio <= b < h.hora_fin)
    ocupacion = round(len(activas) / bloques_hoy * 100) if bloques_hoy else None

    # ---------- Confirmar mañana, de mayor a menor riesgo ----------
    confirmar = []
    if request.user.has_perm('citas.ver_riesgo'):
        from .riesgo import estadisticas, puntuar
        de_manana = list(base.filter(fecha=manana, estado='pendiente').order_by('hora'))
        if de_manana:
            stats = estadisticas()
            for cita in de_manana:
                puntaje, nivel, accion, _ = puntuar(cita, stats)
                confirmar.append({'cita': cita, 'puntaje': puntaje, 'nivel': nivel, 'accion': accion,
                                  # El mensaje y el guion cambian según el riesgo (contacto.py).
                                  'whatsapp': _enlace_whatsapp(cita, nivel),
                                  'guion': guion_llamada(cita, nivel, stats)})
            confirmar.sort(key=lambda c: -c['puntaje'])

    cancelaciones = (Cita.objects.filter(estado='cancelada', fecha_cancelacion__isnull=False)
                     .select_related('mascota', 'cliente', 'cancelada_por')
                     .order_by('-fecha_cancelacion')[:4])

    return render(request, 'citas/panel_dia.html', {
        'seccion': 'hoy' if request.path != '/' else 'inicio',
        'hoy': hoy,
        'manana': manana,
        'es_vet': es_vet,
        'por_llegar': por_llegar,
        'en_sala': en_sala,
        'en_atencion': en_atencion,
        'listas': listas,
        'atendidas': atendidas,
        'total_hoy': len(activas),
        'no_llegaron': no_llegaron,
        'canceladas_hoy': canceladas_hoy,
        'espera_promedio': round(sum(esperas) / len(esperas)) if esperas else None,
        'ocupacion': ocupacion,
        'confirmar': confirmar[:8],
        'confirmar_total': len(confirmar),
        'altos_manana': sum(1 for c in confirmar if c['nivel'] == 'alto'),
        # Como en las aerolíneas: una hora con alto riesgo de quedar vacía
        # puede recibir a un paciente extra (urgencia o lista de espera).
        'sobrecupo': [c for c in confirmar if c['nivel'] == 'alto'],
        'huecos_hoy': _huecos(hoy, ahora.time(), vets, horarios, ocupadas),
        'huecos_manana': _huecos(manana, None, vets, horarios, ocupadas),
        'cancelaciones': cancelaciones,
        'espera_larga': ESPERA_LARGA,
    })

