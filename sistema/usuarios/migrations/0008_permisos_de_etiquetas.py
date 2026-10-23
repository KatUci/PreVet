"""Permisos del catálogo de etiquetas de alerta.

Administración mantiene el catálogo. Recepción y Veterinarios solo lo ven:
asignar una etiqueta a un cliente o a una mascota se controla con el permiso
de modificar ese cliente o esa mascota.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

REPARTO = {
    'Recepción': ['view_etiqueta'],
    'Veterinarios': ['view_etiqueta'],
    'Administración': ['view_etiqueta', 'add_etiqueta', 'change_etiqueta', 'delete_etiqueta'],
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
        ('usuarios', '0007_permisos_de_atencion'),
        ('mascotas', '0011_etiquetas_de_alerta'),
    ]

    operations = [
        migrations.RunPython(repartir, migrations.RunPython.noop),
    ]
