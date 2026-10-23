"""Calendario de citas: vistas por día, semana y mes, y las acciones sobre cada cita."""

import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import riesgo
from .contacto import enlace_whatsapp, guion_llamada, mensaje_segun_riesgo
from .forms import CancelarForm, ReagendarForm
from .models import Cita

# Los colores de cada estado están en prevet.css (clases ev-<estado>),
# para que cambien junto con el modo día o noche.


def _veterinarios():
    return (User.objects.filter(perfil__rol='veterinario', is_active=True)
            .order_by('first_name'))


def _volver(request, cita=None):
    """Vuelve al calendario en la misma vista y fecha desde donde se actuó."""
    destino = request.POST.get('next') or request.GET.get('next')
    if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        return redirect(destino)
    if cita:
        return redirect(f'/citas/calendario/?fecha={cita.fecha.isoformat()}')
    return redirect('calendario')


@login_required
@permission_required('citas.view_cita', raise_exception=True)
def calendario(request):
    # Cada veterinario parte viendo sus propias citas; los demás, todas.
    perfil = getattr(request.user, 'perfil', None)
    por_defecto = str(request.user.pk) if perfil and perfil.rol == 'veterinario' else ''

    return render(request, 'citas/calendario.html', {
        'seccion': 'calendario',
        'veterinarios': _veterinarios(),
        'vet_elegido': request.GET.get('veterinario', por_defecto),
        'fecha_inicial': request.GET.get('fecha', ''),
        'vista_inicial': request.GET.get('vista', ''),
    })


@login_required
@permission_required('citas.view_cita', raise_exception=True)
def eventos(request):
    """Las citas entre dos fechas, en el formato que entiende FullCalendar."""

    def fecha(param):
        texto = request.GET.get(param, '')[:10]
        try:
            return datetime.date.fromisoformat(texto)
        except ValueError:
            return None

    desde, hasta = fecha('start'), fecha('end')
    if not (desde and hasta) or (hasta - desde).days > 62:
        return JsonResponse({'error': 'Rango de fechas inválido.'}, status=400)

    citas = (Cita.objects.filter(fecha__gte=desde, fecha__lt=hasta)
             .select_related('mascota__especie', 'cliente', 'veterinario', 'tipo_atencion'))
    if request.GET.get('veterinario', '').isdigit():
        citas = citas.filter(veterinario_id=request.GET['veterinario'])

    # El riesgo se calcula una sola vez para todas las citas pendientes.
    stats = riesgo.estadisticas()
    resultado = []
    for c in citas:
        nivel = riesgo.puntuar(c, stats)[1] if c.estado == 'pendiente' else None
        alerta = '⚠ ' if nivel == 'alto' else ''
        resultado.append({
            'id': c.pk,
            'title': f'{alerta}{c.mascota.especie.emoji} {c.mascota.nombre} · {c.tipo_atencion.nombre}',
            'start': datetime.datetime.combine(c.fecha, c.hora).isoformat(),
            'end': datetime.datetime.combine(c.fecha, c.hora_termino).isoformat(),
            'classNames': [f'ev-{c.estado}'] + (['riesgo-alto'] if nivel == 'alto' else []),
            'extendedProps': {
                'mascota': c.mascota.nombre,
                'emoji': c.mascota.especie.emoji,
                'atencion': c.tipo_atencion.nombre,
                'cliente': c.cliente.nombre_completo,
                'profesional': c.veterinario.get_full_name(),
                'estado': c.get_estado_display(),
                'riesgo': nivel or '',
            },
        })
    return JsonResponse(resultado, safe=False)


@login_required
@permission_required('citas.view_cita', raise_exception=True)
def detalle(request, pk):
    """El panel lateral que se abre al hacer clic en una cita."""
    cita = get_object_or_404(
        Cita.objects.select_related('mascota__especie', 'mascota__raza', 'cliente',
                                    'veterinario', 'tipo_atencion', 'cancelada_por'), pk=pk)
    hoy = timezone.localdate()

    nivel = puntaje = detalle_riesgo = accion = None
    guion = []
    if cita.estado == 'pendiente':
        stats = riesgo.estadisticas()
        puntaje, nivel, accion, detalle_riesgo = riesgo.puntuar(cita, stats)
        guion = guion_llamada(cita, nivel, stats)

    return render(request, 'citas/_detalle.html', {
        'cita': cita,
        'hoy': hoy,
        'pendiente': cita.estado == 'pendiente',
        'ya_ocurrio': cita.fecha <= hoy,
        'es_hoy': cita.fecha == hoy,
        'nivel': nivel,
        'puntaje': puntaje,
        'detalle_riesgo': detalle_riesgo,
        'accion': accion,
        'whatsapp': _enlace_whatsapp(cita, nivel),
        'guion': guion,
        'duracion': cita.tipo_atencion.duracion_minutos,
        'form_cancelar': CancelarForm(),
    })


