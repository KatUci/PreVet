"""Modelo de puntuación del riesgo de inasistencia.

Estima, para cada cita pendiente, qué tan probable es que el tutor no
se presente. No usa aprendizaje automático: son reglas ponderadas sobre
el historial, de modo que cada puntaje se puede explicar.
"""

from .models import Cita

# Cuánto pesa cada factor sobre un total de 100.
PESO_TUTOR = 40
PESO_ANTICIPACION = 20
PESO_DIA = 20
PESO_TIPO = 20

# Una reserva hecha con esta anticipación o más se considera el máximo riesgo.
DIAS_MAXIMA_ANTICIPACION = 21

UMBRAL_ALTO = 62
UMBRAL_MEDIO = 48

ACCIONES = {
    'alto': 'Confirmar por teléfono y ofrecer el bloque en lista de espera',
    'medio': 'Reforzar el recordatorio el día anterior',
    'bajo': 'Sin acción',
}


def _tasa(faltas, total):
    """Proporción de inasistencias, o None si no hay historial."""
    return faltas / total if total else None


def estadisticas():
    """Calcula de una sola vez las tasas históricas que necesita el modelo.

    Se hace así, y no consultando dentro del bucle, para no golpear la
    base de datos una vez por cita.
    """
    resueltas = Cita.objects.filter(estado__in=['completada', 'no_asistio'])

    por_dia, por_tipo, por_tutor = {}, {}, {}
    total_global = faltas_global = 0

    for cita in resueltas.select_related('tipo_atencion', 'mascota'):
        falto = cita.estado == 'no_asistio'
        total_global += 1
        faltas_global += falto

        dia = cita.fecha.weekday()
        por_dia.setdefault(dia, [0, 0])
        por_dia[dia][0] += falto
        por_dia[dia][1] += 1

        tipo = cita.tipo_atencion_id
        por_tipo.setdefault(tipo, [0, 0])
        por_tipo[tipo][0] += falto
        por_tipo[tipo][1] += 1

        tutor = cita.mascota.dueno_id
        por_tutor.setdefault(tutor, [0, 0])
        por_tutor[tutor][0] += falto
        por_tutor[tutor][1] += 1

    tasas_dia = {d: _tasa(*v) for d, v in por_dia.items()}
    tasas_tipo = {t: _tasa(*v) for t, v in por_tipo.items()}

    return {
        'global': _tasa(faltas_global, total_global) or 0,
        'dia': tasas_dia,
        'tipo': tasas_tipo,
        'tutor': por_tutor,
        # Las tasas de día y tipo se comparan contra la peor observada,
        # para que el factor quede entre 0 y 1.
        'peor_dia': max(tasas_dia.values(), default=0) or 1,
        'peor_tipo': max(tasas_tipo.values(), default=0) or 1,
    }


def puntuar(cita, stats):
    """Devuelve el puntaje, el nivel, la acción sugerida y el detalle.

    El detalle sirve para poder mostrar por qué una cita quedó en
    determinado nivel, en vez de entregar solo un número.
    """
    detalle = []
    puntaje = 0

    # 1. Historial del tutor
    faltas, total = stats['tutor'].get(cita.mascota.dueno_id, (0, 0))
    if total == 0:
        aporte = PESO_TUTOR * 0.375        # primera visita: incertidumbre
        detalle.append('Primera visita, sin historial')
    else:
        tasa = faltas / total
        aporte = PESO_TUTOR * tasa
        detalle.append(f'Ha faltado {faltas} de {total} veces')
    puntaje += aporte

    # 2. Anticipación de la reserva
    dias = max(cita.dias_anticipacion, 0)
    proporcion = min(dias / DIAS_MAXIMA_ANTICIPACION, 1)
    puntaje += PESO_ANTICIPACION * proporcion
    detalle.append(f'Reservada con {dias} días de anticipación')

    # 3. Día de la semana
    tasa_dia = stats['dia'].get(cita.fecha.weekday()) or stats['global']
    puntaje += PESO_DIA * (tasa_dia / stats['peor_dia'])
    detalle.append(f'Ese día falta el {tasa_dia * 100:.0f}% de la gente')

    # 4. Tipo de atención
    tasa_tipo = stats['tipo'].get(cita.tipo_atencion_id) or stats['global']
    puntaje += PESO_TIPO * (tasa_tipo / stats['peor_tipo'])
    detalle.append(f'A {cita.tipo_atencion.nombre} falta el {tasa_tipo * 100:.0f}%')

    puntaje = round(min(puntaje, 100))

    if puntaje >= UMBRAL_ALTO:
        nivel = 'alto'
    elif puntaje >= UMBRAL_MEDIO:
        nivel = 'medio'
    else:
        nivel = 'bajo'

    return puntaje, nivel, ACCIONES[nivel], detalle