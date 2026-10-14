"""Cada cita existente queda a nombre del responsable principal de la mascota."""

from django.db import migrations


def llenar(apps, schema_editor):
    Cita = apps.get_model('citas', 'Cita')
    Tenencia = apps.get_model('mascotas', 'Tenencia')

    responsable = dict(Tenencia.objects.filter(es_principal=True)
                       .values_list('mascota_id', 'cliente_id'))
    for mascota_id, cliente_id in responsable.items():
        Cita.objects.filter(mascota_id=mascota_id, cliente=None).update(cliente_id=cliente_id)


class Migration(migrations.Migration):

    dependencies = [
        ('citas', '0003_cita_cliente'),
    ]

    operations = [
        migrations.RunPython(llenar, migrations.RunPython.noop),
    ]
