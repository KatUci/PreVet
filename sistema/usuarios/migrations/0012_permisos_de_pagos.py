"""Permisos de los pagos.

- Recepción: cobra y ve los pagos.
- Administración: todos los permisos, para corregir un pago mal registrado.
- Veterinarios: no manejan los cobros.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

REPARTO = {
    'Recepción': ['view_pago', 'add_pago'],
    'Administración': ['view_pago', 'add_pago', 'change_pago', 'delete_pago'],
}


def repartir(apps, schema_editor):
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None

    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    for nombre, codenames in REPARTO.items():
        grupo = Group.objects.filter(name=nombre).first()
        if grupo:
            grupo.permissions.add(*Permission.objects.filter(
                content_type__app_label='citas', codename__in=codenames))


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0011_permiso_importar_datos'),
        ('citas', '0014_pagos'),
    ]

    operations = [
        migrations.RunPython(repartir, migrations.RunPython.noop),
    ]
