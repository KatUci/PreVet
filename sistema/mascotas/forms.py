from django import forms

from .models import Cliente, Especie, Mascota, Raza, Tenencia
from .rut import limpiar_rut


class ClienteForm(forms.ModelForm):
    """Registro de una persona que trae mascotas a la clínica."""

    class Meta:
        model = Cliente
        fields = ['rut', 'nombres', 'apellidos', 'telefono', 'email', 'direccion']
        labels = {'nombres': 'Nombres', 'apellidos': 'Apellidos'}
        widgets = {
            'rut': forms.TextInput(attrs={'placeholder': '12.345.678-5'}),
            'telefono': forms.TextInput(attrs={'placeholder': '+56 9 1234 5678'}),
        }

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

    class Meta:
        model = Mascota
        fields = ['especie', 'raza', 'nombre', 'sexo', 'fecha_nacimiento']
        labels = {
            'especie': 'Tipo de mascota',
            'raza': 'Raza',
            'nombre': 'Nombre',
            'fecha_nacimiento': 'Fecha de nacimiento',
        }
        help_texts = {'fecha_nacimiento': 'Si no se sabe, déjala en blanco.'}
        widgets = {'fecha_nacimiento': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['especie'].queryset = Especie.objects.order_by('nombre')
        self.fields['especie'].empty_label = 'Elige el tipo'
        self.fields['raza'].queryset = Raza.objects.select_related('especie')
        self.fields['raza'].empty_label = 'Sin raza o desconocida'
        self.fields['raza'].label_from_instance = lambda r: r.nombre
        self.fields['sexo'].choices = [('', 'Elige el sexo')] + list(Mascota.SEXOS)

    def clean(self):
        datos = super().clean()
        especie, raza = datos.get('especie'), datos.get('raza')
        if especie and raza and raza.especie_id != especie.pk:
            self.add_error('raza', f'{raza.nombre} no es una raza de {especie.nombre.lower()}.')
        return datos

    def razas_por_tipo(self):
        """Pares (id de raza, id de tipo) para que el navegador filtre la lista."""
        return list(self.fields['raza'].queryset.values_list('pk', 'especie_id'))
