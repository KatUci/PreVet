"""Importar los datos reales de la clínica desde Excel o CSV.

- PV-DAT-01: clientes y sus mascotas (una fila por mascota).
- PV-DAT-02: citas históricas con su estado (asistió, no asistió o cancelada),
  para que el modelo de riesgo parta con el historial real de cada tutor.

Las filas con errores se saltan y se informan con su número, para corregirlas
en el archivo. Lo que ya existe no se vuelve a crear, así que se puede
importar el mismo archivo de nuevo sin duplicar nada.
"""
import csv
import datetime
import io
import unicodedata

from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from citas.models import Cita, TipoAtencion
from mascotas.models import Cliente, Especie, Mascota, Tenencia
from mascotas.rut import limpiar_rut, validar_rut

TAMANO_MAXIMO = 2 * 1024 * 1024     # 2 MB
MAXIMO_FILAS = 5000
ERRORES_A_MOSTRAR = 50

FORMATOS = {
    'clientes': {
        'titulo': 'Clientes y mascotas',
        'columnas': ['RUT', 'Nombres', 'Apellidos', 'Teléfono', 'Correo',
                     'Mascota', 'Tipo de mascota', 'Sexo', 'Fecha de nacimiento'],
        'obligatorias': ['RUT', 'Nombres', 'Apellidos'],
        'ejemplo': ['12.345.678-5', 'Ana', 'Soto Pérez', '912345678', 'ana@correo.cl',
                    'Bruno', 'Perro', 'Macho', '15-03-2020'],
    },
    'citas': {
        'titulo': 'Citas históricas',
        'columnas': ['RUT', 'Mascota', 'Fecha', 'Hora', 'Profesional', 'Tipo de atención', 'Estado'],
        'obligatorias': ['RUT', 'Mascota', 'Fecha', 'Hora', 'Profesional', 'Tipo de atención', 'Estado'],
        'ejemplo': ['12.345.678-5', 'Bruno', '02-09-2026', '10:30', 'Paz Herrera', 'Control', 'No asistió'],
    },
}

# Cómo puede venir escrito el estado en el archivo de la clínica.
ESTADOS = {
    'asistio': 'completada',
    'atendida': 'completada',
    'completada': 'completada',
    'no asistio': 'no_asistio',
    'cancelada': 'cancelada',
    'pendiente': 'pendiente',
}


def normalizar(texto):
    """'  Teléfono ' -> 'telefono': sin tildes, en minúscula y sin espacios de más."""
    texto = unicodedata.normalize('NFKD', str(texto or ''))
    texto = ''.join(letra for letra in texto if not unicodedata.combining(letra))
    return ' '.join(texto.lower().split())


def leer_archivo(archivo):
    """Devuelve el encabezado y las filas (cada una como dict) del Excel o CSV."""
    nombre = archivo.name.lower()
    if nombre.endswith('.xlsx'):
        from openpyxl import load_workbook
        hoja = load_workbook(archivo, read_only=True, data_only=True).active
        filas = [list(fila) for fila in hoja.iter_rows(values_only=True)]
    elif nombre.endswith('.csv'):
        datos = archivo.read()
        try:
            texto = datos.decode('utf-8-sig')
        except UnicodeDecodeError:
            texto = datos.decode('latin-1')     # CSV guardado por Excel en Windows
        # El Excel en español separa con punto y coma; otros programas, con coma.
        primera = texto.split('\n')[0]
        separador = ';' if primera.count(';') >= primera.count(',') else ','
        filas = list(csv.reader(io.StringIO(texto), delimiter=separador))
    else:
        raise ValueError('El archivo debe ser Excel (.xlsx) o CSV (.csv).')

    if not filas:
        raise ValueError('El archivo está vacío.')
    encabezado = [normalizar(c) for c in filas[0]]
    resultado = []
    for fila in filas[1:]:
        if all(c is None or str(c).strip() == '' for c in fila):
            continue    # fila vacía
        resultado.append(dict(zip(encabezado, fila)))
    return encabezado, resultado


def texto(fila, columna):
    valor = fila.get(normalizar(columna))
    return '' if valor is None else str(valor).strip()


