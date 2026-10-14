"""Migración de datos: tipos de mascota y paso de dueños a clientes.

1. Los tipos Perro y Gato pasan a llamarse Canino y Felino, y se agregan
   los demás tipos de animales que atiende una clínica.
2. Cada dueño (que antes era un usuario del sistema) pasa a ser un Cliente
   con RUT, y queda como responsable principal de sus mascotas.
"""

from django.db import migrations

RENOMBRAR = {'Perro': 'Canino', 'Gato': 'Felino'}
TIPOS = ['Canino', 'Felino', 'Ave', 'Roedor', 'Conejo', 'Reptil', 'Otro']

# RUTs de los clientes de prueba (los mismos que usa cargar_demo).
RUTS_DEMO = {
    'jperez': '15234871-1', 'msilva': '16890342-1', 'crivas': '18456213-8',
    'psoto': '12987654-9', 'dmunoz': '17345098-2', 'rtapia': '13678452-8',
    'vcastro': '19023876-8', 'imorales': '14567309-7', 'fvega': '20134765-3',
    'aleiva': '11876234-7',
}


def calcular_dv(cuerpo):
    suma, factor = 0, 2
    for digito in reversed(str(cuerpo)):
        suma += int(digito) * factor
        factor = 2 if factor == 7 else factor + 1
    resultado = 11 - suma % 11
    return {11: '0', 10: 'K'}.get(resultado, str(resultado))


def adelante(apps, schema_editor):
    Especie = apps.get_model('mascotas', 'Especie')
    Mascota = apps.get_model('mascotas', 'Mascota')
    Cliente = apps.get_model('mascotas', 'Cliente')
    Tenencia = apps.get_model('mascotas', 'Tenencia')

    # 1. Tipos de mascota
    for viejo, nuevo in RENOMBRAR.items():
        if not Especie.objects.filter(nombre=nuevo).exists():
            Especie.objects.filter(nombre=viejo).update(nombre=nuevo)
    for nombre in TIPOS:
        Especie.objects.get_or_create(nombre=nombre)

    # 2. Dueños -> clientes
    clientes = {}
    for mascota in Mascota.objects.exclude(dueno=None).select_related('dueno'):
        usuario = mascota.dueno
        if usuario.pk not in clientes:
            # Quien no es de los datos de prueba recibe un RUT provisorio
            # válido, para completar después con el real.
            rut = RUTS_DEMO.get(usuario.username)
            if rut is None:
                cuerpo = 30_000_000 + usuario.pk
                rut = f'{cuerpo}-{calcular_dv(cuerpo)}'
            clientes[usuario.pk], _ = Cliente.objects.get_or_create(rut=rut, defaults={
                'nombres': usuario.first_name or usuario.username,
                'apellidos': usuario.last_name,
                'email': usuario.email,
            })
        Tenencia.objects.get_or_create(
            cliente=clientes[usuario.pk], mascota=mascota,
            defaults={'relacion': 'dueno', 'es_principal': True})


def atras(apps, schema_editor):
    Especie = apps.get_model('mascotas', 'Especie')
    Mascota = apps.get_model('mascotas', 'Mascota')
    Tenencia = apps.get_model('mascotas', 'Tenencia')
    User = apps.get_model('auth', 'User')

    # El dueño vuelve a ser el usuario con el mismo nombre de pila, si existe.
    for t in Tenencia.objects.filter(es_principal=True).select_related('cliente', 'mascota'):
        usuario = User.objects.filter(first_name=t.cliente.nombres,
                                      last_name=t.cliente.apellidos).first()
        if usuario:
            Mascota.objects.filter(pk=t.mascota_id).update(dueno=usuario)
    for viejo, nuevo in RENOMBRAR.items():
        Especie.objects.filter(nombre=nuevo).update(nombre=viejo)


class Migration(migrations.Migration):

    dependencies = [
        ('mascotas', '0002_clientes_y_tenencias'),
    ]

    operations = [
        migrations.RunPython(adelante, atras),
    ]
