"""Modelo de puntuación del riesgo de inasistencia.

Estima, para cada cita pendiente, qué tan probable es que el tutor no
se presente. No usa aprendizaje automático: son reglas ponderadas sobre
el historial, de modo que cada puntaje se puede explicar.
"""

from django.utils import timezone

from .models import Cita, PesosModelo

# Cuánto pesa cada factor sobre un total de 100. Son los pesos originales:
# administración puede ajustarlos desde Configuración (PV-RIE-04).
PESO_TUTOR = 40
PESO_ANTICIPACION = 20
PESO_DIA = 20
PESO_TIPO = 20
PESOS_ORIGINALES = {'tutor': PESO_TUTOR, 'anticipacion': PESO_ANTICIPACION, 'dia': PESO_DIA, 'tipo': PESO_TIPO}

# Una reserva hecha con esta anticipación o más se considera el máximo riesgo.
DIAS_MAXIMA_ANTICIPACION = 21

UMBRAL_ALTO = 62
UMBRAL_MEDIO = 48

ACCIONES = {
    'alto': 'Confirmar por teléfono y ofrecer el bloque en lista de espera',
    'medio': 'Reforzar el recordatorio el día anterior',
    'bajo': 'Sin acción',
}


def pesos_actuales():
    """Los pesos que usa el modelo: los ajustados por administración o, si nadie los ha cambiado, los originales."""
    ajustados = PesosModelo.objects.first()
    return ajustados.como_dict() if ajustados else dict(PESOS_ORIGINALES)


def _tasa(faltas, total):
    """Proporción de inasistencias, o None si no hay historial."""
    return faltas / total if total else None


def resueltas():
    """Las citas de las que ya se sabe si el tutor llegó o no.

    Las atenciones sin hora no cuentan: el paciente ya estaba en la clínica,
    así que siempre "asiste" y haría ver el riesgo más bajo de lo que es.
    """
    return Cita.objects.filter(estado__in=['completada', 'no_asistio']).exclude(sin_hora=True)


class Historial:
    """Va contando asistencias y faltas por día, tipo de atención y tutor.

    Se puede llenar de una vez (para puntuar las citas pendientes) o de a
    poco, fecha por fecha, para evaluar el modelo como si se hubiera usado
    en el pasado (ver evaluar()).
    """

    def __init__(self):
        self.por_dia, self.por_tipo, self.por_tutor = {}, {}, {}
        self.total = self.faltas = 0

    def agregar(self, cita):
        falto = cita.estado == 'no_asistio'
        self.total += 1
        self.faltas += falto
        # El historial es de la persona que agenda, no de la mascota.
        for cuenta, clave in ((self.por_dia, cita.fecha.weekday()),
                              (self.por_tipo, cita.tipo_atencion_id),
                              (self.por_tutor, cita.cliente_id)):
            cuenta.setdefault(clave, [0, 0])
            cuenta[clave][0] += falto
            cuenta[clave][1] += 1

    def stats(self):
        tasas_dia = {d: _tasa(*v) for d, v in self.por_dia.items()}
        tasas_tipo = {t: _tasa(*v) for t, v in self.por_tipo.items()}
        return {
            'global': _tasa(self.faltas, self.total) or 0,
            'dia': tasas_dia,
            'tipo': tasas_tipo,
            # Copia: si después se siguen agregando citas, estas tasas no cambian.
            'tutor': {t: tuple(v) for t, v in self.por_tutor.items()},
            # Las tasas de día y tipo se comparan contra la peor observada,
            # para que el factor quede entre 0 y 1.
            'peor_dia': max(tasas_dia.values(), default=0) or 1,
            'peor_tipo': max(tasas_tipo.values(), default=0) or 1,
        }


def estadisticas():
    """Calcula de una sola vez las tasas históricas que necesita el modelo.

    Se hace así, y no consultando dentro del bucle, para no golpear la
    base de datos una vez por cita.
    """
    historial = Historial()
    for cita in resueltas():
        historial.agregar(cita)
    stats = historial.stats()
    stats['pesos'] = pesos_actuales()
    return stats


