"""Registro de cambios de las citas (PV-ADM-05): quién cambió qué y cuándo.

En vez de anotar el cambio en cada pantalla, se compara la cita antes y
después de guardarla. Así queda registrado aunque la cambie una pantalla
nueva o alguien desde el panel /admin/. Quién la cambió lo aporta el
middleware, que recuerda el usuario de la petición en curso.
"""
import contextvars
import datetime

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import CambioCita, Cita

_usuario_actual = contextvars.ContextVar('usuario_actual', default=None)

# Lo que se mira de cada cita y cómo se llama en el historial. Las fechas
# y usuarios de cancelación o confirmación no se listan aparte: el propio
# registro ya dice quién y cuándo.
CAMPOS = [
    ('estado', 'Estado'),
    ('fecha', 'Fecha'),
    ('hora', 'Hora'),
    ('veterinario', 'Profesional'),
    ('tipo_atencion', 'Tipo de atención'),
    ('mascota', 'Mascota'),
    ('cliente', 'Cliente'),
    ('notas', 'Motivo o comentarios'),
    ('motivo_cancelacion', 'Motivo de la cancelación'),
    ('confirmacion', 'Confirmación'),
    ('hora_llegada', 'Llegada'),
    ('inicio_atencion', 'Pasó a atención'),
    ('hora_salida', 'Salida'),
]


class UsuarioActualMiddleware:
    """Recuerda quién hace la petición, para anotarlo en el historial de la cita."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = request.user if getattr(request, 'user', None) and request.user.is_authenticated else None
        token = _usuario_actual.set(usuario)
        try:
            return self.get_response(request)
        finally:
            _usuario_actual.reset(token)


def _normal(cita, campo):
    """El valor del campo con su tipo: una hora escrita como texto ('10:00') pasa a ser una hora."""
    valor = getattr(cita, campo)
    return Cita._meta.get_field(campo).to_python(valor) if isinstance(valor, str) else valor


def _texto(cita, campo):
    """El valor de un campo como se lee en pantalla."""
    valor = _normal(cita, campo)
    if valor in (None, ''):
        return '—'
    if campo == 'veterinario':
        return valor.get_full_name() or valor.username
    if campo == 'tipo_atencion':
        return valor.nombre
    if campo == 'cliente':
        return valor.nombre_completo
    if hasattr(cita, f'get_{campo}_display'):
        return getattr(cita, f'get_{campo}_display')()
    if isinstance(valor, datetime.datetime):
        return timezone.localtime(valor).strftime('%d/%m/%Y %H:%M')
    if isinstance(valor, datetime.date):
        return valor.strftime('%d/%m/%Y')
    if isinstance(valor, datetime.time):
        return valor.strftime('%H:%M')
    return str(valor)


def _valor(cita, campo):
    """Lo que se compara: el id en las relaciones, para no consultar la base."""
    if Cita._meta.get_field(campo).is_relation:
        return getattr(cita, Cita._meta.get_field(campo).attname)
    return _normal(cita, campo)


def _accion(antes, despues, cambiados):
    """Un nombre corto para el cambio, el que se lee primero en el historial."""
    if 'estado' in cambiados:
        return {'cancelada': 'Cancelada', 'no_asistio': 'Marcada como no asistió', 'completada': 'Atendida',
                'pendiente': 'Vuelta a pendiente'}.get(despues.estado, 'Cambio de estado')
    if {'fecha', 'hora', 'veterinario'} & cambiados:
        return 'Reagendada'
    for campo, accion in (('hora_salida', 'Salió'), ('inicio_atencion', 'Pasó a atención'),
                          ('hora_llegada', 'Llegó'), ('confirmacion', 'Confirmación')):
        if campo in cambiados:
            return accion
    return 'Editada'


@receiver(pre_save, sender=Cita)
def _recordar_como_estaba(sender, instance, raw=False, **kwargs):
    instance._antes = None
    if instance.pk and not raw:
        instance._antes = Cita.objects.filter(pk=instance.pk).select_related(
            'veterinario', 'tipo_atencion', 'mascota', 'cliente').first()


@receiver(post_save, sender=Cita)
def _anotar_el_cambio(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    usuario = _usuario_actual.get()
    if created:
        CambioCita.objects.create(
            cita=instance, usuario=usuario, accion='Agendada',
            detalle=f'{_texto(instance, "fecha")} a las {_texto(instance, "hora")} con {_texto(instance, "veterinario")}')
        return

    antes = getattr(instance, '_antes', None)
    if antes is None:
        return
    cambiados = {campo for campo, _ in CAMPOS if _valor(antes, campo) != _valor(instance, campo)}
    if not cambiados:
        return
    detalle = ' · '.join(f'{nombre}: {_texto(antes, campo)} → {_texto(instance, campo)}'
                         for campo, nombre in CAMPOS if campo in cambiados)
    CambioCita.objects.create(cita=instance, usuario=usuario, accion=_accion(antes, instance, cambiados),
                              detalle=detalle)
