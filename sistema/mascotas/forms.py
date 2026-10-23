import re

from django import forms

from .models import Cliente, Especie, Mascota, Raza, Tenencia
from .rut import limpiar_rut


class ClienteForm(forms.ModelForm):
    """Registro de una persona que trae mascotas a la clínica."""

    class Meta:
        model = Cliente
        fields = ['rut', 'nombres', 'apellidos', 'telefono', 'email', 'canal_preferido',
                  'direccion', 'comuna', 'region', 'contacto_emergencia', 'telefono_emergencia',
                  'consentimiento_datos']
        labels = {'nombres': 'Nombres', 'apellidos': 'Apellidos', 'comuna': 'Comuna'}
        help_texts = {'consentimiento_datos': 'El cliente autoriza a la clínica a guardar y usar sus datos '
                                              'para atender a sus mascotas y contactarlo (Ley 19.628).'}
        widgets = {
            'rut': forms.TextInput(attrs={'placeholder': '12.345.678-5'}),
            'telefono': forms.TextInput(attrs={'placeholder': '+56 9 1234 5678'}),
            'telefono_emergencia': forms.TextInput(attrs={'placeholder': '+56 9 1234 5678'}),
            'comuna': forms.TextInput(attrs={'placeholder': 'Colina, Lampa, Quilicura…'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['region'].choices = [('', 'Elige la región')] + list(self.fields['region'].choices)[1:]
        # Si no se elige, se usa WhatsApp, que es lo habitual en la clínica.
        self.fields['canal_preferido'].required = False
        if not self.instance.pk:
            self.fields['region'].initial = 'Metropolitana'

    def clean_telefono_emergencia(self):
        telefono = self.cleaned_data.get('telefono_emergencia', '')
        if telefono and len(re.sub(r'\D', '', telefono)) < 8:
            raise forms.ValidationError('El teléfono de emergencia parece incompleto.')
        return telefono

    def clean(self):
        datos = super().clean()
        if datos.get('telefono_emergencia') and not datos.get('contacto_emergencia'):
            self.add_error('contacto_emergencia', 'Indica de quién es el teléfono de emergencia.')
        if not datos.get('canal_preferido'):
            datos['canal_preferido'] = 'whatsapp'
        if datos.get('canal_preferido') == 'correo' and not datos.get('email'):
            self.add_error('email', 'Si prefiere correo, hay que registrar su correo.')
        return datos

    def clean_rut(self):
        # Se limpia antes de comprobar si ya existe, para que 12.345.678-5
        # y 12345678-5 se reconozcan como el mismo cliente.
        rut = limpiar_rut(self.cleaned_data['rut'])
        repetido = Cliente.objects.filter(rut=rut).exclude(pk=self.instance.pk)
        if repetido.exists():
            raise forms.ValidationError('Ya hay un cliente registrado con este RUT.')
        return rut


class MascotaForm(forms.ModelForm):
    """Registra una mascota y la vincula al cliente.

    El tipo de mascota va primero: según el tipo elegido se muestran solo
    sus razas.
    """

    relacion = forms.ChoiceField(label='Relación del cliente con la mascota',
                                 choices=Tenencia.Relacion.choices,
                                 initial=Tenencia.Relacion.DUENO)
    foto = forms.ImageField(label='Foto (opcional)', required=False,
                            help_text='JPG, PNG o WEBP de hasta 10 MB. Se achica automáticamente.')

    def clean_foto(self):
        from .fotos import PESO_MAXIMO
        foto = self.cleaned_data.get('foto')
        if foto and foto.size > PESO_MAXIMO:
            raise forms.ValidationError('La foto pesa más de 10 MB. Elige una más liviana.')
        return foto

    class Meta:
        model = Mascota
        fields = ['especie', 'raza', 'nombre', 'sexo', 'fecha_nacimiento', 'color', 'tiene_microchip', 'microchip',
                  'peso_kg', 'esterilizada', 'alergias', 'condiciones', 'observaciones']
        labels = {
            'especie': 'Tipo de mascota',
            'raza': 'Raza',
            'nombre': 'Nombre',
            'fecha_nacimiento': 'Fecha de nacimiento',
            'microchip': 'Número de microchip',
            'tiene_microchip': '¿Tiene microchip?',
        }
        help_texts = {'fecha_nacimiento': 'Si no se sabe, déjala en blanco.'}
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'microchip': forms.TextInput(attrs={'inputmode': 'numeric', 'placeholder': '15 dígitos (opcional)'}),
            # Valores 'True'/'False' para que al editar quede marcada la opción guardada.
            'tiene_microchip': forms.RadioSelect(choices=[('False', 'No'), ('True', 'Sí')],
                                                 attrs={'class': 'opciones-radio'}),
            'peso_kg': forms.NumberInput(attrs={'step': '0.1', 'min': '0'}),
            'esterilizada': forms.NullBooleanSelect(),
            'alergias': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Medicamentos, alimentos… (si no tiene, déjalo en blanco)'}),
            'condiciones': forms.Textarea(attrs={'rows': 2}),
            'observaciones': forms.Textarea(attrs={'rows': 2}),
        }

    def clean_microchip(self):
        chip = re.sub(r'\s', '', self.cleaned_data.get('microchip', ''))
        if chip and (not chip.isdigit() or len(chip) != 15):
            raise forms.ValidationError('El microchip debe tener 15 dígitos.')
        if chip and Mascota.objects.filter(microchip=chip).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Ya hay otra mascota registrada con este microchip.')
        return chip

    def clean_peso_kg(self):
        peso = self.cleaned_data.get('peso_kg')
        if peso is not None and not 0 < peso <= 150:
            raise forms.ValidationError('Revisa el peso: debe ser mayor que 0 y menor que 150 kg.')
        return peso

    def clean_fecha_nacimiento(self):
        from django.utils import timezone
        fecha = self.cleaned_data.get('fecha_nacimiento')
        if fecha and fecha > timezone.localdate():
            raise forms.ValidationError('La fecha de nacimiento no puede ser futura.')
        return fecha

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['especie'].queryset = Especie.objects.order_by('nombre')
        self.fields['especie'].empty_label = 'Elige el tipo'
        self.fields['raza'].queryset = Raza.objects.select_related('especie')
        self.fields['raza'].empty_label = 'Sin raza o desconocida'
        self.fields['raza'].label_from_instance = lambda r: r.nombre
        self.fields['sexo'].choices = [('', 'Elige el sexo')] + list(Mascota.SEXOS)
        if not self.instance.pk:
            self.fields['tiene_microchip'].initial = 'False'

    def clean(self):
        datos = super().clean()
        especie, raza = datos.get('especie'), datos.get('raza')
        if especie and raza and raza.especie_id != especie.pk:
            self.add_error('raza', f'{raza.nombre} no es una raza de {especie.nombre.lower()}.')
        # Si dice que no tiene microchip, el número se borra; si escribió un número, tiene.
        if datos.get('tiene_microchip') is False:
            datos['microchip'] = ''
        elif datos.get('microchip'):
            datos['tiene_microchip'] = True
        return datos

    def razas_por_tipo(self):
        """Pares (id de raza, id de tipo) para que el navegador filtre la lista."""
        return list(self.fields['raza'].queryset.values_list('pk', 'especie_id'))


class MascotaEditarForm(MascotaForm):
    """Los mismos datos de la mascota, sin la relación ni la foto (se editan aparte)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        del self.fields['relacion']
        del self.fields['foto']
