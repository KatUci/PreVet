"""Reparte los permisos de la ficha clínica (modelo Atención).

- Veterinarios: registran la atención y ven el historial clínico.
- Administración: todos los permisos.
- Recepción: ninguno. El diagnóstico es información clínica y no la
  necesita para gestionar la agenda.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

REPARTO = {
    'Veterinarios': ['view_atencion', 'add_atencion', 'change_atencion'],
    'Administración': ['view_atencion', 'add_atencion', 'change_atencion', 'delete_atencion'],
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
        ('usuarios', '0006_permisos_de_analisis'),
        ('citas', '0008_atencion_clinica'),
    ]

    operations = [
        migrations.RunPython(repartir, migrations.RunPython.noop),
    ]