def _enlace_whatsapp(cita, nivel=None):
    """Enlace de WhatsApp con el mensaje listo para enviar.

    Si se conoce el riesgo de la cita, el mensaje se adapta a él (ver
    contacto.py); si no, es un recordatorio general.
    """
    if nivel:
        mensaje = mensaje_segun_riesgo(cita, nivel)
    else:
        mensaje = (f'Hola {cita.cliente.nombres}, te escribimos de la clínica para recordarte '
                   f'la hora de {cita.mascota.nombre} el {cita.fecha:%d/%m} a las {cita.hora:%H:%M}. '
                   f'¿Nos confirmas tu asistencia?')
    return enlace_whatsapp(cita.cliente.telefono, mensaje)


def _cita_pendiente(request, pk):
    cita = get_object_or_404(Cita, pk=pk)
    if cita.estado != 'pendiente':
        messages.error(request, 'Esa cita ya no está pendiente: no se puede cambiar.')
        return None, _volver(request, cita)
    return cita, None


@require_POST
@login_required
@permission_required('citas.change_cita', raise_exception=True)
def marcar_llegada(request, pk):
    cita, salida = _cita_pendiente(request, pk)
    if salida:
        return salida
    cita.hora_llegada = timezone.now()
    cita.save(update_fields=['hora_llegada'])
    messages.success(request, f'{cita.mascota.nombre} llegó a las {timezone.localtime(cita.hora_llegada):%H:%M}.')
    return _volver(request, cita)


@require_POST
@login_required
@permission_required('citas.change_cita', raise_exception=True)
def marcar_atendida(request, pk):
    cita, salida = _cita_pendiente(request, pk)
    if salida:
        return salida
    if cita.fecha > timezone.localdate():
        messages.error(request, 'Una cita futura todavía no se puede marcar como atendida.')
        return _volver(request, cita)
    cita.estado = 'completada'
    cita.save(update_fields=['estado'])
    messages.success(request, f'La atención de {cita.mascota.nombre} quedó cerrada.')
    return _volver(request, cita)


@require_POST
@login_required
@permission_required('citas.change_cita', raise_exception=True)
def cancelar(request, pk):
    cita, salida = _cita_pendiente(request, pk)
    if salida:
        return salida
    form = CancelarForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Para cancelar hay que elegir un motivo.')
        return _volver(request, cita)

    cita.estado = 'cancelada'
    cita.cancelada_por = request.user
    cita.fecha_cancelacion = timezone.now()
    cita.motivo_cancelacion = form.texto()
    cita.save(update_fields=['estado', 'cancelada_por', 'fecha_cancelacion', 'motivo_cancelacion'])
    messages.success(request, f'La cita de {cita.mascota.nombre} quedó cancelada y la hora está libre.')
    return _volver(request, cita)


@login_required
@permission_required('citas.change_cita', raise_exception=True)
def reagendar(request, pk):
    cita = get_object_or_404(Cita.objects.select_related('mascota', 'cliente'), pk=pk)
    if cita.estado != 'pendiente':
        messages.error(request, 'Solo se pueden reagendar las citas pendientes.')
        return _volver(request, cita)

    form = ReagendarForm(request.POST or None, instance=cita)
    if request.method == 'POST' and form.is_valid():
        cita = form.save()
        messages.success(request, f'{cita.mascota.nombre} quedó para el {cita.fecha:%d/%m/%Y} a las {cita.hora:%H:%M}.')
        return redirect(f'/citas/calendario/?fecha={cita.fecha.isoformat()}')

    return render(request, 'citas/reagendar.html', {'seccion': 'calendario', 'cita': cita, 'form': form})
