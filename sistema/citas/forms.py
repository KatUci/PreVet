import datetime

from django import forms
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Cita, HorarioAtencion, TipoAtencion

# Horas que se pueden elegir: cada media hora entre las 08:00 y las 19:30.
BLOQUES = [datetime.time(h, m) for h in range(8, 20) for m in (0, 30)]


class AgendarCitaForm(forms.ModelForm):
    """Agenda una hora para una de las mascotas del cliente."""

    hora = forms.TypedChoiceField(
        label='Hora',
        choices=[('', 'Elige la hora')] + [(b.strftime('%H:%M'), b.strftime('%H:%M')) for b in BLOQUES],
        coerce=lambda texto: datetime.datetime.strptime(texto, '%H:%M').time(),
    )

    class Meta:
        model = Cita
        fields = ['mascota', 'tipo_atencion', 'veterinario', 'fecha', 'hora', 'notas']
        labels = {
            'mascota': 'Mascota',
            'tipo_atencion': 'Tipo de atención',
            'veterinario': 'Profesional',
            'fecha': 'Fecha',
            'notas': 'Motivo o comentarios',
        }
        widgets = {
            'mascota': forms.RadioSelect,
            'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'notas': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Opcional'}),
        }

    def __init__(self, *args, cliente, **kwargs):
        # La cita nace a nombre del cliente: así el modelo puede comprobar
        # que la mascota elegida es de él.
        kwargs.setdefault('instance', Cita(cliente=cliente))
        super().__init__(*args, **kwargs)
        self.cliente = cliente

        self.fields['mascota'].queryset = (cliente.mascotas.filter(activo=True)
                                           .select_related('especie', 'raza')
                                           .order_by('especie__nombre', 'nombre'))
        self.fields['mascota'].empty_label = None
        self.fields['tipo_atencion'].queryset = TipoAtencion.objects.filter(activo=True)
        self.fields['tipo_atencion'].empty_label = 'Elige la atención'
        self.fields['veterinario'].queryset = (User.objects
                                               .filter(perfil__rol='veterinario', is_active=True)
                                               .order_by('first_name'))
        self.fields['veterinario'].empty_label = 'Elige al profesional'
        self.fields['veterinario'].label_from_instance = lambda u: u.get_full_name() or u.username
        self.fields['fecha'].widget.attrs['min'] = timezone.localdate().isoformat()

    def mascotas_por_tipo(self):
        """Las opciones de mascota agrupadas por tipo, para mostrar primero el tipo."""
        mascotas = {m.pk: m for m in self.fields['mascota'].queryset}
        grupos = {}
        for opcion in self['mascota']:
            mascota = mascotas[opcion.data['value'].value]
            grupos.setdefault(mascota.especie, []).append((opcion, mascota))
        return list(grupos.items())

    def clean_fecha(self):
        fecha = self.cleaned_data['fecha']
        if fecha < timezone.localdate():
            raise forms.ValidationError('No se puede agendar en una fecha que ya pasó.')
        return fecha

    def clean(self):
        datos = super().clean()
        vet, fecha, hora = datos.get('veterinario'), datos.get('fecha'), datos.get('hora')
        if not (vet and fecha and hora):
            return datos

        # ¿Atiende ese día y a esa hora?
        tramos = HorarioAtencion.objects.filter(veterinario=vet, dia_semana=fecha.weekday(),
                                                activo=True).order_by('hora_inicio')
        if not any(t.hora_inicio <= hora < t.hora_fin for t in tramos):
            nombre = vet.get_full_name() or vet.username
            if tramos:
                horario = ', '.join(f'{t.hora_inicio:%H:%M} a {t.hora_fin:%H:%M}' for t in tramos)
                mensaje = f'{nombre} atiende ese día de {horario}.'
            else:
                mensaje = f'{nombre} no atiende ese día de la semana.'
            self.add_error('hora', mensaje)
            return datos

        # ¿Está libre?
        if Cita.objects.filter(veterinario=vet, fecha=fecha, hora=hora).exists():
            self.add_error('hora', 'Esa hora ya está tomada con este profesional. Elige otra.')

        return datos

    def validate_unique(self):
        # La revisión de hora tomada ya se hizo arriba, con un mensaje claro.
        pass
