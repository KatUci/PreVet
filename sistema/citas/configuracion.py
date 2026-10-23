"""Configuración de la agenda: tipos de atención y horarios de cada veterinario."""
from django import forms
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from core import crud

from .models import DIAS_SEMANA, HorarioAtencion, TipoAtencion

MIGAS = [('Configuración', None)]


# ---------------- Tipos de atención ----------------

class TipoAtencionForm(forms.ModelForm):
    class Meta:
        model = TipoAtencion
        fields = ['nombre', 'duracion_minutos', 'precio', 'activo']
        labels = {'nombre': 'Nombre', 'duracion_minutos': 'Duración (minutos)',
                  'precio': 'Precio ($)', 'activo': 'Se puede agendar'}
        help_texts = {'activo': 'Si lo desmarcas, deja de aparecer al agendar, pero las citas antiguas lo conservan.'}

    def clean_duracion_minutos(self):
        minutos = self.cleaned_data['duracion_minutos']
        if not 5 <= minutos <= 240:
            raise forms.ValidationError('La duración debe estar entre 5 y 240 minutos.')
        return minutos

    def clean_precio(self):
        precio = self.cleaned_data['precio']
        if precio < 0:
            raise forms.ValidationError('El precio no puede ser negativo.')
        return precio


@login_required
@permission_required('citas.view_tipoatencion', raise_exception=True)
def tipos_listado(request):
    puede_editar = request.user.has_perm('citas.change_tipoatencion')
    puede_eliminar = request.user.has_perm('citas.delete_tipoatencion')
    filas = [{
        'nombre': t.nombre,
        'inactivo': not t.activo,
        'celdas': [t.nombre, f'{t.duracion_minutos} min', f'${t.precio:,}'.replace(',', '.'),
                   {'badge': 'Activo' if t.activo else 'Inactivo', 'clase': 'completada' if t.activo else 'neutro'}],
        'editar': reverse('tipo_editar', args=[t.pk]) if puede_editar else None,
        'eliminar': reverse('tipo_eliminar', args=[t.pk]) if puede_eliminar else None,
    } for t in TipoAtencion.objects.order_by('nombre')]
    return crud.listado(
        request, seccion='tipos', titulo='Tipos de atención',
        subtitulo='Lo que se puede agendar, cuánto dura y cuánto cuesta (el precio se usa para estimar lo que se pierde)',
        columnas=['Nombre', 'Duración', 'Precio', 'Estado'], filas=filas,
        url_nuevo=reverse('tipo_nuevo') if request.user.has_perm('citas.add_tipoatencion') else None,
        texto_nuevo='Nuevo tipo', migas=MIGAS + [('Tipos de atención', None)])


@login_required
def tipo_formulario(request, pk=None):
    permiso = 'citas.change_tipoatencion' if pk else 'citas.add_tipoatencion'
    if not request.user.has_perm(permiso):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    tipo = get_object_or_404(TipoAtencion, pk=pk) if pk else None
    volver = reverse('tipos_atencion')
    return crud.formulario(
        request, form=TipoAtencionForm(request.POST or None, instance=tipo), seccion='tipos',
        titulo=f'Editar «{tipo.nombre}»' if tipo else 'Nuevo tipo de atención', volver=volver,
        mensaje='Se guardó el tipo de atención «{objeto.nombre}».',
        migas=MIGAS + [('Tipos de atención', volver), ('Editar' if tipo else 'Nuevo', None)])


@require_POST
@login_required
@permission_required('citas.delete_tipoatencion', raise_exception=True)
def tipo_eliminar(request, pk):
    return crud.eliminar(request, get_object_or_404(TipoAtencion, pk=pk), volver=reverse('tipos_atencion'),
                         en_uso='tiene citas registradas. Desactívalo en vez de eliminarlo.')


# ---------------- Horarios de atención ----------------

