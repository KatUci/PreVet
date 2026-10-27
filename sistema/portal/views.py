"""Mi PreVet: el portal donde cada cliente ve y mantiene sus datos, sus mascotas y sus citas,
y pide hora él mismo.

Todo se filtra por el cliente de la sesión: nadie puede ver ni cambiar datos
de otra persona, aunque cambie los números de la dirección.
"""
from functools import wraps

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone

from citas.disponibilidad import resumen_horarios
from mascotas.fotos import FotoForm, guardar_foto
from mascotas.forms import MascotaEditarForm, MascotaForm
from mascotas.models import FotoMascota, Mascota, Tenencia

from .forms import MisDatosForm, PedirHoraForm, RegistroForm


def solo_tutores(vista):
    """La vista es del portal: exige sesión de un cliente; al personal lo manda a su inicio."""
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        cliente = getattr(request.user, 'cliente', None)
        if cliente is None:
            return redirect('inicio')
        request.cliente = cliente
        return vista(request, *args, **kwargs)
    return login_required(envoltura)


def _mi_mascota(request, pk):
    """Solo mascotas de las que el cliente es tutor."""
    if not Tenencia.objects.filter(cliente=request.cliente, mascota_id=pk).exists():
        raise Http404
    return get_object_or_404(Mascota.objects.select_related('especie', 'raza'), pk=pk)


def registro(request):
    if request.user.is_authenticated:
        return redirect('inicio')
    form = RegistroForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        usuario = form.save()
        login(request, usuario, backend='usuarios.backends.UsuarioORutBackend')
        messages.success(request, f'¡Bienvenida o bienvenido a Mi PreVet, {usuario.first_name}! '
                                  f'Desde ahora entras con tu RUT y tu contraseña.')
        return redirect('portal')
    return render(request, 'registration/registro.html', {'form': form})


@solo_tutores
def inicio(request):
    cliente = request.cliente
    hoy = timezone.localdate()
    citas = cliente.citas.select_related('mascota__especie', 'veterinario', 'tipo_atencion')
    tenencias = (cliente.tenencias.filter(mascota__activo=True)
                 .select_related('mascota__especie', 'mascota__raza').order_by('mascota__nombre'))
    return render(request, 'portal/inicio.html', {
        'seccion': 'portal',
        'cliente': cliente,
        'tenencias': tenencias,
        'proximas': citas.filter(estado='pendiente', fecha__gte=hoy).order_by('fecha', 'hora'),
        'historial': citas.exclude(estado='pendiente', fecha__gte=hoy).order_by('-fecha', '-hora')[:10],
    })


@solo_tutores
def mis_datos(request):
    form = MisDatosForm(request.POST or None, instance=request.cliente)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Tus datos quedaron actualizados.')
        return redirect('portal')
    return render(request, 'portal/formulario.html', {
        'seccion': 'portal_datos', 'form': form, 'titulo': 'Mis datos',
        'subtitulo': f'RUT {request.cliente.rut_formateado}. Para cambiar tu RUT, acércate a la clínica.',
    })


@solo_tutores
def pedir_hora(request):
    """El cliente agenda una hora para una de sus mascotas, sin tener que llamar."""
    form = PedirHoraForm(request.POST or None, cliente=request.cliente)
    if request.method == 'POST' and form.is_valid():
        cita = form.save()
        messages.success(request, f'¡Listo! {cita.mascota.nombre} tiene hora el {cita.fecha:%d/%m/%Y} a las '
                                  f'{cita.hora:%H:%M} con {cita.veterinario.get_full_name()}.')
        return redirect('portal')
    return render(request, 'portal/pedir_hora.html', {
        'seccion': 'portal_hora', 'form': form, 'horarios': resumen_horarios(),
    })


@solo_tutores
def mascota_nueva(request):
    form = MascotaForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            mascota = form.save()
            Tenencia.objects.create(cliente=request.cliente, mascota=mascota,
                                    relacion=form.cleaned_data['relacion'], es_principal=True)
            if form.cleaned_data.get('foto'):
                guardar_foto(mascota, form.cleaned_data['foto'], request.user)
        messages.success(request, f'{mascota.nombre} quedó registrada.')
        return redirect('portal')
    return render(request, 'portal/formulario.html', {
        'seccion': 'portal_mascota', 'form': form, 'titulo': 'Agregar una mascota',
        'subtitulo': 'Primero elige el tipo; luego, si la conoces, la raza.', 'con_archivos': True,
        'razas': True,
    })


@solo_tutores
def mascota_editar(request, pk):
    mascota = _mi_mascota(request, pk)
    form = MascotaEditarForm(request.POST or None, instance=mascota)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Se guardaron los datos de {mascota.nombre}.')
        return redirect('portal')
    return render(request, 'portal/formulario.html', {
        'seccion': 'portal', 'form': form, 'titulo': f'Datos de {mascota.nombre}',
        'subtitulo': 'Mantén al día su peso, alergias y cuidados: así la clínica la atiende mejor.', 'razas': True,
    })


@solo_tutores
def mascota_foto(request, pk):
    """La foto de una de sus mascotas (el personal usa /mascotas/<id>/foto/)."""
    _mi_mascota(request, pk)
    foto = FotoMascota.objects.filter(mascota_id=pk).only('imagen', 'tipo').first()
    if foto is None:
        raise Http404
    respuesta = HttpResponse(bytes(foto.imagen), content_type=foto.tipo)
    respuesta['Cache-Control'] = 'private, max-age=31536000'
    return respuesta


@solo_tutores
def mascota_foto_subir(request, pk):
    mascota = _mi_mascota(request, pk)
    form = FotoForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        guardar_foto(mascota, form.cleaned_data['foto'], request.user)
        messages.success(request, f'Se guardó la foto de {mascota.nombre}.')
        return redirect('portal')
    return render(request, 'portal/foto.html', {'seccion': 'portal', 'mascota': mascota, 'form': form})


class CambiarClave(PasswordChangeView):
    template_name = 'portal/formulario.html'
    success_url = reverse_lazy('portal')
    extra_context = {'seccion': 'portal_clave', 'titulo': 'Cambiar contraseña',
                     'subtitulo': 'Usa al menos 8 caracteres que no sean fáciles de adivinar.'}

    def form_valid(self, form):
        messages.success(self.request, 'Tu contraseña quedó cambiada.')
        return super().form_valid(form)
