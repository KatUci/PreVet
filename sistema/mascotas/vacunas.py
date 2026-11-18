"""Carnet de vacunas (PV-FIC-04).

El veterinario registra la vacuna que aplicó y, si corresponde, la fecha de
la próxima dosis. Recepción ve en "Vacunas por vencer" a quién hay que
recordarle la siguiente vacuna y le puede escribir por WhatsApp.
"""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from citas.contacto import armar_mensaje, enlace_whatsapp

from .forms import VacunaForm
from .models import Mascota, Vacuna

# Cuántos días hacia adelante (y hacia atrás, las atrasadas) muestra la lista.
DIAS_AVISO = 30

# Los tres avisos de una vacuna. No decimos que la vacuna "venció" o quedó
# inválida: eso depende del producto y lo decide el veterinario.
ESTADOS = {
    'al_dia': ('Al día', 'ok', 'Vacunación vigente.'),
    'proxima': ('Próxima vacuna', 'warn', 'Se acerca la fecha de vacunación.'),
    'atrasada': ('Atrasada', 'mal', 'La fecha programada ya pasó. Contactar al veterinario para revisar el calendario.'),
}


def estado_vacuna(fecha):
    """Aviso según la fecha de la próxima dosis: al día, próxima (dentro de 30 días) o atrasada."""
    hoy = timezone.localdate()
    if fecha < hoy:
        clave = 'atrasada'
    elif fecha <= hoy + timedelta(days=DIAS_AVISO):
        clave = 'proxima'
    else:
        clave = 'al_dia'
    nombre, color, aviso = ESTADOS[clave]
    return {'clave': clave, 'nombre': nombre, 'color': color, 'aviso': aviso}


def ultimas_dosis(vacunas):
    """De cada vacuna de cada mascota deja solo la última que se le puso.

    Si Bruno tiene dos Antirrábicas, la próxima dosis que vale es la de la más
    nueva (la vieja ya quedó cubierta). Devuelve las que tienen próxima dosis,
    ordenadas por fecha y con su aviso en `vacuna.estado`.
    """
    ultimas = {}
    for v in vacunas.select_related('mascota__especie').order_by('fecha_aplicacion', 'pk'):
        ultimas[(v.mascota_id, v.nombre.strip().lower())] = v
    lista = sorted((v for v in ultimas.values() if v.proxima_dosis), key=lambda v: v.proxima_dosis)
    for v in lista:
        v.estado = estado_vacuna(v.proxima_dosis)
    return lista


MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
         'septiembre', 'octubre', 'noviembre', 'diciembre']


def calendario_vacunas(request, vacunas, citas):
    """Arma un mes del calendario con las próximas dosis y las citas de vacunación.

    `vacunas` y `citas` vienen ya filtradas según quién mira (el cliente ve solo
    sus mascotas; el personal, todas). El mes se elige con ?mes=2026-11.
    """
    import calendar
    import datetime

    hoy = timezone.localdate()
    try:
        anio, mes = (int(x) for x in request.GET.get('mes', '').split('-'))
        primero = datetime.date(anio, mes, 1)
    except ValueError:
        primero = hoy.replace(day=1)
    semanas = calendar.Calendar(firstweekday=0).monthdatescalendar(primero.year, primero.month)
    desde, hasta = semanas[0][0], semanas[-1][-1]

    por_dia = {}
    for v in ultimas_dosis(vacunas):
        if desde <= v.proxima_dosis <= hasta:
            por_dia.setdefault(v.proxima_dosis, []).append(
                {'tipo': v.estado['color'], 'aviso': v.estado['nombre'],
                 'texto': f'{v.mascota.nombre} · {v.nombre}', 'emoji': v.mascota.especie.emoji})
    for c in citas.filter(fecha__range=(desde, hasta)).select_related('mascota__especie'):
        por_dia.setdefault(c.fecha, []).append(
            {'tipo': 'cita', 'aviso': 'Hora de vacunación agendada',
             'texto': f'{c.mascota.nombre} · {c.hora:%H:%M}', 'emoji': c.mascota.especie.emoji})

    anterior = (primero - datetime.timedelta(days=1)).replace(day=1)
    siguiente = (primero + datetime.timedelta(days=32)).replace(day=1)
    return {
        'titulo': f'{MESES[primero.month - 1].capitalize()} {primero.year}',
        'anterior': f'{anterior:%Y-%m}', 'siguiente': f'{siguiente:%Y-%m}',
        'dias_semana': ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'],
        'semanas': [[{'fecha': d, 'del_mes': d.month == primero.month, 'hoy': d == hoy,
                      'finde': d.weekday() >= 5, 'cosas': por_dia.get(d, [])} for d in semana]
                    for semana in semanas],
    }


@login_required
@permission_required('mascotas.add_vacuna', raise_exception=True)
def registrar(request, pk):
    """Agrega una vacuna al carnet de la mascota."""
    mascota = get_object_or_404(Mascota, pk=pk)
    form = VacunaForm(request.POST or None, initial={'fecha_aplicacion': timezone.localdate()})

    if request.method == 'POST' and form.is_valid():
        vacuna = form.save(commit=False)
        vacuna.mascota = mascota
        vacuna.registrada_por = request.user
        vacuna.save()
        messages.success(request, f'La vacuna {vacuna.nombre} quedó en el carnet de {mascota.nombre}.')
        return redirect('mascota_ficha', pk=mascota.pk)

    return render(request, 'mascotas/vacuna_form.html', {
        'seccion': 'mascotas',
        'mascota': mascota,
        'form': form,
    })


@login_required
@permission_required('mascotas.view_vacuna', raise_exception=True)
def por_vencer(request):
    """Próximas dosis de los siguientes 30 días y las que ya se atrasaron."""
    hoy = timezone.localdate()
    todas = Vacuna.objects.filter(mascota__activo=True).prefetch_related('mascota__tenencias__cliente')

    filas = []
    for vacuna in ultimas_dosis(todas):
        # Solo las de los próximos 30 días y las atrasadas de los últimos 30.
        if abs((vacuna.proxima_dosis - hoy).days) > DIAS_AVISO:
            continue
        tutor = vacuna.mascota.responsable
        whatsapp = None
        if tutor:
            mensaje = armar_mensaje('vacuna', {
                'tutor': tutor.nombres, 'mascota': vacuna.mascota.nombre,
                'vacuna': vacuna.nombre, 'fecha': vacuna.proxima_dosis.strftime('%d/%m/%Y')})
            whatsapp = enlace_whatsapp(tutor.telefono, mensaje)
        filas.append({
            'vacuna': vacuna,
            'tutor': tutor,
            'whatsapp': whatsapp,
            'atrasada': vacuna.proxima_dosis < hoy,
            'estado': vacuna.estado,
        })

    from citas.models import Cita
    calendario = calendario_vacunas(
        request,
        Vacuna.objects.filter(mascota__activo=True),
        Cita.objects.filter(estado='pendiente', tipo_atencion__nombre__icontains='vacuna'))

    return render(request, 'mascotas/vacunas_por_vencer.html', {
        'seccion': 'vacunas',
        'filas': filas,
        'dias': DIAS_AVISO,
        'calendario': calendario,
        'estados': ESTADOS.values(),
    })
