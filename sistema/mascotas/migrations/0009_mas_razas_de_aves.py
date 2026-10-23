"""Agrega más aves frecuentes en clínicas (guacamayos, loros, aves de corral, etc.).

Solo agrega las que no existen, igual que la 0006.
"""
from django.db import migrations

AVES = [
    'Amazona', 'Caique', 'Codorniz', 'Conuro', 'Diamante de Gould', 'Eclectus',
    'Ganso', 'Guacamayo', 'Guacamayo azul y amarillo', 'Guacamayo rojo', 'Lori arcoíris', 'Loro gris africano',
    'Paloma', 'Pato', 'Pavo', 'Pinzón cebra', 'Tórtola', 'Tucán',
]


def cargar(apps, schema_editor):
    Especie = apps.get_model('mascotas', 'Especie')
    Raza = apps.get_model('mascotas', 'Raza')
    ave, _ = Especie.objects.get_or_create(nombre='Ave')
    existentes = {n.lower() for n in Raza.objects.filter(especie=ave).values_list('nombre', flat=True)}
    Raza.objects.bulk_create([Raza(especie=ave, nombre=n) for n in AVES if n.lower() not in existentes])


class Migration(migrations.Migration):

    dependencies = [('mascotas', '0008_tiene_microchip')]

    operations = [migrations.RunPython(cargar, migrations.RunPython.noop)]
