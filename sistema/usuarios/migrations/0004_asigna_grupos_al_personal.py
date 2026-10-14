"""Al personal que ya existía sin grupos le asigna el grupo de su rol.

Solo toca a quienes no tienen ningún grupo, así que no deshace
asignaciones hechas a mano.
"""

from django.db import migrations

GRUPO_POR_ROL = {
    'veterinario': 'Veterinarios',
    'recepcionista': 'Recepción',
    'admin': 'Administración',
}


def asignar(apps, schema_editor):
    Perfil = apps.get_model('usuarios', 'Perfil')
    Group = apps.get_model('auth', 'Group')
    grupos = {g.name: g for g in Group.objects.filter(name__in=GRUPO_POR_ROL.values())}

    for perfil in Perfil.objects.filter(rol__in=GRUPO_POR_ROL).select_related('usuario'):
        usuario = perfil.usuario
        grupo = grupos.get(GRUPO_POR_ROL[perfil.rol])
        if grupo and not usuario.groups.exists():
            usuario.groups.add(grupo)


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0003_grupos_iniciales'),
    ]

    operations = [
        migrations.RunPython(asignar, migrations.RunPython.noop),
    ]
