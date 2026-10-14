"""Crea los tres grupos de permisos con los que parte la clínica.

Es una migración de datos: no cambia tablas, agrega filas. Así los grupos
existen en cualquier base de datos donde se corra `migrate`, sin tener que
crearlos a mano. Después se pueden ajustar desde el sistema.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

# Qué puede hacer cada grupo, por modelo: ver, agregar, modificar, eliminar.
GRUPOS = {
    'Veterinarios': {
        'cita': ['view', 'change'],
        'mascota': ['view', 'change'],
        'especie': ['view'],
        'raza': ['view'],
        'tipoatencion': ['view'],
        'horarioatencion': ['view'],
    },
    'Recepción': {
        'cita': ['view', 'add', 'change'],
        'mascota': ['view', 'add', 'change'],
        'especie': ['view'],
        'raza': ['view'],
        'tipoatencion': ['view'],
        'horarioatencion': ['view'],
    },
}

# Administración recibe todos los permisos de estas aplicaciones.
APPS_ADMINISTRACION = ['citas', 'mascotas', 'usuarios']


def crear_grupos(apps, schema_editor):
    # Los permisos de Django se crean recién al terminar todas las
    # migraciones. Se fuerzan aquí para poder asignarlos.
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None

    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    for nombre, modelos in GRUPOS.items():
        grupo, _ = Group.objects.get_or_create(name=nombre)
        codenames = [f'{accion}_{modelo}'
                     for modelo, acciones in modelos.items() for accion in acciones]
        grupo.permissions.set(Permission.objects.filter(
            codename__in=codenames,
            content_type__app_label__in=['citas', 'mascotas'],
        ))

    admin, _ = Group.objects.get_or_create(name='Administración')
    admin.permissions.set(Permission.objects.filter(
        content_type__app_label__in=APPS_ADMINISTRACION))


def borrar_grupos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=[*GRUPOS, 'Administración']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0002_personal_y_grupos'),
        ('citas', '0002_alter_cita_veterinario'),
        ('mascotas', '0001_initial'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RunPython(crear_grupos, borrar_grupos),
    ]
