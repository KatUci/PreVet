"""Formularios del portal del tutor: crear la cuenta, mantener sus datos y pedir hora."""
import re

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone

from citas.forms import AgendarCitaForm
from mascotas.forms import ClienteForm
from mascotas.models import Cliente
from mascotas.rut import limpiar_rut, validar_rut
from usuarios.models import Perfil


def _digitos(telefono):
    return re.sub(r'\D', '', telefono or '')[-8:]


class RegistroForm(forms.Form):
    """Crea la cuenta de un cliente.

    Si el RUT ya está en la clínica, la cuenta se vincula a esa ficha solo si
    el correo o el teléfono coinciden con los registrados: así nadie puede
    apropiarse de la ficha de otra persona sabiendo solo su RUT.
    """

    rut = forms.CharField(label='RUT', max_length=12, widget=forms.TextInput(attrs={'placeholder': '12.345.678-5'}))
    nombres = forms.CharField(max_length=80)
    apellidos = forms.CharField(max_length=80)
    email = forms.EmailField(label='Correo')
    telefono = forms.CharField(label='Teléfono', max_length=20,
                               widget=forms.TextInput(attrs={'placeholder': '+56 9 1234 5678'}))
    password1 = forms.CharField(label='Contraseña', widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    password2 = forms.CharField(label='Repite la contraseña', widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    consentimiento = forms.BooleanField(
        label='Acepto que la clínica guarde y use mis datos para atender a mis mascotas y contactarme (Ley 19.628).')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cliente_existente = None

    def clean_rut(self):
        rut = self.cleaned_data['rut']
        validar_rut(rut)                     # lanza el error con el motivo (dígito verificador, formato)
        rut = limpiar_rut(rut)
        if User.objects.filter(username=rut).exists():
            raise forms.ValidationError('Ya existe una cuenta con este RUT. Inicia sesión.')
        return rut

    def clean_telefono(self):
        telefono = self.cleaned_data['telefono']
        if len(re.sub(r'\D', '', telefono)) < 8:
            raise forms.ValidationError('El teléfono parece incompleto.')
        return telefono

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Ya hay una cuenta con este correo.')
        return email

    def clean(self):
        datos = super().clean()
        p1, p2 = datos.get('password1'), datos.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'Las contraseñas no coinciden.')
        elif p1:
            try:
                validate_password(p1, User(username=datos.get('rut', ''), email=datos.get('email', ''),
                                           first_name=datos.get('nombres', '')))
            except forms.ValidationError as error:
                self.add_error('password1', error)

        rut = datos.get('rut')
        cliente = Cliente.objects.filter(rut=rut).first() if rut else None
        if cliente:
            if cliente.usuario_id:
                raise forms.ValidationError('Ya existe una cuenta para este RUT. Inicia sesión.')
            mismo_correo = cliente.email and cliente.email.lower() == (datos.get('email') or '')
            mismo_telefono = cliente.telefono and _digitos(cliente.telefono) == _digitos(datos.get('telefono'))
            if not (mismo_correo or mismo_telefono):
                raise forms.ValidationError(
                    'Tu RUT ya está registrado en la clínica, pero el correo y el teléfono no coinciden con los '
                    'que tenemos. Acércate a recepción o llámanos para actualizarlos.')
            self.cliente_existente = cliente
        return datos

    @transaction.atomic
    def save(self):
        d = self.cleaned_data
        usuario = User.objects.create_user(username=d['rut'], email=d['email'], password=d['password1'],
                                           first_name=d['nombres'], last_name=d['apellidos'])
        Perfil.objects.create(usuario=usuario, rol=Perfil.Rol.DUENO, telefono=d['telefono'])
        cliente = self.cliente_existente or Cliente(rut=d['rut'], nombres=d['nombres'], apellidos=d['apellidos'])
        cliente.usuario = usuario
        cliente.email = cliente.email or d['email']
        cliente.telefono = cliente.telefono or d['telefono']
        cliente.consentimiento_datos = True
        cliente.save()
        return usuario


class MisDatosForm(ClienteForm):
    """El cliente actualiza sus propios datos (el RUT no se cambia desde aquí)."""

    class Meta(ClienteForm.Meta):
        fields = ['nombres', 'apellidos', 'telefono', 'email', 'canal_preferido', 'direccion', 'comuna',
                  'region', 'contacto_emergencia', 'telefono_emergencia']

    def save(self, commit=True):
        cliente = super().save(commit)
        if cliente.usuario_id:
            User.objects.filter(pk=cliente.usuario_id).update(
                first_name=cliente.nombres, last_name=cliente.apellidos, email=cliente.email)
        return cliente


class PedirHoraForm(AgendarCitaForm):
    """El cliente pide hora desde Mi PreVet.

    Es la misma ficha que usa recepción (solo sus mascotas, solo horas en que
    el profesional atiende y que estén libres), más una regla: no puede pedir
    una hora de hoy que ya pasó.
    """

    def clean(self):
        datos = super().clean()
        fecha, hora = datos.get('fecha'), datos.get('hora')
        if fecha == timezone.localdate() and hora and hora <= timezone.localtime().time():
            self.add_error('hora', 'Esa hora ya pasó. Elige una más tarde.')
        return datos
