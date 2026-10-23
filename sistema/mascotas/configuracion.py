"""Configuración de mascotas: tipos de mascota (especies), razas y etiquetas de alerta."""
from django import forms
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from core import crud

from .models import Especie, Etiqueta, Raza

MIGAS = [('Configuración', None)]


class EspecieForm(forms.ModelForm):
    class Meta:
        model = Especie
        fields = ['nombre']
        labels = {'nombre': 'Tipo de mascota'}
        help_texts = {'nombre': 'Por ejemplo: Perro, Gato, Conejo, Hurón.'}


class RazaForm(forms.ModelForm):
    class Meta:
        model = Raza
        fields = ['especie', 'nombre']
        labels = {'especie': 'Tipo de mascota', 'nombre': 'Raza'}

    def clean(self):
        datos = super().clean()
        especie, nombre = datos.get('especie'), (datos.get('nombre') or '').strip()
        if especie and nombre and (Raza.objects.filter(especie=especie, nombre__iexact=nombre)
                                   .exclude(pk=self.instance.pk).exists()):
            self.add_error('nombre', f'Ya existe la raza «{nombre}» para {especie.nombre}.')
        return datos


def _exigir(request, permiso):
    if not request.user.has_perm(permiso):
        raise PermissionDenied


@login_required
@permission_required('mascotas.view_especie', raise_exception=True)
def especies_listado(request):
    puede_editar = request.user.has_perm('mascotas.change_especie')
    puede_eliminar = request.user.has_perm('mascotas.delete_especie')
    especies = Especie.objects.annotate(n_razas=Count('razas', distinct=True),
                                        n_mascotas=Count('mascota', distinct=True)).order_by('nombre')
    filas = [{
        'nombre': e.nombre,
        'celdas': [f'{e.emoji} {e.nombre}', e.n_razas, e.n_mascotas],
        'editar': reverse('especie_editar', args=[e.pk]) if puede_editar else None,
        'eliminar': reverse('especie_eliminar', args=[e.pk]) if puede_eliminar else None,
    } for e in especies]
    return crud.listado(
        request, seccion='especies', titulo='Tipos de mascota',
        subtitulo='Al registrar una mascota se elige primero su tipo y luego la raza',
        columnas=['Tipo', 'Razas', 'Mascotas'], filas=filas,
        url_nuevo=reverse('especie_nueva') if request.user.has_perm('mascotas.add_especie') else None,
        texto_nuevo='Nuevo tipo', migas=MIGAS + [('Tipos de mascota', None)])


@login_required
def especie_formulario(request, pk=None):
    _exigir(request, 'mascotas.change_especie' if pk else 'mascotas.add_especie')
    especie = get_object_or_404(Especie, pk=pk) if pk else None
    volver = reverse('especies')
    return crud.formulario(
        request, form=EspecieForm(request.POST or None, instance=especie), seccion='especies',
        titulo=f'Editar «{especie.nombre}»' if especie else 'Nuevo tipo de mascota', volver=volver,
        mensaje='Se guardó el tipo de mascota «{objeto.nombre}».',
        migas=MIGAS + [('Tipos de mascota', volver), ('Editar' if especie else 'Nuevo', None)])


@require_POST
@login_required
@permission_required('mascotas.delete_especie', raise_exception=True)
def especie_eliminar(request, pk):
    return crud.eliminar(request, get_object_or_404(Especie, pk=pk), volver=reverse('especies'),
                         en_uso='hay mascotas registradas de este tipo.')


@login_required
@permission_required('mascotas.view_raza', raise_exception=True)
def razas_listado(request):
    puede_editar = request.user.has_perm('mascotas.change_raza')
    puede_eliminar = request.user.has_perm('mascotas.delete_raza')
    razas = (Raza.objects.select_related('especie').annotate(n_mascotas=Count('mascota'))
             .order_by('especie__nombre', 'nombre'))
    filas = [{
        'nombre': r.nombre,
        'celdas': [r.nombre, f'{r.especie.emoji} {r.especie.nombre}', r.n_mascotas],
        'editar': reverse('raza_editar', args=[r.pk]) if puede_editar else None,
        'eliminar': reverse('raza_eliminar', args=[r.pk]) if puede_eliminar else None,
    } for r in razas]
    return crud.listado(
        request, seccion='razas', titulo='Razas', subtitulo='Razas disponibles para cada tipo de mascota',
        columnas=['Raza', 'Tipo', 'Mascotas'], filas=filas,
        url_nuevo=reverse('raza_nueva') if request.user.has_perm('mascotas.add_raza') else None,
        texto_nuevo='Nueva raza', migas=MIGAS + [('Razas', None)])


