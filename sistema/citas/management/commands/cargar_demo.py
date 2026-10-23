import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from usuarios.models import Perfil
from mascotas.models import Cliente, Especie, Raza, Mascota, Tenencia
from citas.models import TipoAtencion, HorarioAtencion, Cita

BLOQUES = ['09:00', '09:30', '10:00', '10:30', '11:00', '11:30', '12:00', '12:30',
           '15:00', '15:30', '16:00', '16:30', '17:00', '17:30', '18:00', '18:30']

VETERINARIOS = [('paz.herrera', 'Paz', 'Herrera'),
                ('luis.contreras', 'Luis', 'Contreras')]

# Profesionales que se incorporaron después del período analizado. Quedan en el
# sistema con su horario, y se les puede agendar de aquí en adelante, pero no
# participan del histórico: si se repartieran las citas pasadas entre cinco en
# vez de dos, los indicadores del informe dejarían de cuadrar.
VETERINARIOS_NUEVOS = [('carolina.fuentes', 'Carolina', 'Fuentes'),
                       ('sebastian.rios', 'Sebastián', 'Ríos'),
                       ('antonia.lagos', 'Antonia', 'Lagos')]

# Clientes de la clínica, con RUT válido. No son usuarios del sistema.
CLIENTES = [('15234871-1', 'Javiera', 'Pérez'), ('16890342-1', 'Matías', 'Silva'),
            ('18456213-8', 'Camila', 'Rivas'), ('12987654-9', 'Pablo', 'Soto'),
            ('17345098-2', 'Daniela', 'Muñoz'), ('13678452-8', 'Rodrigo', 'Tapia'),
            ('19023876-8', 'Valentina', 'Castro'), ('14567309-7', 'Ignacio', 'Morales'),
            ('20134765-3', 'Fernanda', 'Vega'), ('11876234-7', 'Andrés', 'Leiva')]

MASCOTAS = [('Michi', 'Felino'), ('Koda', 'Canino'), ('Luna', 'Canino'), ('Simba', 'Felino'),
            ('Rocky', 'Canino'), ('Nala', 'Felino'), ('Toby', 'Canino'), ('Pelusa', 'Felino'),
            ('Max', 'Canino'), ('Mia', 'Felino'), ('Bruno', 'Canino'), ('Kira', 'Canino'),
            ('Copito', 'Felino'), ('Thor', 'Canino'), ('Lola', 'Canino')]

# Mascotas que además tienen un familiar a cargo: muestra que una mascota
# puede tener más de un cliente. (índice de la mascota, índice del cliente)
FAMILIARES = [(0, 5), (4, 9), (10, 1)]

