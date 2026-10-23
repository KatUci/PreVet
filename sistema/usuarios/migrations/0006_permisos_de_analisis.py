"""Reparte los permisos nuevos de las pantallas de análisis.

- Horas en riesgo: Recepción (es quien llama para confirmar) y Administración.
- Indicadores: Administración (incluyen montos de ingresos perdidos).
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

REPARTO = {
    'Recepción': ['ver_riesgo'],
    'Administración': ['ver_riesgo', 'ver_indicadores'],
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
        ('usuarios', '0005_permisos_de_clientes'),
        ('citas', '0006_permisos_de_analisis'),
    ]

    operations = [
        migrations.RunPython(repartir, migrations.RunPython.noop),
    ]