def leer_fecha(valor):
    if isinstance(valor, datetime.datetime):
        return valor.date()
    if isinstance(valor, datetime.date):
        return valor
    for formato in ('%d-%m-%Y', '%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.datetime.strptime(str(valor).strip(), formato).date()
        except ValueError:
            pass
    raise ValueError(f'la fecha «{valor}» no se entiende (usa día-mes-año, ej: 15-03-2020)')


def leer_hora(valor):
    if isinstance(valor, datetime.datetime):
        return valor.time()
    if isinstance(valor, datetime.time):
        return valor
    for formato in ('%H:%M', '%H:%M:%S'):
        try:
            return datetime.datetime.strptime(str(valor).strip(), formato).time()
        except ValueError:
            pass
    raise ValueError(f'la hora «{valor}» no se entiende (usa horas:minutos, ej: 10:30)')


def mensaje_de_error(error):
    if isinstance(error, ValidationError):
        return ' '.join(error.messages)
    return str(error)


# ---------------- PV-DAT-01: clientes y mascotas ----------------

def importar_clientes(filas):
    resultado = {'clientes': 0, 'mascotas': 0, 'citas': 0, 'omitidas': 0, 'errores': []}
    especies = {normalizar(e.nombre): e for e in Especie.objects.all()}

    for numero, fila in enumerate(filas, start=2):     # la fila 1 es el encabezado
        try:
            # Cada fila se guarda completa o no se guarda.
            with transaction.atomic():
                rut = texto(fila, 'RUT')
                validar_rut(rut)
                cliente = Cliente.objects.filter(rut=limpiar_rut(rut)).first()
                nuevo = cliente is None
                if nuevo:
                    cliente = Cliente(rut=rut, nombres=texto(fila, 'Nombres'), apellidos=texto(fila, 'Apellidos'),
                                      telefono=texto(fila, 'Teléfono'), email=texto(fila, 'Correo'))
                    cliente.full_clean()
                    cliente.save()
                    resultado['clientes'] += 1

                nombre_mascota = texto(fila, 'Mascota')
                if not nombre_mascota:
                    if not nuevo:
                        resultado['omitidas'] += 1
                    continue
                if cliente.mascotas.filter(nombre__iexact=nombre_mascota).exists():
                    resultado['omitidas'] += 1     # ya estaba registrada
                    continue

                tipo = texto(fila, 'Tipo de mascota')
                especie = especies.get(normalizar(tipo))
                if especie is None:
                    raise ValueError(f'el tipo de mascota «{tipo}» no existe en PreVet '
                                     f'(agrégalo en Configuración > Tipos de mascota)')
                sexo = normalizar(texto(fila, 'Sexo'))
                if sexo.startswith('m'):
                    sexo = 'macho'
                elif sexo.startswith('h'):
                    sexo = 'hembra'
                else:
                    raise ValueError('el sexo debe ser Macho o Hembra')
                nacimiento = fila.get(normalizar('Fecha de nacimiento'))
                # El microchip va vacío a propósito: la regla de microchip único
                # solo se aplica a los que tienen número.
                mascota = Mascota(nombre=nombre_mascota, especie=especie, sexo=sexo, microchip='',
                                  fecha_nacimiento=leer_fecha(nacimiento) if nacimiento else None)
                mascota.full_clean()
                mascota.save()
                Tenencia.objects.create(cliente=cliente, mascota=mascota, es_principal=True)
                resultado['mascotas'] += 1
        except (ValueError, ValidationError) as error:
            resultado['errores'].append(f'Fila {numero}: {mensaje_de_error(error)}')
    return resultado


# ---------------- PV-DAT-02: citas históricas ----------------

def importar_citas(filas):
    resultado = {'clientes': 0, 'mascotas': 0, 'citas': 0, 'omitidas': 0, 'errores': []}
    hoy = timezone.localdate()
    tipos = {normalizar(t.nombre): t for t in TipoAtencion.objects.all()}
    # El profesional se puede escribir con su usuario o con su nombre completo.
    profesionales = {}
    for vet in User.objects.filter(perfil__rol='veterinario'):
        profesionales[normalizar(vet.username)] = vet
        profesionales[normalizar(vet.get_full_name())] = vet

    for numero, fila in enumerate(filas, start=2):
        try:
            with transaction.atomic():
                rut = texto(fila, 'RUT')
                validar_rut(rut)
                cliente = Cliente.objects.filter(rut=limpiar_rut(rut)).first()
                if cliente is None:
                    raise ValueError(f'no hay ningún cliente con el RUT {rut} (impórtalo primero)')
                nombre_mascota = texto(fila, 'Mascota')
                mascota = cliente.mascotas.filter(nombre__iexact=nombre_mascota).first()
                if mascota is None:
                    raise ValueError(f'{cliente.nombre_completo} no tiene una mascota llamada «{nombre_mascota}»')

                fecha = leer_fecha(fila.get(normalizar('Fecha')))
                hora = leer_hora(fila.get(normalizar('Hora')))
                vet = profesionales.get(normalizar(texto(fila, 'Profesional')))
                if vet is None:
                    raise ValueError(f'el profesional «{texto(fila, "Profesional")}» no existe en PreVet')
                tipo = tipos.get(normalizar(texto(fila, 'Tipo de atención')))
                if tipo is None:
                    raise ValueError(f'el tipo de atención «{texto(fila, "Tipo de atención")}» no existe en PreVet')
                estado = ESTADOS.get(normalizar(texto(fila, 'Estado')))
                if estado is None:
                    raise ValueError('el estado debe ser Asistió, No asistió, Cancelada o Pendiente')
                if estado in ('completada', 'no_asistio') and fecha > hoy:
                    raise ValueError('una cita futura no puede estar marcada como atendida o inasistencia')

                # Si la cita ya está, no se duplica.
                repetida = Cita.objects.filter(veterinario=vet, fecha=fecha, hora=hora)
                if estado == 'cancelada':
                    repetida = repetida.filter(mascota=mascota, estado='cancelada')
                else:
                    repetida = repetida.exclude(estado='cancelada')
                if repetida.exists():
                    resultado['omitidas'] += 1
                    continue

                cita = Cita(veterinario=vet, mascota=mascota, cliente=cliente, tipo_atencion=tipo,
                            fecha=fecha, hora=hora, estado=estado)
                cita.full_clean(validate_unique=False, validate_constraints=False)
                cita.save()
                resultado['citas'] += 1
        except (ValueError, ValidationError) as error:
            resultado['errores'].append(f'Fila {numero}: {mensaje_de_error(error)}')
    return resultado


# ---------------- Pantallas ----------------

@login_required
@permission_required('mascotas.importar_datos', raise_exception=True)
def importar(request):
    resultado, error, tipo = None, None, request.POST.get('tipo')

    if request.method == 'POST':
        archivo = request.FILES.get('archivo')
        if tipo not in FORMATOS:
            error = 'Elige qué quieres importar.'
        elif archivo is None:
            error = 'Elige el archivo Excel o CSV.'
        elif archivo.size > TAMANO_MAXIMO:
            error = 'El archivo pesa más de 2 MB. Divídelo en partes más chicas.'
        else:
            try:
                encabezado, filas = leer_archivo(archivo)
            except ValueError as e:
                error = str(e)
            except Exception:
                # Un archivo dañado o que no es Excel de verdad.
                error = 'No se pudo leer el archivo. Revisa que sea un Excel (.xlsx) o CSV válido.'
            else:
                faltan = [c for c in FORMATOS[tipo]['obligatorias'] if normalizar(c) not in encabezado]
                if faltan:
                    error = 'Al archivo le faltan las columnas: ' + ', '.join(faltan) + '. Usa la plantilla.'
                elif len(filas) > MAXIMO_FILAS:
                    error = f'El archivo tiene más de {MAXIMO_FILAS} filas. Divídelo en partes más chicas.'
                else:
                    if tipo == 'clientes':
                        resultado = importar_clientes(filas)
                    else:
                        resultado = importar_citas(filas)
                    resultado['total_errores'] = len(resultado['errores'])
                    resultado['errores'] = resultado['errores'][:ERRORES_A_MOSTRAR]
                    resultado['titulo'] = FORMATOS[tipo]['titulo']

    return render(request, 'core/importar.html', {
        'seccion': 'importar',
        'formatos': FORMATOS,
        'tipo': tipo,
        'resultado': resultado,
        'error': error,
    })


@login_required
@permission_required('mascotas.importar_datos', raise_exception=True)
def plantilla(request, tipo):
    """Excel vacío con las columnas y una fila de ejemplo."""
    if tipo not in FORMATOS:
        raise Http404
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    formato = FORMATOS[tipo]
    libro = Workbook()
    hoja = libro.active
    hoja.title = formato['titulo']
    hoja.append(formato['columnas'])
    hoja.append(formato['ejemplo'])
    for celda in hoja[1]:
        celda.font = Font(bold=True, color='FFFFFF')
        celda.fill = PatternFill('solid', fgColor='2B2160')
        hoja.column_dimensions[celda.column_letter].width = 20

    respuesta = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    respuesta['Content-Disposition'] = f'attachment; filename="plantilla_{tipo}_prevet.xlsx"'
    libro.save(respuesta)
    return respuesta
