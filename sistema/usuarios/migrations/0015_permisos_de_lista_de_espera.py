"""Permisos de la lista de espera (PV-REC-01).

- Recepción y Administración: anotan, agendan y descartan a quienes esperan una hora.
- Veterinarios: no manejan la agenda.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

REPARTO = {
    'Recepción': ['view_esperahora', 'add_esperahora', 'change_esperahora'],
    'Administración': ['view_esperahora', 'add_esperahora', 'change_esperahora', 'delete_esperahora'],
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
        ('usuarios', '0014_permisos_del_historial'),
        ('citas', '0017_lista_de_espera'),
    ]

    operations = [
        migrations.RunPython(repartir, migrations.RunPython.noop),
    ]
