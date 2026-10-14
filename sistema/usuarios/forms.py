from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.models import Group, Permission, User

from .models import Perfil

ROLES_PERSONAL = [(valor, etiqueta) for valor, etiqueta in Perfil.Rol.choices
                  if valor in Perfil.ROLES_PERSONAL]

# Cómo se muestra cada acción de un permiso de Django.
ACCIONES = {'view': 'Ver', 'add': 'Agregar', 'change': 'Modificar', 'delete': 'Eliminar'}
ORDEN_ACCIONES = ['view', 'add', 'change', 'delete']

# Aplicaciones de PreVet cuyos permisos se pueden repartir en grupos.
APPS_CON_PERMISOS = ['citas', 'mascotas', 'usuarios']


class PersonalForm(forms.ModelForm):
    """Crea o edita a una persona del equipo: su usuario y su perfil."""

    rol = forms.ChoiceField(choices=ROLES_PERSONAL)
    telefono = forms.CharField(label='Teléfono', max_length=20, required=False)
    direccion = forms.CharField(label='Dirección', max_length=200, required=False)

    password1 = forms.CharField(label='Contraseña', required=False,
                                widget=forms.PasswordInput(render_value=False))
    password2 = forms.CharField(label='Repite la contraseña', required=False,
                                widget=forms.PasswordInput(render_value=False))

    groups = forms.ModelMultipleChoiceField(
        label='Grupos de permisos',
        queryset=Group.objects.order_by('name'),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'is_active', 'groups']
        labels = {
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'username': 'Usuario',
            'email': 'Correo',
            'is_active': 'Puede entrar al sistema',
        }
        help_texts = {
            'username': 'Con este nombre inicia sesión. Sin espacios.',
            'is_active': 'Si lo desmarcas, la persona deja de poder entrar, '
                         'pero su historial de citas se conserva.',
        }

    def __init__(self, *args, editor=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Quién está usando el formulario, para no dejarlo quitarse el acceso.
        self.editor = editor
        self.es_nuevo = self.instance.pk is None

        self.fields['first_name'].required = True
        self.fields['last_name'].required = True

        if self.es_nuevo:
            self.fields['password1'].required = True
            self.fields['password2'].required = True
            self.fields['groups'].help_text = (
                'Si no eliges ninguno, recibe el grupo que corresponde a su rol.')
        else:
            self.fields['password1'].label = 'Nueva contraseña'
            self.fields['password1'].help_text = 'Déjala en blanco para no cambiarla.'
            perfil = getattr(self.instance, 'perfil', None)
            if perfil is not None:
                self.fields['rol'].initial = perfil.rol
                self.fields['telefono'].initial = perfil.telefono
                self.fields['direccion'].initial = perfil.direccion

    def clean(self):
        datos = super().clean()
        p1, p2 = datos.get('password1'), datos.get('password2')

        if p1 or p2:
            if p1 != p2:
                self.add_error('password2', 'Las contraseñas no coinciden.')
            else:
                try:
                    # Aplica las reglas de settings.AUTH_PASSWORD_VALIDATORS:
                    # largo mínimo, que no sea común, que no se parezca al usuario...
                    password_validation.validate_password(p1, self.instance)
                except forms.ValidationError as error:
                    self.add_error('password1', error)

        # Nadie puede dejarse fuera a sí mismo por error.
        if self.editor is not None and self.instance.pk == self.editor.pk:
            if not datos.get('is_active', True):
                self.add_error('is_active', 'No puedes quitarle el acceso a tu propia cuenta.')

            perfil = getattr(self.editor, 'perfil', None)
            admin_solo_por_rol = (perfil is not None
                                  and perfil.rol == Perfil.Rol.ADMINISTRADOR
                                  and not perfil.es_administrador
                                  and not self.editor.is_superuser)
            if admin_solo_por_rol and datos.get('rol') != Perfil.Rol.ADMINISTRADOR:
                self.add_error('rol', 'No puedes quitarte el rol de administrador.')

        return datos

    def save(self, commit=True):
        user = super().save(commit=False)
        rol = self.cleaned_data['rol']

        if self.cleaned_data.get('password1'):
            user.set_password(self.cleaned_data['password1'])

        # Solo administración entra al panel completo de Django (/admin/).
        user.is_staff = user.is_superuser or rol == Perfil.Rol.ADMINISTRADOR

        if commit:
            user.save()
            Perfil.objects.update_or_create(usuario=user, defaults={
                'rol': rol,
                'telefono': self.cleaned_data['telefono'],
                'direccion': self.cleaned_data['direccion'],
            })

            grupos = list(self.cleaned_data['groups'])
            if self.es_nuevo and not grupos:
                por_defecto = Group.objects.filter(name=Perfil.GRUPO_POR_ROL[rol]).first()
                if por_defecto:
                    grupos = [por_defecto]
            user.groups.set(grupos)

        return user


class GrupoForm(forms.ModelForm):
    """Crea o edita un grupo y elige sus permisos con casillas."""

    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.filter(content_type__app_label__in=APPS_CON_PERMISOS),
        required=False,
    )

    class Meta:
        model = Group
        fields = ['name', 'permissions']
        labels = {'name': 'Nombre del grupo'}
        help_texts = {'name': 'Por ejemplo: Recepción de fin de semana.'}

    def secciones(self):
        """Los permisos agrupados por módulo, listos para dibujar casillas.

        Devuelve una lista como:
          [{'titulo': 'Citas', 'permisos': [{'id': 7, 'accion': 'Ver', 'marcado': True}, ...]}, ...]
        """
        if self.is_bound:
            marcados = {str(v) for v in self.data.getlist('permissions')}
        elif self.instance.pk:
            marcados = {str(p) for p in self.instance.permissions.values_list('pk', flat=True)}
        else:
            marcados = set()

        por_modelo = {}
        permisos = (self.fields['permissions'].queryset
                    .select_related('content_type')
                    .order_by('content_type__app_label', 'content_type__model'))
        for permiso in permisos:
            modelo = permiso.content_type.model_class()
            accion = permiso.codename.split('_', 1)[0]
            if modelo is None or accion not in ACCIONES:
                continue
            titulo = str(modelo._meta.verbose_name_plural).capitalize()
            por_modelo.setdefault(titulo, []).append({
                'id': permiso.pk,
                'accion': ACCIONES[accion],
                'orden': ORDEN_ACCIONES.index(accion),
                'marcado': str(permiso.pk) in marcados,
            })

        return [{'titulo': titulo, 'permisos': sorted(lista, key=lambda p: p['orden'])}
                for titulo, lista in por_modelo.items()]
