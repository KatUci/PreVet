"""Lista de espera (PV-REC-01): tutores que quieren una hora que hoy no está disponible.

Recepción los anota por día y, si lo piden, por profesional. La lista muestra
las horas libres de ese día, así que cuando una cita se cancela se ve al tiro
a quién ofrecerle el bloque, y desde ahí se agenda con un clic.
"""
from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .disponibilidad import horas_libres
from .forms import veterinarios_con_horario
from .models import EsperaHora, TipoAtencion


class EsperaForm(forms.ModelForm):
    class Meta:
        model = EsperaHora
        fields = ['mascota', 'fecha', 'veterinario', 'tipo_atencion', 'notas']
        labels = {'mascota': 'Mascota'}
        widgets = {'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')}

    def __init__(self, *args, cliente, **kwargs):
        # Queda a nombre del cliente: así el modelo revisa que la mascota sea suya.
        kwargs.setdefault('instance', EsperaHora(cliente=cliente))
        super().__init__(*args, **kwargs)
        self.fields['mascota'].queryset = cliente.mascotas.filter(activo=True).order_by('nombre')
        self.fields['mascota'].empty_label = 'Elige la mascota'
        self.fields['veterinario'].queryset = veterinarios_con_horario()
        self.fields['veterinario'].empty_label = 'Cualquier profesional'
        self.fields['veterinario'].label_from_instance = lambda u: u.get_full_name() or u.username
        self.fields['tipo_atencion'].queryset = TipoAtencion.objects.filter(activo=True)
        self.fields['tipo_atencion'].empty_label = 'Cualquiera'
        self.fields['fecha'].widget.attrs['min'] = timezone.localdate().isoformat()

    def clean_fecha(self):
        fecha = self.cleaned_data['fecha']
        if fecha < timezone.localdate():
            raise ValidationError('Ese día ya pasó.')
        return fecha


def esperando(fecha=None, veterinario=None):
    """Quienes siguen esperando, desde hoy. Con fecha y profesional, solo los que calzan con esa hora."""
    esperas = (EsperaHora.objects.filter(estado='esperando', fecha__gte=timezone.localdate())
               .select_related('cliente', 'mascota__especie', 'veterinario', 'tipo_atencion'))
    if fecha:
        esperas = esperas.filter(fecha=fecha)
    if veterinario:
        esperas = esperas.filter(Q(veterinario__isnull=True) | Q(veterinario=veterinario))
    return esperas


def opciones(espera):
    """Las horas libres de ese día con el profesional pedido o, si le da lo mismo, con cualquiera."""
    hoy = timezone.localdate()
    desde = timezone.localtime().time() if espera.fecha == hoy else None
    profesionales = [espera.veterinario] if espera.veterinario_id else veterinarios_con_horario()
    resultado = []
    for vet in profesionales:
        _, libres = horas_libres(vet, espera.fecha, desde=desde)
        if libres:
            resultado.append({
                'veterinario': vet,
                'libres': libres,
                'agendar': reverse('agendar') + '?' + urlencode({
                    'rut': espera.cliente.rut, 'espera': espera.pk, 'veterinario': vet.pk,
                    'fecha': espera.fecha.isoformat(), 'hora': libres[0].strftime('%H:%M')}),
            })
    return resultado


@login_required
@permission_required('citas.view_esperahora', raise_exception=True)
def listado(request):
    filas = [{'espera': e, 'opciones': opciones(e)} for e in esperando()]
    return render(request, 'citas/espera_listado.html', {
        'seccion': 'espera',
        'filas': filas,
        'con_horas': sum(1 for f in filas if f['opciones']),
    })


@login_required
@permission_required('citas.add_esperahora', raise_exception=True)
def anotar(request):
    """Igual que agendar: primero el cliente por su RUT, después la mascota y el día."""
    from .views import _buscar_cliente

    rut_escrito, cliente, error_rut = _buscar_cliente(request)

    form = None
    if cliente:
        inicial = {clave: request.GET[clave] for clave in ('fecha', 'veterinario') if request.GET.get(clave)}
        form = EsperaForm(request.POST or None, cliente=cliente, initial=inicial)
        if request.method == 'POST' and form.is_valid():
            espera = form.save(commit=False)
            espera.creada_por = request.user
            espera.save()
            messages.success(request, f'{espera.mascota.nombre} quedó en la lista de espera para el '
                                      f'{espera.fecha:%d/%m/%Y}. Si se libera una hora ese día, aparecerá aquí.')
            return redirect('lista_espera')

    return render(request, 'citas/espera_form.html', {
        'seccion': 'espera',
        'rut_escrito': rut_escrito,
        'error_rut': error_rut,
        'cliente': cliente,
        'form': form,
    })


@require_POST
@login_required
@permission_required('citas.change_esperahora', raise_exception=True)
def descartar(request, pk):
    espera = get_object_or_404(EsperaHora, pk=pk, estado='esperando')
    espera.estado = 'descartada'
    espera.save(update_fields=['estado'])
    messages.success(request, f'{espera.mascota.nombre} salió de la lista de espera.')
    return redirect('lista_espera')