def puntuar(cita, stats):
    """Devuelve el puntaje, el nivel, la acción sugerida y el detalle.

    El detalle sirve para poder mostrar por qué una cita quedó en
    determinado nivel, en vez de entregar solo un número.
    """
    detalle = []
    puntaje = 0
    pesos = stats.get('pesos') or PESOS_ORIGINALES

    # 1. Historial del tutor
    faltas, total = stats['tutor'].get(cita.cliente_id, (0, 0))
    if total == 0:
        aporte = pesos['tutor'] * 0.375    # primera visita: incertidumbre
        detalle.append('Primera visita, sin historial')
    else:
        tasa = faltas / total
        aporte = pesos['tutor'] * tasa
        detalle.append(f'Ha faltado {faltas} de {total} veces')
    puntaje += aporte

    # 2. Anticipación de la reserva
    dias = max(cita.dias_anticipacion, 0)
    proporcion = min(dias / DIAS_MAXIMA_ANTICIPACION, 1)
    puntaje += pesos['anticipacion'] * proporcion
    detalle.append(f'Reservada con {dias} días de anticipación')

    # 3. Día de la semana
    tasa_dia = stats['dia'].get(cita.fecha.weekday()) or stats['global']
    puntaje += pesos['dia'] * (tasa_dia / stats['peor_dia'])
    detalle.append(f'Ese día falta el {tasa_dia * 100:.0f}% de la gente')

    # 4. Tipo de atención
    tasa_tipo = stats['tipo'].get(cita.tipo_atencion_id) or stats['global']
    puntaje += pesos['tipo'] * (tasa_tipo / stats['peor_tipo'])
    detalle.append(f'A {cita.tipo_atencion.nombre} falta el {tasa_tipo * 100:.0f}%')

    puntaje = round(min(puntaje, 100))

    if puntaje >= UMBRAL_ALTO:
        nivel = 'alto'
    elif puntaje >= UMBRAL_MEDIO:
        nivel = 'medio'
    else:
        nivel = 'bajo'

    return puntaje, nivel, ACCIONES[nivel], detalle

def evaluar(desde=None, hasta=None, pesos=None):
    """¿Acierta el modelo? Compara el riesgo estimado con lo que pasó (PV-RIE-03).

    Recorre las citas resueltas de la más antigua a la más nueva y puntúa
    cada una solo con el historial de las fechas anteriores, como si el
    modelo la hubiera evaluado el día antes. Si se usara todo el historial,
    la falta de la propia cita subiría su puntaje y el modelo parecería
    acertar más de lo que acierta.

    Devuelve una lista de (cita, puntaje, nivel), solo de las citas entre
    `desde` y `hasta`; las anteriores igual alimentan el historial. Con
    `pesos` se prueba otra combinación sin guardarla (PV-RIE-04).
    """
    from itertools import groupby

    citas = (resueltas().select_related('tipo_atencion')
             .filter(fecha__lt=timezone.localdate()).order_by('fecha', 'hora'))
    if hasta:
        citas = citas.filter(fecha__lte=hasta)

    pesos = pesos or pesos_actuales()
    historial = Historial()
    evaluadas = []
    for fecha, del_dia in groupby(citas, key=lambda c: c.fecha):
        del_dia = list(del_dia)
        if not desde or fecha >= desde:
            stats = historial.stats()
            stats['pesos'] = pesos
            for cita in del_dia:
                puntaje, nivel, _, _ = puntuar(cita, stats)
                evaluadas.append((cita, puntaje, nivel))
        for cita in del_dia:
            historial.agregar(cita)
    return evaluadas


def resumen_evaluacion(evaluadas):
    """Cuántas citas cayeron en cada nivel y cuántas de ellas terminaron en falta."""
    total = len(evaluadas)
    faltas = sum(1 for c, _, _ in evaluadas if c.estado == 'no_asistio')
    niveles = []
    for nivel in ('alto', 'medio', 'bajo'):
        grupo = [c for c, _, n in evaluadas if n == nivel]
        faltaron = sum(1 for c in grupo if c.estado == 'no_asistio')
        niveles.append({
            'nivel': nivel,
            'citas': len(grupo),
            'faltas': faltaron,
            'asistieron': len(grupo) - faltaron,
            'tasa': round(faltaron / len(grupo) * 100, 1) if grupo else 0,
            # Qué parte de todas las faltas cayó en este nivel.
            'de_las_faltas': round(faltaron / faltas * 100) if faltas else 0,
        })
    por_nivel = {n['nivel']: n for n in niveles}

    # Se cuenta como acierto avisar (alto o medio) a quien faltó y no
    # avisar (bajo) a quien llegó.
    aciertos = (por_nivel['alto']['faltas'] + por_nivel['medio']['faltas']
                + por_nivel['bajo']['asistieron'])
    bajo = por_nivel['bajo']['tasa']
    return {
        'total': total,
        'faltas': faltas,
        'tasa': round(faltas / total * 100, 1) if total else 0,
        'niveles': niveles,
        'aciertos': round(aciertos / total * 100) if total else 0,
        # De todas las faltas, cuántas el modelo marcó con riesgo alto o medio.
        'anticipadas': por_nivel['alto']['de_las_faltas'] + por_nivel['medio']['de_las_faltas'],
        # Cuántas veces más se falta en riesgo alto que en riesgo bajo.
        'veces': round(por_nivel['alto']['tasa'] / bajo, 1) if bajo and por_nivel['alto']['citas'] else None,
    }
