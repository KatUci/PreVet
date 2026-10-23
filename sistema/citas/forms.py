import datetime

from django import forms
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Cita, HorarioAtencion, TipoAtencion

# Horas que se pueden elegir: cada media hora entre las 08:00 y las 19:30.
BLOQUES = [datetime.time(h, m) for h in range(8, 20) for m in (0, 30)]



def campo_hora():
    """Lista de horas cada media hora; devuelve un objeto time al validar."""
    return forms.TypedChoiceField(
        label='Hora',
        choices=[('', 'Elige la hora')] + [(b.strftime('%H:%M'), b.strftime('%H:%M')) for b in BLOQUES],
        coerce=lambda texto: datetime.datetime.strptime(texto, '%H:%M').time(),
    )

# Estados que no ocupan la hora: si se cancela, el bloque queda libre.
ESTADOS_QUE_LIBERAN = ['cancelada']


def validar_bloque(vet, fecha, hora, excepto=None):
    """Revisa que el profesional atienda a esa hora y que esté libre.

    Devuelve el mensaje de error, o None si se puede agendar. `excepto` es la
    cita que se está reagendando, para que no choque consigo misma.
    """
    if not (vet and fecha and hora):
        return None

    tramos = HorarioAtencion.objects.filter(veterinario=vet, dia_semana=fecha.weekday(),
                                            activo=True).order_by('hora_inicio')
    if not any(t.hora_inicio <= hora < t.hora_fin for t in tramos):
        nombre = vet.get_full_name() or vet.username
        if tramos:
            horario = ', '.join(f'{t.hora_inicio:%H:%M} a {t.hora_fin:%H:%M}' for t in tramos)
            return f'{nombre} atiende ese día de {horario}.'
        return f'{nombre} no atiende ese día de la semana.'

    ocupada = (Cita.objects.filter(veterinario=vet, fecha=fecha, hora=hora)
               .exclude(estado__in=ESTADOS_QUE_LIBERAN))
    if excepto is not None:
        ocupada = ocupada.exclude(pk=excepto.pk)
    if ocupada.exists():
        return 'Esa hora ya está tomada con este profesional. Elige otra.'
    return None


class AgendarCitaForm(forms.ModelForm):
    """Agenda una hora para una de las mascotas del cliente."""

    hora = campo_hora()

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
        error = validar_bloque(datos.get('veterinario'), datos.get('fecha'), datos.get('hora'))
        if error:
            self.add_error('hora', error)
        return datos

    def validate_unique(self):
        # La revisión de hora tomada ya se hizo arriba, con un mensaje claro.
        pass


class ReagendarForm(forms.ModelForm):
    """Cambia el profesional, la fecha o la hora de una cita pendiente."""

    hora = campo_hora()

    class Meta:
        model = Cita
        fields = ['veterinario', 'fecha', 'hora']
        labels = {'veterinario': 'Profesional', 'fecha': 'Nueva fecha'}
        widgets = {'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['veterinario'].queryset = (User.objects
                                               .filter(perfil__rol='veterinario', is_active=True)
                                               .order_by('first_name'))
        self.fields['veterinario'].label_from_instance = lambda u: u.get_full_name() or u.username
        self.fields['fecha'].widget.attrs['min'] = timezone.localdate().isoformat()
        if self.instance.pk:
            self.initial['hora'] = self.instance.hora.strftime('%H:%M')

    def clean_fecha(self):
        fecha = self.cleaned_data['fecha']
        if fecha < timezone.localdate():
            raise forms.ValidationError('No se puede mover a una fecha que ya pasó.')
        return fecha

    def clean(self):
        datos = super().clean()
        error = validar_bloque(datos.get('veterinario'), datos.get('fecha'), datos.get('hora'),
                               excepto=self.instance)
        if error:
            self.add_error('hora', error)
        return datos

    def validate_unique(self):
        pass


class CancelarForm(forms.Form):
    """Cancelar no borra la cita: queda registrada, con motivo, para el modelo."""

    MOTIVOS = [
        ('', 'Elige el motivo'),
        ('El cliente avisó que no puede asistir', 'El cliente avisó que no puede asistir'),
        ('El cliente pidió cambiar la hora', 'El cliente pidió cambiar la hora'),
        ('El profesional no estará disponible', 'El profesional no estará disponible'),
        ('Se agendó por error', 'Se agendó por error'),
        ('Otro', 'Otro'),
    ]
    motivo = forms.ChoiceField(label='Motivo', choices=MOTIVOS)
    detalle = forms.CharField(label='Detalle (opcional)', max_length=150, required=False)

    def texto(self):
        motivo, detalle = self.cleaned_data['motivo'], self.cleaned_data['detalle']
        return f'{motivo}: {detalle}' if detalle else motivo