@login_required
def raza_formulario(request, pk=None):
    _exigir(request, 'mascotas.change_raza' if pk else 'mascotas.add_raza')
    raza = get_object_or_404(Raza, pk=pk) if pk else None
    volver = reverse('razas')
    return crud.formulario(
        request, form=RazaForm(request.POST or None, instance=raza), seccion='razas',
        titulo=f'Editar «{raza.nombre}»' if raza else 'Nueva raza', volver=volver,
        mensaje='Se guardó la raza «{objeto.nombre}».',
        migas=MIGAS + [('Razas', volver), ('Editar' if raza else 'Nueva', None)])


@require_POST
@login_required
@permission_required('mascotas.delete_raza', raise_exception=True)
def raza_eliminar(request, pk):
    return crud.eliminar(request, get_object_or_404(Raza, pk=pk), volver=reverse('razas'),
                         en_uso='hay mascotas registradas con esta raza.')


# ---------------- Etiquetas de alerta (PV-CLI-04) ----------------

class EtiquetaForm(forms.ModelForm):
    class Meta:
        model = Etiqueta
        fields = ['nombre', 'para', 'tono', 'activo']
        labels = {'nombre': 'Etiqueta'}
        help_texts = {'nombre': 'Corta y clara: «Muerde: usar bozal», «Deuda pendiente».'}

    def clean_para(self):
        para = self.cleaned_data['para']
        etiqueta = self.instance
        if etiqueta.pk and para != etiqueta.para and (etiqueta.clientes.exists() or etiqueta.mascotas.exists()):
            raise forms.ValidationError('Ya está asignada: para cambiar su tipo, primero quítala de quienes la tienen.')
        return para

    def clean_nombre(self):
        nombre = self.cleaned_data['nombre'].strip()
        if Etiqueta.objects.filter(nombre__iexact=nombre).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Ya existe una etiqueta con ese nombre.')
        return nombre


@login_required
@permission_required('mascotas.view_etiqueta', raise_exception=True)
def etiquetas_listado(request):
    puede_editar = request.user.has_perm('mascotas.change_etiqueta')
    puede_eliminar = request.user.has_perm('mascotas.delete_etiqueta')
    etiquetas = Etiqueta.objects.annotate(
        n_clientes=Count('clientes', distinct=True), n_mascotas=Count('mascotas', distinct=True))
    filas = [{
        'nombre': e.nombre,
        'inactivo': not e.activo,
        'celdas': [{'badge': e.nombre, 'clase': f'etq-{e.tono}'}, e.get_para_display(),
                   e.n_clientes + e.n_mascotas,
                   {'badge': 'Disponible' if e.activo else 'No disponible',
                    'clase': 'completada' if e.activo else 'neutro'}],
        'editar': reverse('etiqueta_editar', args=[e.pk]) if puede_editar else None,
        'eliminar': reverse('etiqueta_eliminar', args=[e.pk]) if puede_eliminar else None,
    } for e in etiquetas]
    return crud.listado(
        request, seccion='etiquetas', titulo='Etiquetas de alerta',
        subtitulo='Avisos que se pegan a un cliente o a una mascota y se ven en el panel del día y en el detalle de la cita',
        columnas=['Etiqueta', 'Se usa en', 'Asignada a', 'Estado'], filas=filas,
        url_nuevo=reverse('etiqueta_nueva') if request.user.has_perm('mascotas.add_etiqueta') else None,
        texto_nuevo='Nueva etiqueta', migas=MIGAS + [('Etiquetas de alerta', None)])


@login_required
def etiqueta_formulario(request, pk=None):
    _exigir(request, 'mascotas.change_etiqueta' if pk else 'mascotas.add_etiqueta')
    etiqueta = get_object_or_404(Etiqueta, pk=pk) if pk else None
    volver = reverse('etiquetas')
    return crud.formulario(
        request, form=EtiquetaForm(request.POST or None, instance=etiqueta), seccion='etiquetas',
        titulo=f'Editar «{etiqueta.nombre}»' if etiqueta else 'Nueva etiqueta de alerta', volver=volver,
        mensaje='Se guardó la etiqueta «{objeto.nombre}».',
        migas=MIGAS + [('Etiquetas de alerta', volver), ('Editar' if etiqueta else 'Nueva', None)])


@require_POST
@login_required
@permission_required('mascotas.delete_etiqueta', raise_exception=True)
def etiqueta_eliminar(request, pk):
    # Una etiqueta se puede borrar aunque esté asignada: solo se quita el aviso.
    return crud.eliminar(request, get_object_or_404(Etiqueta, pk=pk), volver=reverse('etiquetas'))
