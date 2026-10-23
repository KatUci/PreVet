import datetime
import re

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from mascotas.models import Cliente
from mascotas.rut import limpiar_rut, validar_rut

from .forms import AgendarCitaForm
from .models import Cita, TipoAtencion


POR_PAGINA = (20, 50, 100)


def _filtrar_citas(g):
    """Aplica los filtros del listado (g = parámetros de la dirección).

    Lo usan la pantalla, los conteos por estado y la exportación a Excel.
    """
    filtros = {
        'q': g.get('q', '').strip(),
        'estado': g.get('estado', ''),
        'veterinario': g.get('veterinario', ''),
        'desde': g.get('desde', ''),
        'hasta': g.get('hasta', ''),
        'orden': g.get('orden', 'recientes'),
    }

    citas = Cita.objects.select_related('mascota__especie', 'cliente', 'veterinario', 'tipo_atencion')

    # Cada palabra debe aparecer en la mascota, el cliente, su RUT o teléfono,
    # o el profesional: así "javiera luna" encuentra a Luna de Javiera Pérez.
    for palabra in filtros['q'].split():
        condicion = (Q(mascota__nombre__icontains=palabra)
                     | Q(cliente__nombres__icontains=palabra)
                     | Q(cliente__apellidos__icontains=palabra)
                     | Q(cliente__telefono__icontains=palabra)
                     | Q(veterinario__first_name__icontains=palabra)
                     | Q(veterinario__last_name__icontains=palabra))
        # RUT con o sin puntos, guion o dígito verificador: 15.234.871-1 o 15234871.
        digitos = re.sub(r'[^0-9kK]', '', palabra)
        if len(digitos) >= 4 and digitos[:-1].isdigit():
            condicion |= (Q(cliente__rut__startswith=limpiar_rut(digitos))
                          | Q(cliente__rut__startswith=digitos))
        citas = citas.filter(condicion)

    if filtros['estado'] in dict(Cita.ESTADOS):
        citas = citas.filter(estado=filtros['estado'])
    if filtros['veterinario'].isdigit():
        citas = citas.filter(veterinario_id=filtros['veterinario'])
    for campo, condicion in (('desde', 'fecha__gte'), ('hasta', 'fecha__lte')):
        try:
            citas = citas.filter(**{condicion: datetime.date.fromisoformat(filtros[campo])})
        except ValueError:
            filtros[campo] = ''

    if filtros['orden'] == 'antiguas':
        citas = citas.order_by('fecha', 'hora')
    else:
        filtros['orden'] = 'recientes'
        citas = citas.order_by('-fecha', '-hora')
    return citas, filtros


@login_required
@permission_required('citas.view_cita', raise_exception=True)
def listado(request):
    """Listado de citas con buscador, filtros, paginador y exportación."""

    citas, filtros = _filtrar_citas(request.GET)
    hoy = timezone.localdate()

    try:
        por_pagina = int(request.GET.get('por_pagina', POR_PAGINA[0]))
    except ValueError:
        por_pagina = POR_PAGINA[0]
    if por_pagina not in POR_PAGINA:
        por_pagina = POR_PAGINA[0]

    pagina = Paginator(citas, por_pagina).get_page(request.GET.get('pagina'))

    # La dirección actual sin la página, para que el paginador no pierda los filtros.
    parametros = request.GET.copy()
    parametros.pop('pagina', None)
    sin_estado = parametros.copy()
    sin_estado.pop('estado', None)

    # Conteo por estado según los demás filtros, para los botones de estado.
    sin_estado_citas, _ = _filtrar_citas(sin_estado)
    conteos = dict(sin_estado_citas.order_by().values_list('estado').annotate(n=Count('id')))
    estados = [{'valor': v, 'etiqueta': e, 'conteo': conteos.get(v, 0)} for v, e in Cita.ESTADOS]

    manana = hoy + datetime.timedelta(days=1)
    return render(request, 'citas/listado.html', {
        'seccion': 'citas',
        'pagina': pagina,
        'rango_paginas': pagina.paginator.get_elided_page_range(pagina.number, on_each_side=2, on_ends=1),
        'total': pagina.paginator.count,
        'total_general': sum(conteos.values()),
        'filtros': filtros,
        'estados': estados,
        'veterinarios': User.objects.filter(perfil__rol='veterinario').order_by('first_name'),
        'qs': parametros.urlencode(),
        'qs_sin_estado': sin_estado.urlencode(),
        'por_pagina': por_pagina,
        'opciones_por_pagina': POR_PAGINA,
        'hay_filtros': any(filtros[k] for k in ('q', 'estado', 'veterinario', 'desde', 'hasta')),
        'atajos': [
            ('Hoy', hoy, hoy),
            ('Mañana', manana, manana),
            ('Próximos 7 días', hoy, hoy + datetime.timedelta(days=6)),
            ('Últimos 30 días', hoy - datetime.timedelta(days=30), hoy),
        ],
        'hoy': hoy,
    })


