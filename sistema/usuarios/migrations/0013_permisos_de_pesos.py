"""Permisos de los pesos del modelo de riesgo (PV-RIE-04).

- Administración: ve y ajusta los pesos.
- Recepción y Veterinarios: no los cambian; el modelo los usa igual para ellos.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

REPARTO = {
    'Administración': ['view_pesosmodelo', 'change_pesosmodelo'],
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
        ('usuarios', '0012_permisos_de_pagos'),
        ('citas', '0015_pesos_del_modelo'),
    ]

    operations = [
        migrations.RunPython(repartir, migrations.RunPython.noop),
    ]
