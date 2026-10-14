from django.contrib import messages
from django.contrib.auth.models import Group
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ROLES_PERSONAL, GrupoForm, PersonalForm
from .models import Personal
from .permisos import solo_administradores


@solo_administradores
def personal_listado(request):
    """Quienes trabajan en la clínica, con filtro por rol y buscador."""

    rol = request.GET.get('rol', '')
    buscar = request.GET.get('buscar', '').strip()

    personal = Personal.objects.prefetch_related('groups')
    if rol:
        personal = personal.filter(perfil__rol=rol)
    if buscar:
        personal = personal.filter(
            Q(first_name__icontains=buscar)
            | Q(last_name__icontains=buscar)
            | Q(username__icontains=buscar)
        )

    # Cada filtro con su propio conteo, igual que en Citas.
    filtros = [
        {'valor': valor, 'etiqueta': etiqueta,
         'conteo': Personal.objects.filter(perfil__rol=valor).count()}
        for valor, etiqueta in ROLES_PERSONAL
    ]

    return render(request, 'usuarios/personal_listado.html', {
        'seccion': 'personal',
        'personal': personal,
        'total': Personal.objects.count(),
        'filtros': filtros,
        'rol_activo': rol,
        'buscar': buscar,
    })


@solo_administradores
def personal_formulario(request, pk=None):
    """Sirve para crear (sin pk) y para editar (con pk)."""

    persona = get_object_or_404(Personal, pk=pk) if pk else None
    form = PersonalForm(request.POST or None, instance=persona, editor=request.user)

    if request.method == 'POST' and form.is_valid():
        user = form.save()
        nombre = user.get_full_name()
        if persona:
            messages.success(request, f'Se guardaron los cambios de {nombre}.')
        else:
            messages.success(request, f'{nombre} ya forma parte del personal.')
        return redirect('personal')

    return render(request, 'usuarios/personal_form.html', {
        'seccion': 'personal',
        'form': form,
        'persona': persona,
    })


@solo_administradores
def grupos_listado(request):
    """Los grupos de permisos, con cuántos permisos y personas tiene cada uno."""

    grupos = (Group.objects
              .annotate(n_permisos=Count('permissions', distinct=True),
                        n_personas=Count('user', distinct=True))
              .order_by('name'))

    return render(request, 'usuarios/grupos_listado.html', {
        'seccion': 'grupos',
        'grupos': grupos,
    })


@solo_administradores
def grupo_formulario(request, pk=None):
    """Crea o edita un grupo y sus permisos."""

    grupo = get_object_or_404(Group, pk=pk) if pk else None
    form = GrupoForm(request.POST or None, instance=grupo)

    if request.method == 'POST' and form.is_valid():
        grupo = form.save()
        messages.success(request, f'Se guardó el grupo «{grupo.name}».')
        return redirect('grupos')

    return render(request, 'usuarios/grupo_form.html', {
        'seccion': 'grupos',
        'form': form,
        'grupo': grupo,
        'personas': grupo.user_set.order_by('first_name') if grupo else [],
    })