def texto_seguro(hoja):
    """Evita que un texto que empieza con "=" se guarde como fórmula en el Excel.

    Un nombre o motivo escrito como "=HIPERVINCULO(...)" se ejecutaría al abrir
    el archivo; así queda como texto común.
    """
    for fila in hoja.iter_rows(min_row=2):
        for celda in fila:
            if isinstance(celda.value, str) and celda.value.startswith('='):
                celda.data_type = 's'


@login_required
# Exportar entrega RUT y teléfonos de muchos clientes: solo quien agenda
# (recepción y administración), no todo el que puede ver citas.
@permission_required('citas.add_cita', raise_exception=True)
def exportar(request):
    """Descarga en Excel las citas que se están viendo, con los mismos filtros."""

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    citas, _ = _filtrar_citas(request.GET)

    libro = Workbook()
    hoja = libro.active
    hoja.title = 'Citas'
    columnas = [('Fecha', 12), ('Hora', 8), ('Mascota', 16), ('Tipo', 10), ('Cliente', 26), ('RUT', 14),
                ('Teléfono', 15), ('Atención', 22), ('Profesional', 24), ('Estado', 13),
                ('Llegada', 9), ('Motivo de cancelación', 30), ('Valor ($)', 11)]
    hoja.append([c for c, _ in columnas])
    for celda in hoja[1]:
        celda.font = Font(bold=True, color='FFFFFF')
        celda.fill = PatternFill('solid', fgColor='2B2160')
        celda.alignment = Alignment(vertical='center')
    for i, (_, ancho) in enumerate(columnas, start=1):
        hoja.column_dimensions[get_column_letter(i)].width = ancho

    for c in citas:
        llegada = timezone.localtime(c.hora_llegada).strftime('%H:%M') if c.hora_llegada else ''
        hoja.append([c.fecha, c.hora.strftime('%H:%M'), c.mascota.nombre, c.mascota.especie.nombre,
                     c.cliente.nombre_completo, c.cliente.rut_formateado, c.cliente.telefono,
                     c.tipo_atencion.nombre, c.veterinario.get_full_name(), c.get_estado_display(),
                     llegada, c.motivo_cancelacion, c.tipo_atencion.precio])
    for fila in hoja.iter_rows(min_row=2):
        fila[0].number_format = 'DD-MM-YYYY'
        fila[12].number_format = '#,##0'
    texto_seguro(hoja)
    hoja.freeze_panes = 'A2'
    hoja.auto_filter.ref = hoja.dimensions

    respuesta = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    nombre = f'citas_prevet_{timezone.localdate():%Y-%m-%d}.xlsx'
    respuesta['Content-Disposition'] = f'attachment; filename="{nombre}"'
    libro.save(respuesta)
    return respuesta


