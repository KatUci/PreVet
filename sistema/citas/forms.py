import datetime

from django import forms
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Atencion, Cita, HorarioAtencion, TipoAtencion

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


def veterinarios_con_horario():
    """Profesionales activos que tienen al menos un tramo de atención: a los demás no se les puede agendar."""
    return (User.objects.filter(perfil__rol='veterinario', is_active=True, horarios__activo=True)
            .distinct().order_by('first_name'))


def atiende_a(tramos, hora):
    """Si con estos tramos del día el profesional atiende a esa hora.

    La hora en que termina su último tramo del día también se puede agendar:
    es la última hora para tomar hora (con 15:00 a 19:00, la última es 19:00).
    Las horas de colación siguen cerradas (con 09:00 a 13:00 y 15:00 a 19:00,
    a las 13:00 no se agenda).
    """
    if not tramos:
        return False
    ultima = max(t.hora_fin for t in tramos)
    return hora == ultima or any(t.hora_inicio <= hora < t.hora_fin for t in tramos)


def validar_bloque(vet, fecha, hora, excepto=None):
    """Revisa que el profesional atienda a esa hora y que esté libre.

    Devuelve el mensaje de error, o None si se puede agendar. `excepto` es la
    cita que se está reagendando, para que no choque consigo misma.
    """
    if not (vet and fecha and hora):
        return None

    tramos = HorarioAtencion.objects.filter(veterinario=vet, dia_semana=fecha.weekday(),
                                            activo=True).order_by('hora_inicio')
    if not atiende_a(tramos, hora):
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


# Sábado y domingo la clínica atiende solo urgencias: las consultas, controles
# y exámenes se agendan de lunes a viernes. La excepción es la vacuna, si justo
# ese día le toca a la mascota su próxima dosis (según su carnet de vacunas).
DIAS_SOLO_URGENCIAS = (5, 6)


def solo_urgencias(tipo, fecha, mascota=None):
    """Devuelve el mensaje de error si se agenda algo que no corresponde en fin de semana."""
    if not (tipo and fecha) or fecha.weekday() not in DIAS_SOLO_URGENCIAS:
        return None
    nombre = tipo.nombre.lower()
    if 'urgencia' in nombre:
        return None
    if 'vacuna' in nombre and mascota and mascota.vacunas.filter(proxima_dosis=fecha).exists():
        return None
    return ('Los sábados y domingos solo se atienden urgencias, y vacunas cuando ese día le toca '
            'la próxima dosis a la mascota. Las consultas, controles y exámenes se agendan de lunes a viernes.')


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
        self.fields['veterinario'].queryset = veterinarios_con_horario()
        self.fields['veterinario'].empty_label = 'Elige al profesional'
        self.fields['veterinario'].label_from_instance = lambda u: u.get_full_name() or u.username
        # La atención sin hora no tiene fecha (SinHoraForm, más abajo).
        if 'fecha' in self.fields:
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
        # La atención sin hora no tiene fecha en el formulario: es hoy.
        fecha = datos.get('fecha') if 'fecha' in self.fields else timezone.localdate()
        error = solo_urgencias(datos.get('tipo_atencion'), fecha, datos.get('mascota'))
        if error:
            self.add_error('tipo_atencion', error)
        return datos

    def validate_unique(self):
        # La revisión de hora tomada ya se hizo arriba, con un mensaje claro.
        pass


def proximas_dosis(cliente):
    """{id de mascota: [fechas de su próxima dosis]}, para avisar en pantalla."""
    from mascotas.models import Vacuna
    dosis = {}
    for v in Vacuna.objects.filter(mascota__tenencias__cliente=cliente, proxima_dosis__gte=timezone.localdate()):
        dosis.setdefault(str(v.mascota_id), []).append(v.proxima_dosis.isoformat())
    return dosis


class SinHoraForm(AgendarCitaForm):
    """Atención sin hora: igual que agendar, pero sin elegir fecha ni hora,
    porque el paciente ya está en la clínica."""

    hora = None

    class Meta(AgendarCitaForm.Meta):
        fields = ['mascota', 'tipo_atencion', 'veterinario', 'notas']
        labels = dict(AgendarCitaForm.Meta.labels, notas='Motivo de la urgencia')


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
        # Un control o examen no se puede mover a un sábado o domingo.
        error = solo_urgencias(self.instance.tipo_atencion, datos.get('fecha'), self.instance.mascota)
        if error:
            self.add_error('fecha', error)
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


class AtencionForm(forms.ModelForm):
    """Lo que el veterinario registra al cerrar la atención."""

    documento = forms.FileField(
        label='Adjuntar receta o indicaciones (opcional)', required=False,
        help_text='PDF o Word de hasta 5 MB.',
        widget=forms.ClearableFileInput(attrs={'accept': '.pdf,.doc,.docx'}))

    class Meta:
        model = Atencion
        fields = ['motivo', 'diagnostico', 'tratamiento', 'peso_kg']
        widgets = {
            'motivo': forms.TextInput(attrs={'placeholder': 'Control anual, vómitos, cojera…'}),
            'diagnostico': forms.Textarea(attrs={'rows': 4}),
            'tratamiento': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Medicamentos, dosis, cuidados en casa, próximo control…'}),
            'peso_kg': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }

    def clean_documento(self):
        from .documentos import validar_documento
        archivo = self.cleaned_data.get('documento')
        return validar_documento(archivo) if archivo else None

    def clean_peso_kg(self):
        peso = self.cleaned_data.get('peso_kg')
        if peso is not None and not 0 < peso < 1000:
            raise forms.ValidationError('Revisa el peso: debe ser mayor que 0 y menor que 1000 kg.')
        return peso
