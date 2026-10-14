"""Validación y formato del RUT chileno.

El RUT se guarda limpio, sin puntos y con guion: 12345678-5.
Se muestra con puntos: 12.345.678-5.
"""

import re

from django.core.exceptions import ValidationError


def calcular_dv(cuerpo):
    """Dígito verificador por módulo 11: multiplica los dígitos de derecha a
    izquierda por 2, 3, 4, 5, 6, 7, 2, 3..., suma, y resta a 11 el resto."""
    suma, factor = 0, 2
    for digito in reversed(str(cuerpo)):
        suma += int(digito) * factor
        factor = 2 if factor == 7 else factor + 1
    resultado = 11 - suma % 11
    return {11: '0', 10: 'K'}.get(resultado, str(resultado))


def limpiar_rut(rut):
    """'12.345.678-k' -> '12345678-K'. No valida, solo ordena el texto."""
    texto = re.sub(r'[^0-9kK]', '', str(rut or '')).upper()
    if len(texto) < 2:
        return texto
    return f'{texto[:-1]}-{texto[-1]}'


def validar_rut(rut):
    """Lanza ValidationError si el RUT no existe o está mal escrito."""
    limpio = limpiar_rut(rut)
    if not re.fullmatch(r'\d{7,8}-[0-9K]', limpio):
        raise ValidationError('Escribe el RUT completo, con su dígito verificador. Ej: 12.345.678-5.')

    cuerpo, dv = limpio.split('-')
    if calcular_dv(cuerpo) != dv:
        raise ValidationError('El RUT no es válido: el dígito verificador no corresponde.')


def formatear_rut(rut):
    """'12345678-5' -> '12.345.678-5'."""
    limpio = limpiar_rut(rut)
    if '-' not in limpio:
        return limpio
    cuerpo, dv = limpio.split('-')
    return f'{int(cuerpo):,}'.replace(',', '.') + f'-{dv}'
