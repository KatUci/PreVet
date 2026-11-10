"""Contacto con el tutor según el riesgo de la cita.

Los sistemas veterinarios del mercado mandan el mismo recordatorio a todos.
PreVet usa el riesgo de inasistencia para decidir qué decir: a una cita de
riesgo alto se le pide una confirmación explícita, a una de riesgo medio se
le recuerda con la opción de cambiarla y a una de riesgo bajo basta un aviso
breve. Además arma un guion para la llamada a partir de los factores que
explican el puntaje.
"""
import re
from urllib.parse import quote

DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']

# Desde cuántos días de anticipación conviene recordarle la fecha al tutor.
RESERVA_LEJANA = 14
# Cuánto más alta que el promedio debe ser una tasa para mencionarla en el guion.
SOBRE_PROMEDIO = 1.2


def numero_internacional(telefono):
    """Los dígitos del teléfono con el código de Chile; None si el teléfono no sirve."""
    digitos = re.sub(r'\D', '', telefono or '')
    if len(digitos) == 9:            # 9 1234 5678 -> se le agrega el 56 de Chile
        digitos = '56' + digitos
    if not 11 <= len(digitos) <= 15:
        return None
    return digitos


def enlace_whatsapp(telefono, mensaje):
    """Enlace que abre la app de WhatsApp con el chat y el mensaje listos.

    Usa el protocolo whatsapp:// en vez de wa.me: así se abre directo la
    aplicación instalada (WhatsApp de escritorio o del celular), sin pasar
    por la página intermedia que ofrece WhatsApp Web. Quien atiende decide
    si lo envía. None si el teléfono no sirve.
    """
    digitos = numero_internacional(telefono)
    if digitos is None:
        return None
    return f'whatsapp://send?phone={digitos}&text={quote(mensaje)}'


def enlace_llamada(telefono):
    """Enlace tel: con el número completo, para llamar de verdad.

    En el celular abre el marcador; en Windows, la app Enlace Móvil llama
    a través del celular de la clínica. None si el teléfono no sirve.
    """
    digitos = numero_internacional(telefono)
    return f'tel:+{digitos}' if digitos else None


# Textos originales de los mensajes (PV-REC-06). Administración los puede
# cambiar en Configuración > Mensajes de WhatsApp; si no los ha cambiado,
# se usan estos.
TEXTOS_ORIGINALES = {
    'riesgo_alto': ('Hola {tutor}, te escribimos de la clínica veterinaria para confirmar la hora de '
                    '{mascota} el {dia} {fecha} a las {hora} con {profesional}. '
                    '¿Nos respondes SÍ para confirmarla? Si no puedes venir, avísanos y te buscamos otra hora: '
                    'así podemos dar ese espacio a otra mascota que lo necesita.'),
    'riesgo_medio': ('Hola {tutor}, te recordamos la hora de {mascota} el {dia} {fecha} a las {hora}. '
                     'Si necesitas cambiarla, respóndenos este mensaje y te ayudamos.'),
    'riesgo_bajo': 'Hola {tutor}, te recordamos la hora de {mascota} el {dia} {fecha} a las {hora}. ¡Te esperamos!',
    'recordatorio': ('Hola {tutor}, te escribimos de la clínica para recordarte la hora de {mascota} '
                     'el {fecha} a las {hora}. ¿Nos confirmas tu asistencia?'),
    'vacuna': ('Hola {tutor}, te escribimos de la clínica veterinaria. A {mascota} le corresponde '
               'la vacuna {vacuna} el {fecha}. ¿Te agendamos una hora?'),
}

# Variables que se pueden usar en cada plantilla.
VARIABLES_CITA = ['tutor', 'mascota', 'dia', 'fecha', 'hora', 'profesional']
VARIABLES = {clave: VARIABLES_CITA for clave in TEXTOS_ORIGINALES}
VARIABLES['vacuna'] = ['tutor', 'mascota', 'vacuna', 'fecha']


def texto_plantilla(clave):
    """El texto que está usando la clínica: el editado, o si no, el original."""
    from .models import PlantillaMensaje
    plantilla = PlantillaMensaje.objects.filter(clave=clave).first()
    return plantilla.texto if plantilla else TEXTOS_ORIGINALES[clave]


def armar_mensaje(clave, datos):
    """Reemplaza cada {variable} de la plantilla por su valor."""
    texto = texto_plantilla(clave)
    for variable, valor in datos.items():
        texto = texto.replace('{' + variable + '}', str(valor))
    return texto


def datos_de_cita(cita):
    """Los valores de las variables para una cita."""
    return {
        'tutor': cita.cliente.nombres,
        'mascota': cita.mascota.nombre,
        'dia': DIAS[cita.fecha.weekday()],
        'fecha': cita.fecha.strftime('%d/%m'),
        'hora': cita.hora.strftime('%H:%M'),
        'profesional': cita.veterinario.get_full_name(),
    }


def mensaje_segun_riesgo(cita, nivel):
    """El texto del WhatsApp cambia según el riesgo de que el tutor no llegue."""
    if nivel not in ('alto', 'medio'):
        nivel = 'bajo'
    return armar_mensaje('riesgo_' + nivel, datos_de_cita(cita))


def guion_llamada(cita, nivel, stats):
    """Qué decirle al tutor, según los factores que hacen riesgosa la cita."""
    guion = []

    faltas, total = stats['tutor'].get(cita.cliente_id, (0, 0))
    if total == 0:
        guion.append('Es su primera visita: confirma que sabe llegar a la clínica y qué debe traer.')
    elif faltas >= 2 or faltas / total >= .3:
        guion.append(f'Ha faltado {faltas} de {total} veces: pide que confirme explícitamente y, '
                     f'si duda, ofrécele cambiar la hora en la misma llamada.')

    dias = max(cita.dias_anticipacion, 0)
    if dias >= RESERVA_LEJANA:
        guion.append(f'La reservó hace {dias} días: repítele la fecha y la hora, puede haberla olvidado.')

    tasa_dia = stats['dia'].get(cita.fecha.weekday())
    if tasa_dia and tasa_dia >= stats['global'] * SOBRE_PROMEDIO:
        guion.append(f'Los {DIAS[cita.fecha.weekday()]} falta más gente ({tasa_dia * 100:.0f}%): '
                     f'pregúntale si ese día le sigue acomodando.')

    tasa_tipo = stats['tipo'].get(cita.tipo_atencion_id)
    if tasa_tipo and tasa_tipo >= stats['global'] * SOBRE_PROMEDIO:
        guion.append(f'A {cita.tipo_atencion.nombre.lower()} falta el {tasa_tipo * 100:.0f}%: '
                     f'explícale por qué es importante no perder la hora.')

    if nivel == 'alto':
        guion.append('Si no contesta, envíale el WhatsApp y considera la hora para un sobrecupo.')
    if not guion:
        guion.append('Basta con un recordatorio breve.')
    return guion