@login_required
@permission_required('citas.change_cita', raise_exception=True)
def marcar_no_asistio(request, pk):
    """Registra que el tutor no se presentó a su hora."""

    if request.method != 'POST':
        return redirect('citas')

    cita = get_object_or_404(Cita, pk=pk)
    volver = request.META.get('HTTP_REFERER', '/citas/')
    if cita.estado != 'pendiente' or cita.fecha > timezone.localdate():
        messages.error(request, 'Solo se puede marcar la inasistencia de una cita pendiente de hoy o de antes.')
        return redirect(volver)

    cita.estado = 'no_asistio'
    cita.fecha_marcada_no_asistio = timezone.now()
    cita.save()

    messages.success(
        request,
        f'{cita.mascota.nombre} quedó registrada como inasistencia. '
        f'Se perdieron ${cita.tipo_atencion.precio:,}'.replace(',', '.')
    )
    return redirect(volver)

@login_required
@permission_required('citas.add_cita', raise_exception=True)
def agendar(request):
    """Agendar una hora: primero se busca al cliente por RUT, después se
    elige una de sus mascotas y el resto de los datos de la cita."""

    rut_escrito = request.GET.get('rut', '').strip()
    cliente, error_rut = None, None

    if rut_escrito:
        try:
            validar_rut(rut_escrito)
        except ValidationError as error:
            error_rut = error.messages[0]
        else:
            cliente = Cliente.objects.filter(rut=limpiar_rut(rut_escrito), activo=True).first()

    form = None
    if cliente:
        form = AgendarCitaForm(request.POST or None, cliente=cliente)
        if request.method == 'POST' and form.is_valid():
            cita = form.save()
            messages.success(
                request,
                f'Hora agendada: {cita.mascota.nombre} el {cita.fecha:%d/%m/%Y} a las '
                f'{cita.hora:%H:%M} con {cita.veterinario.get_full_name()}.')
            return redirect('citas')

    return render(request, 'citas/agendar.html', {
        'seccion': 'citas',
        'rut_escrito': rut_escrito,
        'rut_limpio': limpiar_rut(rut_escrito),
        'error_rut': error_rut,
        'cliente': cliente,
        'form': form,
    })


class EditarCitaForm(forms.ModelForm):
    """Lo que se puede corregir de una cita pendiente sin moverla de hora."""

    class Meta:
        model = Cita
        fields = ['tipo_atencion', 'notas']
        labels = {'tipo_atencion': 'Tipo de atención', 'notas': 'Motivo o comentarios'}
        widgets = {'notas': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo_atencion'].queryset = TipoAtencion.objects.filter(activo=True).order_by('nombre')

    def _update_errors(self, errors):
        # La cita valida campos que este formulario no muestra (por ejemplo,
        # el cliente): esos errores se muestran arriba del formulario.
        from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
        if hasattr(errors, 'error_dict'):
            errors = ValidationError({(campo if campo in self.fields else NON_FIELD_ERRORS): lista
                                      for campo, lista in errors.error_dict.items()})
        super()._update_errors(errors)


@login_required
@permission_required('citas.change_cita', raise_exception=True)
def editar(request, pk):
    cita = get_object_or_404(Cita.objects.select_related('mascota', 'cliente'), pk=pk)
    if cita.estado != 'pendiente':
        messages.error(request, 'Solo se pueden editar citas pendientes.')
        return redirect('citas')
    form = EditarCitaForm(request.POST or None, instance=cita)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Se guardaron los cambios de la cita de {cita.mascota.nombre}.')
        return redirect(f'/citas/calendario/?vista=timeGridDay&fecha={cita.fecha.isoformat()}')
    from core import crud
    return crud.formulario(
        request, form=form, seccion='citas', titulo=f'Editar la cita de {cita.mascota.nombre}',
        volver=f'/citas/calendario/?vista=timeGridDay&fecha={cita.fecha.isoformat()}', mensaje='',
        ayuda=f'{cita.fecha:%d/%m/%Y} a las {cita.hora:%H:%M} con {cita.cliente.nombre_completo}. '
              f'Para cambiar el día, la hora o el profesional, usa «Reagendar».',
        migas=[('Citas', '/citas/'), ('Editar', None)])
