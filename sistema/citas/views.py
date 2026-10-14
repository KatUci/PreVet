from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.utils import timezone

from mascotas.models import Cliente
from mascotas.rut import limpiar_rut, validar_rut

from .forms import AgendarCitaForm
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
