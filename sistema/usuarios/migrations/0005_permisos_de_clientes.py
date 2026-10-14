"""Suma a los grupos los permisos de los modelos nuevos: Cliente y Tenencia."""

from django.contrib.auth.management import create_permissions
from django.db import migrations

NUEVOS = {
    'Recepción': ['view_cliente', 'add_cliente', 'change_cliente',
                  'view_tenencia', 'add_tenencia', 'change_tenencia'],
    'Veterinarios': ['view_cliente', 'view_tenencia'],
}


def agregar(apps, schema_editor):
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None

    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    for nombre, codenames in NUEVOS.items():
        grupo = Group.objects.filter(name=nombre).first()
        if grupo:
            grupo.permissions.add(*Permission.objects.filter(
                content_type__app_label='mascotas', codename__in=codenames))

    admin = Group.objects.filter(name='Administración').first()
    if admin:
        admin.permissions.add(*Permission.objects.filter(content_type__app_label='mascotas'))


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0004_asigna_grupos_al_personal'),
        ('mascotas', '0004_remove_mascota_dueno'),
    ]

    operations = [
        migrations.RunPython(agregar, migrations.RunPython.noop),
    ]