RAZAS = {
    'Canino': ['Quiltro', 'Labrador', 'Poodle'],
    'Felino': ['Mestizo', 'Siamés'],
    'Ave': ['Loro', 'Canario', 'Cotorra'],
    'Roedor': ['Hámster', 'Cuy'],
    'Conejo': ['Mini lop', 'Cabeza de león'],
    'Reptil': ['Tortuga', 'Iguana'],
}

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

        # Se crean aparte, y a propósito no entran en 'vets': así tienen ficha y
        # horario sin alterar el reparto de las citas históricas.
        vets_nuevos = []
        for username, nombre, apellido in VETERINARIOS_NUEVOS:
            u, _ = User.objects.get_or_create(
                username=username,
                defaults={'first_name': nombre, 'last_name': apellido})
            Perfil.objects.get_or_create(usuario=u, defaults={'rol': 'veterinario'})
            vets_nuevos.append(u)

        clientes = []
        for i, (rut, nombres, apellidos) in enumerate(CLIENTES):
            # Teléfono de prueba (inventado), para poder probar los botones
            # de llamar y de WhatsApp. No usa random: no altera la semilla.
            telefono = f'+56 9 {5100 + i * 137:04d} {2300 + i * 311:04d}'
            c, _ = Cliente.objects.update_or_create(
                rut=rut, defaults={'nombres': nombres, 'apellidos': apellidos,
                                   'telefono': telefono})
            clientes.append(c)

        # --- catálogos ---
        especies = {}
        for nombre in ('Canino', 'Felino', 'Ave', 'Roedor', 'Conejo', 'Reptil', 'Otro'):
            especies[nombre], _ = Especie.objects.get_or_create(nombre=nombre)

        for esp, razas in RAZAS.items():
            for r in razas:
                Raza.objects.get_or_create(especie=especies[esp], nombre=r)

        tipos = []
        for nombre, dur, precio in ATENCIONES:
            t, _ = TipoAtencion.objects.get_or_create(
                nombre=nombre,
                defaults={'duracion_minutos': dur, 'precio': precio})
            tipos.append(t)

        # --- horarios ---
        # Los nuevos también atienden: tienen agenda disponible de aquí en adelante.
        for v in vets + vets_nuevos:
            for dia in range(5):
                HorarioAtencion.objects.get_or_create(
                    veterinario=v, dia_semana=dia, hora_inicio='09:00',
                    defaults={'hora_fin': '13:00'})
                HorarioAtencion.objects.get_or_create(
                    veterinario=v, dia_semana=dia, hora_inicio='15:00',
                    defaults={'hora_fin': '19:00'})

        # --- mascotas ---
        # Generador aparte para las fechas de nacimiento: así no se altera la
        # secuencia de random que arma las citas, y los indicadores del informe
        # siguen dando los mismos números.
        rnd_nac = random.Random(7)

        mascotas = []
        for i, (nombre, esp) in enumerate(MASCOTAS):
            meses = rnd_nac.randint(8, 150)
            cliente = clientes[i % len(clientes)]
            datos = {
                'especie': especies[esp],
                'sexo': random.choice(['macho', 'hembra']),
                'fecha_nacimiento': timezone.localdate() - timedelta(days=meses * 30),
            }
            m = Mascota.objects.filter(nombre=nombre, tutores=cliente).first()
            if m is None:
                m = Mascota.objects.create(nombre=nombre, **datos)
            else:
                Mascota.objects.filter(pk=m.pk).update(**datos)
            Tenencia.objects.get_or_create(
                cliente=cliente, mascota=m,
                defaults={'relacion': Tenencia.Relacion.DUENO, 'es_principal': True})
            mascotas.append(m)

        # Algunas mascotas tienen además un familiar a cargo.
        for i_mascota, i_cliente in FAMILIARES:
            Tenencia.objects.get_or_create(
                cliente=clientes[i_cliente], mascota=mascotas[i_mascota],
                defaults={'relacion': Tenencia.Relacion.FAMILIAR})

        # La cita queda a nombre del responsable principal de la mascota.
        responsable = {m.pk: clientes[i % len(clientes)] for i, m in enumerate(mascotas)}

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

            # Se eligen en el mismo orden de siempre (primero la mascota, después
            # la atención) para no alterar la secuencia aleatoria de la semilla.
            mascota = random.choice(mascotas)
            tipo = random.choice(tipos)
            cita = Cita.objects.create(
                veterinario=vet,
                mascota=mascota,
                cliente=responsable[mascota.pk],
                tipo_atencion=tipo,
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
                # Antes aquí se sorteaba qué dueño (usuario) cancelaba. Como los
                # clientes ya no son usuarios, la cancelación queda sin usuario
                # asociado: la pidió el propio cliente. El sorteo se mantiene
                # para no mover la secuencia aleatoria de las citas siguientes.
                random.choice(clientes)
                Cita.objects.filter(pk=cita.pk).update(
                    fecha_cancelacion=reservada + timedelta(days=1))
            creadas += 1

        self.stdout.write(self.style.SUCCESS(
            f"Listo: {creadas} citas, {len(mascotas)} mascotas, {len(clientes)} clientes, "
            f"{len(vets) + len(vets_nuevos)} veterinarios "
            f"({len(vets)} con histórico), {len(tipos)} tipos de atención."))