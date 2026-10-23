"""Carga las razas más frecuentes en Chile para cada tipo de mascota.

Es una migración de datos: solo agrega filas que no existan, así se puede
correr en cualquier base (la compartida o la de cada computador) sin
duplicar nada. Las razas se pueden seguir editando desde Configuración.
"""
from django.db import migrations

RAZAS = {
    'Canino': [
        'Akita Inu', 'American Staffordshire Terrier', 'Basset Hound', 'Beagle', 'Bichón Frisé', 'Border Collie',
        'Boston Terrier', 'Boxer', 'Bull Terrier', 'Bulldog Francés', 'Bulldog Inglés',
        'Cavalier King Charles Spaniel', 'Chihuahua', 'Chow Chow', 'Cocker Spaniel', 'Collie', 'Dachshund (salchicha)',
        'Dálmata', 'Dóberman', 'Dogo Argentino', 'Fox Terrier', 'Galgo', 'Golden Retriever', 'Gran Danés',
        'Husky Siberiano', 'Jack Russell Terrier', 'Labrador', 'Lhasa Apso', 'Maltés', 'Mestizo', 'Pastor Alemán',
        'Pastor Australiano', 'Pastor Belga Malinois', 'Pekinés', 'Pitbull', 'Pomerania', 'Poodle', 'Pug',
        'Quiltro', 'Rottweiler', 'Samoyedo', 'San Bernardo', 'Schnauzer', 'Shiba Inu', 'Shih Tzu', 'Weimaraner',
        'West Highland White Terrier', 'Yorkshire Terrier',
    ],
    'Felino': [
        'Abisinio', 'Angora Turco', 'Azul Ruso', 'Bengalí', 'Bosque de Noruega', 'British Shorthair', 'Burmés',
        'Devon Rex', 'Europeo común', 'Exótico de pelo corto', 'Himalayo', 'Maine Coon', 'Mestizo', 'Persa',
        'Ragdoll', 'Sagrado de Birmania', 'Scottish Fold', 'Siamés', 'Sphynx',
    ],
    'Ave': ['Agapornis', 'Cacatúa', 'Canario', 'Cotorra', 'Diamante mandarín', 'Gallina', 'Jilguero', 'Loro',
            'Ninfa', 'Periquito australiano'],
    'Roedor': ['Chinchilla', 'Cuy', 'Degú', 'Hámster', 'Hámster ruso', 'Jerbo', 'Rata doméstica', 'Ratón'],
    'Conejo': ['Angora', 'Belier', 'Cabeza de león', 'Holandés enano', 'Mestizo', 'Mini lop', 'Rex'],
    'Reptil': ['Camaleón', 'Dragón barbudo', 'Gecko leopardo', 'Iguana', 'Pitón bola', 'Tortuga',
               'Tortuga de agua'],
    'Otro': ['Erizo de tierra', 'Hurón', 'Pez'],
}


def cargar(apps, schema_editor):
    Especie = apps.get_model('mascotas', 'Especie')
    Raza = apps.get_model('mascotas', 'Raza')
    for tipo, razas in RAZAS.items():
        especie, _ = Especie.objects.get_or_create(nombre=tipo)
        existentes = {n.lower() for n in Raza.objects.filter(especie=especie).values_list('nombre', flat=True)}
        Raza.objects.bulk_create([Raza(especie=especie, nombre=r) for r in razas if r.lower() not in existentes])


class Migration(migrations.Migration):

    dependencies = [('mascotas', '0005_fotos_de_mascotas')]

    # Al deshacer no se borra nada: podría haber mascotas usando estas razas.
    operations = [migrations.RunPython(cargar, migrations.RunPython.noop)]
