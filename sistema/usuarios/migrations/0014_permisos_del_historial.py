"""Permiso para ver el historial de cambios de las citas (PV-ADM-05).

- Administración: ve quién cambió cada cita, qué cambió y cuándo.
- Nadie puede editar ni borrar el historial: se escribe solo.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

REPARTO = {
    'Administración': ['view_cambiocita'],
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
        ('usuarios', '0013_permisos_de_pesos'),
        ('citas', '0016_historial_de_cambios'),
    ]

    operations = [
        migrations.RunPython(repartir, migrations.RunPython.noop),
    ]
