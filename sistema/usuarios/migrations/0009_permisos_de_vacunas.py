"""Reparte los permisos del carnet de vacunas.

- Veterinarios: registran las vacunas y las ven.
- Recepción: solo las ve, para recordarle al tutor la próxima dosis.
- Administración: todos los permisos.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

REPARTO = {
    'Veterinarios': ['view_vacuna', 'add_vacuna', 'change_vacuna'],
    'Recepción': ['view_vacuna'],
    'Administración': ['view_vacuna', 'add_vacuna', 'change_vacuna', 'delete_vacuna'],
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
        ('usuarios', '0008_permisos_de_etiquetas'),
        ('mascotas', '0013_vacunas'),
    ]

    operations = [
        migrations.RunPython(repartir, migrations.RunPython.noop),
    ]
