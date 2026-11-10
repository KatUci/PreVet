"""Cobro de las atenciones (PV-PAG-01) y lo que entra a la clínica (PV-PAG-02).

Cuando la mascota queda "Lista para salir", recepción ve cuánto debe pagar el
cliente (el precio del tipo de atención, que se puede ajustar si se cobró algo
más) y registra el pago. Cada pago deja un comprobante que el cliente también
ve en Mi PreVet.
"""
import datetime

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .calendario import _volver
from .models import Cita, Pago


class PagoForm(forms.ModelForm):
    class Meta:
        model = Pago
        fields = ['monto', 'medio', 'detalle']
        widgets = {'monto': forms.NumberInput(attrs={'min': '0', 'step': '1'}),
                   'medio': forms.RadioSelect}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['medio'].choices = Pago.MEDIOS     # sin la opción vacía "---------"

    def clean_monto(self):
        monto = self.cleaned_data['monto']
        if monto <= 0:
            raise forms.ValidationError('El monto debe ser mayor que cero.')
        return monto


@login_required
@permission_required('citas.add_pago', raise_exception=True)
def cobrar(request, pk):
    cita = get_object_or_404(Cita.objects.select_related('mascota__especie', 'cliente', 'tipo_atencion',
                                                         'veterinario'), pk=pk)
    volver = _volver(request, cita).url
    if cita.estado != 'completada':
        messages.error(request, 'Solo se cobra una atención ya realizada.')
        return redirect(volver)
    if Pago.objects.filter(cita=cita).exists():
        messages.error(request, 'Esta atención ya está pagada.')
        return redirect(volver)

    # El valor a pagar parte en el precio del tipo de atención.
    form = PagoForm(request.POST or None, initial={'monto': cita.tipo_atencion.precio, 'medio': 'efectivo'})
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            # Se bloquea la cita para que dos personas no la cobren a la vez.
            cita = Cita.objects.select_for_update().get(pk=cita.pk)
            if Pago.objects.filter(cita=cita).exists():
                messages.error(request, 'Otra persona ya registró este pago.')
                return redirect(volver)
            pago = form.save(commit=False)
            pago.cita = cita
            pago.cobrado_por = request.user
            pago.save()
            # Al pagar, la mascota se va de la clínica.
            if not cita.hora_salida:
                cita.hora_salida = timezone.now()
                cita.save(update_fields=['hora_salida'])
        messages.success(request, f'Pago de {pago.monto_txt} registrado. Comprobante N° {pago.numero}.')
        return redirect('comprobante', pago.pk)

    return render(request, 'citas/cobrar.html', {
        'seccion': 'hoy',
        'cita': cita,
        'form': form,
        'volver': volver,
    })


@login_required
@permission_required('citas.view_pago', raise_exception=True)
def comprobante(request, pk):
    pago = get_object_or_404(Pago.objects.select_related(
        'cita__mascota__especie', 'cita__cliente', 'cita__tipo_atencion', 'cita__veterinario', 'cobrado_por'), pk=pk)
    return render(request, 'citas/comprobante.html', {'seccion': 'pagos', 'pago': pago, 'volver': '/citas/pagos/'})


@login_required
@permission_required('citas.view_pago', raise_exception=True)
def listado(request):
    """Lo que entra a la clínica: los pagos entre dos fechas, con el total."""
    hoy = timezone.localdate()

    def fecha(param, por_defecto):
        try:
            return datetime.date.fromisoformat(request.GET.get(param, ''))
        except ValueError:
            return por_defecto

    desde = fecha('desde', hoy.replace(day=1))      # por defecto, el mes actual
    hasta = fecha('hasta', hoy)
    pagos = (Pago.objects.filter(fecha__date__gte=desde, fecha__date__lte=hasta)
             .select_related('cita__mascota', 'cita__cliente', 'cita__tipo_atencion', 'cobrado_por'))
    total = pagos.aggregate(total=Sum('monto'))['total'] or 0
    medios = dict(Pago.MEDIOS)
    por_medio = [{'medio': medios[fila['medio']], 'total': fila['total'], 'cantidad': fila['cantidad']}
                 for fila in pagos.order_by().values('medio').annotate(total=Sum('monto'), cantidad=Count('id'))]

    return render(request, 'citas/pagos.html', {
        'seccion': 'pagos',
        'pagos': pagos,
        'total': total,
        'por_medio': por_medio,
        'desde': desde,
        'hasta': hasta,
        'hoy_total': Pago.objects.filter(fecha__date=hoy).aggregate(t=Sum('monto'))['t'] or 0,
    })
