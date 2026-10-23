"""Carga las etiquetas de alerta con las que parte la clínica.

Administración puede agregar, cambiar o desactivar etiquetas después, desde
Configuración.
"""
from django.db import migrations

INICIALES = [
    # (nombre, para, tono)
    ('Muerde: usar bozal', 'mascota', 'mal'),
    ('Posible contagio: aislar', 'mascota', 'mal'),
    ('Nervioso', 'mascota', 'warn'),
    ('Paciente geriátrico', 'mascota', 'warn'),
    ('Paciente crónico', 'mascota', 'warn'),
    ('Deuda pendiente', 'cliente', 'mal'),
    ('Confirmar por teléfono', 'cliente', 'warn'),
    ('Suele llegar tarde', 'cliente', 'warn'),
    ('Cliente frecuente', 'cliente', 'neutro'),
]


def cargar(apps, schema_editor):
    Etiqueta = apps.get_model('mascotas', 'Etiqueta')
    for nombre, para, tono in INICIALES:
        Etiqueta.objects.get_or_create(nombre=nombre, defaults={'para': para, 'tono': tono})


def quitar(apps, schema_editor):
    apps.get_model('mascotas', 'Etiqueta').objects.filter(
        nombre__in=[n for n, _, _ in INICIALES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mascotas', '0011_etiquetas_de_alerta'),
    ]

    operations = [
        migrations.RunPython(cargar, quitar),
    ]
