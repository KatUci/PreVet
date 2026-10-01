import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from usuarios.models import Perfil
from mascotas.models import Especie, Raza, Mascota
from citas.models import TipoAtencion, HorarioAtencion, Cita

BLOQUES = ['09:00', '09:30', '10:00', '10:30', '11:00', '11:30', '12:00', '12:30',
           '15:00', '15:30', '16:00', '16:30', '17:00', '17:30', '18:00', '18:30']

VETERINARIOS = [('paz.herrera', 'Paz', 'Herrera'),
                ('luis.contreras', 'Luis', 'Contreras')]

DUENOS = [('jperez', 'Javiera', 'Pérez'), ('msilva', 'Matías', 'Silva'),
          ('crivas', 'Camila', 'Rivas'), ('psoto', 'Pablo', 'Soto'),
          ('dmunoz', 'Daniela', 'Muñoz'), ('rtapia', 'Rodrigo', 'Tapia'),
          ('vcastro', 'Valentina', 'Castro'), ('imorales', 'Ignacio', 'Morales'),
          ('fvega', 'Fernanda', 'Vega'), ('aleiva', 'Andrés', 'Leiva')]

MASCOTAS = [('Michi', 'Gato'), ('Koda', 'Perro'), ('Luna', 'Perro'), ('Simba', 'Gato'),
            ('Rocky', 'Perro'), ('Nala', 'Gato'), ('Toby', 'Perro'), ('Pelusa', 'Gato'),
            ('Max', 'Perro'), ('Mia', 'Gato'), ('Bruno', 'Perro'), ('Kira', 'Perro'),
            ('Copito', 'Gato'), ('Thor', 'Perro'), ('Lola', 'Perro')]

ATENCIONES = [('Consulta general', 30, 25000), ('Vacunación', 20, 15000),
              ('Control', 20, 18000), ('Urgencia', 40, 45000),
              ('Examen de sangre', 30, 35000)]


class Command(BaseCommand):
    help = "Carga datos de ejemplo para el demo de PreVet"

    def handle(self, *args, **opciones):
        random.seed(42)

        self.stdout.write("Borrando citas anteriores...")
        Cita.objects.all().delete()

        # --- personas ---
        vets = []
        for username, nombre, apellido in VETERINARIOS:
            u, _ = User.objects.get_or_create(
                username=username,
                defaults={'first_name': nombre, 'last_name': apellido})
            Perfil.objects.get_or_create(usuario=u, defaults={'rol': 'veterinario'})
            vets.append(u)

        duenos = []
        for username, nombre, apellido in DUENOS:
            u, _ = User.objects.get_or_create(
                username=username,
                defaults={'first_name': nombre, 'last_name': apellido})
            Perfil.objects.get_or_create(usuario=u, defaults={'rol': 'dueno'})
            duenos.append(u)

        # --- catálogos ---
        especies = {}
        for nombre in ('Perro', 'Gato'):
            especies[nombre], _ = Especie.objects.get_or_create(nombre=nombre)

        for esp, razas in (('Perro', ['Quiltro', 'Labrador', 'Poodle']),
                           ('Gato', ['Mestizo', 'Siamés'])):
            for r in razas:
                Raza.objects.get_or_create(especie=especies[esp], nombre=r)

        tipos = []
        for nombre, dur, precio in ATENCIONES:
            t, _ = TipoAtencion.objects.get_or_create(
                nombre=nombre,
                defaults={'duracion_minutos': dur, 'precio': precio})
            tipos.append(t)

        # --- horarios ---
        for v in vets:
            for dia in range(5):
                HorarioAtencion.objects.get_or_create(
                    veterinario=v, dia_semana=dia, hora_inicio='09:00',
                    defaults={'hora_fin': '13:00'})
                HorarioAtencion.objects.get_or_create(
                    veterinario=v, dia_semana=dia, hora_inicio='15:00',
                    defaults={'hora_fin': '19:00'})

        # --- mascotas ---
        mascotas = []
        for i, (nombre, esp) in enumerate(MASCOTAS):
            m, _ = Mascota.objects.get_or_create(
                nombre=nombre,
                dueno=duenos[i % len(duenos)],
                defaults={
                    'especie': especies[esp],
                    'sexo': random.choice(['macho', 'hembra']),
                })
            mascotas.append(m)

        # --- citas ---
        hoy = timezone.localdate()
        ranuras = []
        for delta in range(-90, 22):
            dia = hoy + timedelta(days=delta)
            if dia.weekday() >= 5:
                continue
            for v in vets:
                for b in BLOQUES:
                    ranuras.append((v, dia, b))
        random.shuffle(ranuras)

        pasadas = [r for r in ranuras if r[1] < hoy][:220]
        futuras = [r for r in ranuras if r[1] >= hoy][:35]

        creadas = 0
        for vet, dia, bloque in pasadas + futuras:
            if dia < hoy:
                estado = random.choices(
                    ['completada', 'no_asistio', 'cancelada'],
                    weights=[70, 18, 12])[0]
            else:
                estado = 'pendiente'

            cita = Cita.objects.create(
                veterinario=vet,
                mascota=random.choice(mascotas),
                tipo_atencion=random.choice(tipos),
                fecha=dia,
                hora=bloque,
                estado=estado,
            )

            # La anticipación de la reserva es una variable predictora,
            # así que la generamos explícitamente.
            anticipacion = random.randint(1, 21)
            reservada = timezone.make_aware(
                timezone.datetime.combine(dia - timedelta(days=anticipacion),
                                          timezone.datetime.min.time()))
            Cita.objects.filter(pk=cita.pk).update(fecha_creacion=reservada)

            if estado == 'no_asistio':
                Cita.objects.filter(pk=cita.pk).update(
                    fecha_marcada_no_asistio=reservada + timedelta(days=anticipacion))
            elif estado == 'cancelada':
                Cita.objects.filter(pk=cita.pk).update(
                    cancelada_por=random.choice(duenos),
                    fecha_cancelacion=reservada + timedelta(days=1))
            creadas += 1

        self.stdout.write(self.style.SUCCESS(
            f"Listo: {creadas} citas, {len(mascotas)} mascotas, "
            f"{len(vets)} veterinarios, {len(tipos)} tipos de atención."))