class HorarioForm(forms.ModelForm):
    class Meta:
        model = HorarioAtencion
        fields = ['veterinario', 'dia_semana', 'hora_inicio', 'hora_fin', 'activo']
        labels = {'veterinario': 'Profesional', 'dia_semana': 'Día', 'hora_inicio': 'Desde',
                  'hora_fin': 'Hasta', 'activo': 'Vigente'}
        widgets = {'hora_inicio': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
                   'hora_fin': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M')}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['veterinario'].queryset = (User.objects.filter(perfil__rol='veterinario', is_active=True)
                                               .order_by('first_name'))
        self.fields['veterinario'].label_from_instance = lambda u: u.get_full_name() or u.username
        self.fields['dia_semana'].choices = list(DIAS_SEMANA)

    def clean(self):
        datos = super().clean()
        vet, dia = datos.get('veterinario'), datos.get('dia_semana')
        inicio, fin = datos.get('hora_inicio'), datos.get('hora_fin')
        if inicio and fin and fin <= inicio:
            self.add_error('hora_fin', 'La hora de término debe ser posterior a la de inicio.')
        elif vet and dia is not None and inicio and fin and datos.get('activo'):
            # Dos tramos del mismo profesional el mismo día no pueden pisarse.
            choque = (HorarioAtencion.objects.filter(veterinario=vet, dia_semana=dia, activo=True,
                                                     hora_inicio__lt=fin, hora_fin__gt=inicio)
                      .exclude(pk=self.instance.pk).first())
            if choque:
                raise forms.ValidationError(
                    f'Se cruza con otro tramo de ese día: {choque.hora_inicio:%H:%M} a {choque.hora_fin:%H:%M}.')
        return datos


@login_required
@permission_required('citas.view_horarioatencion', raise_exception=True)
def horarios_listado(request):
    puede_editar = request.user.has_perm('citas.change_horarioatencion')
    puede_eliminar = request.user.has_perm('citas.delete_horarioatencion')
    horarios = (HorarioAtencion.objects.select_related('veterinario')
                .order_by('veterinario__first_name', 'dia_semana', 'hora_inicio'))
    filas = [{
        'nombre': f'{h.get_dia_semana_display()} {h.hora_inicio:%H:%M}',
        'inactivo': not h.activo,
        'celdas': [h.veterinario.get_full_name() or h.veterinario.username, h.get_dia_semana_display(),
                   f'{h.hora_inicio:%H:%M} a {h.hora_fin:%H:%M}',
                   {'badge': 'Vigente' if h.activo else 'Suspendido', 'clase': 'completada' if h.activo else 'neutro'}],
        'editar': reverse('horario_editar', args=[h.pk]) if puede_editar else None,
        'eliminar': reverse('horario_eliminar', args=[h.pk]) if puede_eliminar else None,
    } for h in horarios]
    return crud.listado(
        request, seccion='horarios', titulo='Horarios de atención',
        subtitulo='Al agendar solo se ofrecen las horas dentro de estos tramos',
        columnas=['Profesional', 'Día', 'Horario', 'Estado'], filas=filas,
        url_nuevo=reverse('horario_nuevo') if request.user.has_perm('citas.add_horarioatencion') else None,
        texto_nuevo='Nuevo tramo', migas=MIGAS + [('Horarios de atención', None)])


@login_required
def horario_formulario(request, pk=None):
    permiso = 'citas.change_horarioatencion' if pk else 'citas.add_horarioatencion'
    if not request.user.has_perm(permiso):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    horario = get_object_or_404(HorarioAtencion, pk=pk) if pk else None
    volver = reverse('horarios')
    return crud.formulario(
        request, form=HorarioForm(request.POST or None, instance=horario), seccion='horarios',
        titulo='Editar tramo de atención' if horario else 'Nuevo tramo de atención', volver=volver,
        mensaje='Se guardó el horario de {objeto.veterinario.first_name}.',
        ayuda='Las citas ya agendadas no cambian; si un tramo se acorta, revisa el calendario de ese día.',
        migas=MIGAS + [('Horarios de atención', volver), ('Editar' if horario else 'Nuevo', None)])


@require_POST
@login_required
@permission_required('citas.delete_horarioatencion', raise_exception=True)
def horario_eliminar(request, pk):
    return crud.eliminar(request, get_object_or_404(HorarioAtencion, pk=pk), volver=reverse('horarios'))
