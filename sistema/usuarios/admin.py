from django import forms
from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User

from .models import GrupoPermisos, Perfil, Personal


class PerfilInline(admin.StackedInline):
    """Muestra el rol, teléfono y dirección dentro de la ficha del usuario."""

    model = Perfil
    can_delete = False
    verbose_name = 'datos en PreVet'
    verbose_name_plural = 'datos en PreVet'
    fields = ('rol', 'es_administrador', 'telefono', 'direccion')


class PerfilPersonalForm(forms.ModelForm):
    """En el apartado de personal solo se ofrecen los roles del equipo."""

    class Meta:
        model = Perfil
        fields = PerfilInline.fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['rol'].choices = [c for c in Perfil.Rol.choices
                                      if c[0] in Perfil.ROLES_PERSONAL]
        if not self.instance.pk:
            self.fields['rol'].initial = Perfil.Rol.RECEPCIONISTA


class PerfilPersonalInline(PerfilInline):
    form = PerfilPersonalForm
    min_num = 1


class UsuarioAdmin(UserAdmin):
    """Todos los usuarios (personal y dueños), con su perfil adentro."""

    inlines = [PerfilInline]
    list_display = ('username', 'nombre', 'rol', 'email', 'is_active')
    list_filter = ('perfil__rol', 'is_active', 'is_staff', 'groups')

    @admin.display(description='Nombre', ordering='first_name')
    def nombre(self, obj):
        return obj.get_full_name() or '—'

    @admin.display(description='Rol', ordering='perfil__rol')
    def rol(self, obj):
        perfil = getattr(obj, 'perfil', None)
        return perfil.get_rol_display() if perfil else '—'


@admin.register(Personal)
class PersonalAdmin(UsuarioAdmin):
    """Solo quienes trabajan en la clínica."""

    inlines = [PerfilPersonalInline]
    list_display = ('username', 'nombre', 'rol', 'grupos', 'is_active')
    list_filter = ('perfil__rol', 'is_active', 'groups')

    @admin.display(description='Grupos de permisos')
    def grupos(self, obj):
        return ', '.join(g.name for g in obj.groups.all()) or '—'

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('groups')


@admin.register(GrupoPermisos)
class GrupoPermisosAdmin(GroupAdmin):
    pass


# Se reemplazan los apartados que Django trae por defecto: "Usuarios" ahora
# muestra el perfil, y "Grupos" pasa a ser "Grupos de permisos".
admin.site.unregister(User)
admin.site.register(User, UsuarioAdmin)
admin.site.unregister(Group)
