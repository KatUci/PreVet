from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone

from citas.models import Cita


@login_required
def inicio(request):
    """Tablero con los indicadores de inasistencia."""

    hoy = timezone.localdate()

    # Solo las citas que ya ocurrieron: de las futuras todavía
    # no se sabe si van a concretarse.
    ocurridas = Cita.objects.filter(fecha__lt=hoy).exclude(estado='pendiente')

    total = ocurridas.count()
    faltas = ocurridas.filter(estado='no_asistio')
    n_faltas = faltas.count()

    tasa = (n_faltas / total * 100) if total else 0
    perdido = faltas.aggregate(t=Sum('tipo_atencion__precio'))['t'] or 0

    # Inasistencias por día de la semana, para ver si hay patrón.
    nombres = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    por_dia = []
    for numero, nombre in enumerate(nombres):
        del_dia = [c for c in ocurridas if c.fecha.weekday() == numero]
        n = len(del_dia)
        f = len([c for c in del_dia if c.estado == 'no_asistio'])
        if n:
            por_dia.append({
                'dia': nombre,
                'total': n,
                'faltas': f,
                'tasa': round(f / n * 100),
            })

    tope = max([d['tasa'] for d in por_dia] + [1])
    for d in por_dia:
        d['alto'] = round(d['tasa'] / tope * 100)

    contexto = {
        'seccion': 'inicio',
        'total_ocurridas': total,
        'total_faltas': n_faltas,
        'tasa': round(tasa, 1),
        'perdido': perdido,
        'por_dia': por_dia,
        'proximas': Cita.objects.filter(fecha__gte=hoy, estado='pendiente')
                                .select_related('mascota', 'veterinario', 'tipo_atencion')
                                .order_by('fecha', 'hora')[:8],
    }
    return render(request, 'core/inicio.html', contexto)

@login_required
def riesgo(request):
    """Citas pendientes ordenadas por su riesgo de inasistencia."""

    from citas.riesgo import estadisticas, puntuar

    hoy = timezone.localdate()
    pendientes = (Cita.objects
                      .filter(fecha__gte=hoy, estado='pendiente')
                      .select_related('mascota', 'cliente', 'veterinario', 'tipo_atencion'))

    stats = estadisticas()
    evaluadas = []
    for cita in pendientes:
        puntaje, nivel, accion, detalle = puntuar(cita, stats)
        evaluadas.append({
            'cita': cita,
            'puntaje': puntaje,
            'nivel': nivel,
            'accion': accion,
            'detalle': detalle,
        })

    evaluadas.sort(key=lambda e: -e['puntaje'])

    return render(request, 'core/riesgo.html', {
        'seccion': 'riesgo',
        'evaluadas': evaluadas,
        'altos': sum(1 for e in evaluadas if e['nivel'] == 'alto'),
        'medios': sum(1 for e in evaluadas if e['nivel'] == 'medio'),
        'bajos': sum(1 for e in evaluadas if e['nivel'] == 'bajo'),
    })


@login_required
def indicadores(request):
    """Análisis de las inasistencias, factor por factor del modelo de riesgo."""

    hoy = timezone.localdate()

    # Se traen todas de una vez y el resto del cálculo se hace en Python.
    # Son poco más de 200 citas: cabe de sobra en memoria y evita decenas
    # de consultas separadas contra la base de datos.
    ocurridas = list(Cita.objects
                     .filter(fecha__lt=hoy)
                     .exclude(estado='pendiente')
                     .select_related('tipo_atencion', 'cliente'))

    def resumen(grupo):
        """Cuenta total, faltas, tasa y plata perdida de un grupo de citas."""
        faltas = [c for c in grupo if c.estado == 'no_asistio']
        perdido = sum(c.tipo_atencion.precio for c in faltas)
        return {
            'total': len(grupo),
            'faltas': len(faltas),
            'tasa': round(len(faltas) / len(grupo) * 100, 1) if grupo else 0,
            'perdido': perdido,
            # El monto se arma acá, con punto como separador de miles, que es
            # como se escriben los pesos en Chile. El filtro intcomma de Django
            # depende del idioma configurado y deja espacios en vez de puntos.
            'perdido_txt': f"{perdido:,}".replace(",", "."),
        }

    def escalar(filas):
        """Agrega el ancho de la barra, en porcentaje de la mayor."""
        tope = max([f['tasa'] for f in filas] + [1])
        for f in filas:
            f['ancho'] = round(f['tasa'] / tope * 100)
        return filas

    # ---------- Por tipo de atención (peso 20 en el modelo) ----------
    tipos = {}
    for c in ocurridas:
        tipos.setdefault(c.tipo_atencion.nombre, []).append(c)

    por_tipo = escalar(sorted(
        [dict(nombre=n, **resumen(g)) for n, g in tipos.items()],
        key=lambda f: -f['tasa']))

    # ---------- Por anticipación (peso 20 en el modelo) ----------
    TRAMOS = [(1, 3, '1 a 3 días'), (4, 7, '4 a 7 días'),
              (8, 14, '8 a 14 días'), (15, 99, '15 días o más')]

    por_anticipacion = escalar([
        dict(nombre=etiqueta,
             **resumen([c for c in ocurridas
                        if desde <= c.dias_anticipacion <= hasta]))
        for desde, hasta, etiqueta in TRAMOS])

    # ---------- Tutores reincidentes (peso 40, el más alto) ----------
    tutores = {}
    for c in ocurridas:
        tutores.setdefault(c.cliente, []).append(c)

    reincidentes = sorted(
        [dict(nombre=d.nombre_completo, **resumen(g))
         for d, g in tutores.items()],
        key=lambda f: (-f['faltas'], -f['tasa']))[:8]

    return render(request, 'core/indicadores.html', {
        'seccion': 'indicadores',
        'por_tipo': por_tipo,
        'por_anticipacion': por_anticipacion,
        'reincidentes': reincidentes,
        'general': resumen(ocurridas),
    })
