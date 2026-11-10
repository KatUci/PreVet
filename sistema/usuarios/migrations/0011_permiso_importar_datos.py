"""Permiso para importar los datos de la clínica desde Excel.

Solo Administración carga clientes, mascotas y citas históricas.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

REPARTO = {
    'Administración': ['importar_datos'],
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
                content_type__app_label='mascotas', codename__in=codenames))


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0010_permisos_de_mensajes'),
        ('mascotas', '0014_permiso_importar_datos'),
    ]

    operations = [
        migrations.RunPython(repartir, migrations.RunPython.noop),
    ]
