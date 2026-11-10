"""Permisos de los mensajes de WhatsApp editables.

Solo Administración puede cambiar los textos que se envían a los tutores.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

REPARTO = {
    'Administración': ['view_plantillamensaje', 'add_plantillamensaje', 'change_plantillamensaje'],
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
        ('usuarios', '0009_permisos_de_vacunas'),
        ('citas', '0012_plantillas_de_mensajes'),
    ]

    operations = [
        migrations.RunPython(repartir, migrations.RunPython.noop),
    ]
