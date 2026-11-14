"""Horarios de los profesionales y horas libres para agendar.

Quien agenda (recepción o el mismo cliente desde Mi PreVet) ve desde el
principio qué días y a qué horas atiende cada profesional, y al elegir
profesional y fecha la lista de horas trae solo las libres. Así no se
entera recién al guardar de que ese día el profesional no atiende.
"""
import datetime
from itertools import groupby

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.utils import timezone

from .contacto import DIAS
from .forms import BLOQUES, ESTADOS_QUE_LIBERAN, veterinarios_con_horario
from .models import Cita, HorarioAtencion

DIAS_CORTOS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']

# Los profesionales que atienden urgencias se marcan con este grupo, en
# Administración > Personal (el grupo se crea en Grupos de permisos, sin permisos).
GRUPO_URGENCIAS = 'Urgencias'


def urgencias_ids():
    """Los profesionales que atienden urgencias."""
    return set(User.objects.filter(groups__name=GRUPO_URGENCIAS).values_list('pk', flat=True))


def _texto_tramos(tramos):
    return ' y '.join(f'{t.hora_inicio:%H:%M} a {t.hora_fin:%H:%M}' for t in tramos)


def _rango_dias(desde, hasta):
    if desde == hasta:
        return DIAS_CORTOS[desde]
    union = ' y ' if hasta == desde + 1 else ' a '
    return f'{DIAS_CORTOS[desde]}{union}{DIAS_CORTOS[hasta]}'


def resumen_horarios(veterinario=None):
    """Una entrada por profesional, con los días seguidos de igual horario juntos.

    Ej.: Paz Herrera → ['Lun a Vie 09:00 a 13:00 y 15:00 a 19:00', 'Sáb 09:00 a 19:00']
    """
    tramos = (HorarioAtencion.objects
              .filter(activo=True, veterinario__in=veterinarios_con_horario())
              .select_related('veterinario')
              .order_by('veterinario__first_name', 'veterinario_id', 'dia_semana', 'hora_inicio'))
    if veterinario is not None:
        tramos = tramos.filter(veterinario=veterinario)

    resumen = []
    de_urgencias = urgencias_ids()
    hoy = timezone.localdate().weekday()
    for vet, del_vet in groupby(tramos, key=lambda t: t.veterinario):
        por_dia = {}
        for tramo in del_vet:
            por_dia.setdefault(tramo.dia_semana, []).append(tramo)

        grupos = []                     # [primer día, último día, horario]
        for dia in sorted(por_dia):
            texto = _texto_tramos(por_dia[dia])
            if grupos and grupos[-1][1] == dia - 1 and grupos[-1][2] == texto:
                grupos[-1][1] = dia
            else:
                grupos.append([dia, dia, texto])

        resumen.append({
            'veterinario': vet,
            'nombre': vet.get_full_name() or vet.username,
            'lineas': [f'{_rango_dias(desde, hasta)} {texto}' for desde, hasta, texto in grupos],
            'sabado': 5 in por_dia,
            'urgencias': vet.pk in de_urgencias,
            'atiende_hoy': hoy in por_dia,
        })
    return resumen


def horas_libres(vet, fecha, excepto=None, desde=None):
    """Los tramos del profesional ese día y los bloques que siguen libres.

    `excepto` es la cita que se está reagendando (su propia hora cuenta como
    libre) y `desde`, una hora antes de la cual no se ofrece nada (hoy).
    """
    tramos = list(HorarioAtencion.objects.filter(veterinario=vet, dia_semana=fecha.weekday(), activo=True)
                  .order_by('hora_inicio'))
    tomadas = (Cita.objects.filter(veterinario=vet, fecha=fecha)
               .exclude(estado__in=ESTADOS_QUE_LIBERAN))
    if excepto:
        tomadas = tomadas.exclude(pk=excepto)
    tomadas = set(tomadas.values_list('hora', flat=True))

    libres = [b for b in BLOQUES
              if any(t.hora_inicio <= b < t.hora_fin for t in tramos)
              and b not in tomadas
              and (desde is None or b > desde)]
    return tramos, libres


@login_required
def disponibles(request):
    """Horas libres de un profesional en una fecha, para llenar la lista de horas.

    Solo entrega horas, nunca de quién son las citas: lo pueden consultar
    tanto el personal como los clientes desde su portal.
    """
    try:
        vet = veterinarios_con_horario().get(pk=int(request.GET['veterinario']))
        fecha = datetime.date.fromisoformat(request.GET['fecha'])
    except (KeyError, ValueError, User.DoesNotExist):
        return JsonResponse({'error': 'Elige un profesional y una fecha válidos.'}, status=400)

    excepto = request.GET.get('excepto', '')
    excepto = int(excepto) if excepto.isdigit() else None
    nombre = vet.get_full_name() or vet.username
    hoy = timezone.localdate()

    if fecha < hoy:
        return JsonResponse({'atiende': False, 'libres': [], 'mensaje': 'Esa fecha ya pasó: elige otra.'})

    # El cliente no puede pedir una hora de hoy que ya pasó; recepción sí registra las del momento.
    desde = timezone.localtime().time() if fecha == hoy and request.GET.get('futuras') else None
    tramos, libres = horas_libres(vet, fecha, excepto=excepto, desde=desde)

    if not tramos:
        dia = DIAS[fecha.weekday()]
        dias = dia if dia.endswith('s') else dia + 's'
        lineas = resumen_horarios(vet)
        atiende = '; '.join(lineas[0]['lineas']) if lineas else ''
        mensaje = f'{nombre} no atiende los {dias}. Atiende: {atiende}.'
    elif not libres:
        mensaje = f'{nombre} no tiene horas libres ese día. Prueba otra fecha u otro profesional.'
    else:
        cuantas = 'una hora libre' if len(libres) == 1 else f'{len(libres)} horas libres'
        mensaje = f'{nombre} atiende ese día de {_texto_tramos(tramos)}: quedan {cuantas}.'

    return JsonResponse({'atiende': bool(tramos), 'libres': [h.strftime('%H:%M') for h in libres],
                         'mensaje': mensaje})


@login_required
def horarios_semana(request):
    """Horarios del equipo: qué días y a qué horas atiende cada profesional."""
    from django.core.exceptions import PermissionDenied
    from django.shortcuts import render
    if not request.user.has_perm('citas.view_cita'):
        raise PermissionDenied

    tramos = list(HorarioAtencion.objects.filter(activo=True, veterinario__in=veterinarios_con_horario())
                  .select_related('veterinario').order_by('hora_inicio'))
    # El domingo solo aparece si alguien atiende ese día.
    dias = list(range(6)) + ([6] if any(t.dia_semana == 6 for t in tramos) else [])

    filas = []
    de_urgencias = urgencias_ids()
    for vet in veterinarios_con_horario():
        celdas = []
        for dia in dias:
            del_dia = [t for t in tramos if t.veterinario_id == vet.pk and t.dia_semana == dia]
            celdas.append(_texto_tramos(del_dia) if del_dia else '')
        filas.append({'nombre': vet.get_full_name() or vet.username, 'celdas': celdas, 'urgencias': vet.pk in de_urgencias})

    return render(request, 'citas/horarios_semana.html', {
        'seccion': 'horarios_semana',
        'dias': [DIAS_CORTOS[d] for d in dias],
        'hoy': timezone.localdate().weekday(),
        'filas': filas,
    })
