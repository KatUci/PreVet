"""Pruebas del tablero y de la pantalla de indicadores."""

from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from citas.models import Cita, TipoAtencion
from mascotas.models import Cliente, Especie, Mascota, Tenencia


class BaseTablero(TestCase):
    """Historial conocido, para poder afirmar qué número tiene que salir."""

    def setUp(self):
        self.vet = User.objects.create_user('vet', first_name='Paz',
                                            last_name='Herrera')
        self.tutor = User.objects.create_user('tutor', first_name='Ana',
                                              last_name='Soto')
        especie = Especie.objects.create(nombre='Perro')
        self.mascota = Mascota.objects.create(
            nombre='Bruno', especie=especie, sexo='macho')
        self.cliente = Cliente.objects.create(
            rut='15234871-1', nombres='Ana', apellidos='Soto')
        Tenencia.objects.create(cliente=self.cliente, mascota=self.mascota,
                                es_principal=True)

        self.control = TipoAtencion.objects.create(
            nombre='Control', duracion_minutos=30, precio=20000)
        self.urgencia = TipoAtencion.objects.create(
            nombre='Urgencia', duracion_minutos=45, precio=35000)

        self._bloque = 0
        self.client.force_login(self.tutor)

    def crear_cita(self, estado, tipo=None, dias=-5):
        """Por omisión crea citas en el pasado: el tablero solo mira esas."""
        self._bloque += 1
        hora = (datetime.min + timedelta(hours=8, minutes=5 * self._bloque)).time()
        return Cita.objects.create(
            veterinario=self.vet, mascota=self.mascota, cliente=self.cliente,
            tipo_atencion=tipo or self.control,
            fecha=timezone.localdate() + timedelta(days=dias),
            hora=hora, estado=estado)


class TableroTest(BaseTablero):

    def test_exige_haber_iniciado_sesion(self):
        self.client.logout()
        self.assertEqual(self.client.get('/').status_code, 302)

    def test_la_tasa_se_calcula_sobre_las_citas_ya_ocurridas(self):
        for _ in range(3):
            self.crear_cita('completada')
        self.crear_cita('no_asistio')

        contexto = self.client.get('/').context
        self.assertEqual(contexto['total_ocurridas'], 4)
        self.assertEqual(contexto['total_faltas'], 1)
        self.assertEqual(contexto['tasa'], 25.0)

    def test_las_citas_futuras_no_entran_en_la_tasa(self):
        """De una cita que todavía no ocurre no se sabe si se va a concretar."""
        self.crear_cita('completada')
        self.crear_cita('pendiente', dias=10)

        self.assertEqual(self.client.get('/').context['total_ocurridas'], 1)

    def test_el_monto_perdido_suma_el_precio_de_las_faltas(self):
        self.crear_cita('no_asistio', tipo=self.control)      # 20.000
        self.crear_cita('no_asistio', tipo=self.urgencia)     # 35.000
        self.crear_cita('completada', tipo=self.urgencia)     # no suma

        self.assertEqual(self.client.get('/').context['perdido'], 55000)


class IndicadoresTest(BaseTablero):

    def test_la_pantalla_responde(self):
        """Antes este enlace del menú devolvía un error 404."""
        self.assertEqual(self.client.get('/indicadores/').status_code, 200)

    def test_exige_haber_iniciado_sesion(self):
        self.client.logout()
        self.assertEqual(self.client.get('/indicadores/').status_code, 302)

    def test_agrupa_la_tasa_por_tipo_de_atencion(self):
        self.crear_cita('no_asistio', tipo=self.urgencia)
        self.crear_cita('completada', tipo=self.urgencia)
        self.crear_cita('completada', tipo=self.control)

        por_tipo = {f['nombre']: f for f in
                    self.client.get('/indicadores/').context['por_tipo']}

        self.assertEqual(por_tipo['Urgencia']['tasa'], 50.0)
        self.assertEqual(por_tipo['Control']['tasa'], 0)

    def test_ordena_los_tipos_de_peor_a_mejor(self):
        self.crear_cita('no_asistio', tipo=self.urgencia)
        self.crear_cita('completada', tipo=self.control)

        tasas = [f['tasa'] for f in
                 self.client.get('/indicadores/').context['por_tipo']]
        self.assertEqual(tasas, sorted(tasas, reverse=True))

    def test_lista_a_los_tutores_con_mas_faltas_primero(self):
        self.crear_cita('no_asistio')
        self.crear_cita('completada')

        primero = self.client.get('/indicadores/').context['reincidentes'][0]
        self.assertEqual(primero['nombre'], 'Ana Soto')
        self.assertEqual(primero['faltas'], 1)

    def test_el_monto_se_escribe_con_puntos_de_miles(self):
        """En Chile los miles van con punto; intcomma depende del idioma."""
        self.crear_cita('no_asistio', tipo=self.urgencia)   # 35.000

        general = self.client.get('/indicadores/').context['general']
        self.assertEqual(general['perdido_txt'], '35.000')
