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
        # Las pantallas exigen permisos: el usuario de prueba entra como Administración.
        from django.contrib.auth.models import Group
        self.tutor.groups.add(Group.objects.get(name='Administración'))
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


class BuscadorGlobalTest(TestCase):
    """El buscador de la barra superior encuentra clientes, mascotas y citas."""

    def setUp(self):
        from django.contrib.auth.models import Group

        from mascotas.models import Cliente, Especie, Mascota, Tenencia
        usuario = User.objects.create_user('recep')
        usuario.groups.add(Group.objects.get(name='Recepción'))
        self.client.force_login(usuario)
        cliente = Cliente.objects.create(rut='15234871-1', nombres='Javiera', apellidos='Pérez')
        luna = Mascota.objects.create(nombre='Luna', especie=Especie.objects.create(nombre='Gato'), sexo='hembra')
        Tenencia.objects.create(cliente=cliente, mascota=luna, es_principal=True)

    def test_encuentra_al_cliente_y_su_mascota(self):
        contexto = self.client.get('/buscar/?q=javiera').context
        self.assertEqual(contexto['totales']['clientes'], 1)
        self.assertEqual(contexto['totales']['mascotas'], 1)

    def test_con_una_letra_no_busca(self):
        self.assertEqual(self.client.get('/buscar/?q=j').context['total'], 0)


class EvaluacionModeloTest(BaseTablero):
    """¿Acierta el modelo? (PV-RIE-03): riesgo estimado contra asistencia real."""

    def test_cada_cita_se_puntua_sin_conocer_su_propio_resultado(self):
        from citas.riesgo import evaluar
        cita = self.crear_cita('no_asistio')
        # Con todo el historial, esta falta pesaría en su propio puntaje. Antes
        # de su fecha no había historial: primera visita (15 pts) y nada más.
        self.assertEqual(evaluar(), [(cita, 15, 'bajo')])

    def test_el_historial_de_las_fechas_anteriores_si_cuenta(self):
        from citas.riesgo import evaluar
        self.crear_cita('no_asistio', dias=-10)
        self.crear_cita('no_asistio', dias=-9)
        cita = self.crear_cita('completada', dias=-5)
        # Desde hace 6 días solo se evalúa la última, pero las faltas de
        # antes alimentan su historial: el tutor faltó 2 de 2 veces.
        desde = timezone.localdate() - timedelta(days=6)
        [(evaluada, puntaje, nivel)] = evaluar(desde=desde)
        self.assertEqual((evaluada, nivel), (cita, 'alto'))
        self.assertGreaterEqual(puntaje, 62)

    def test_resumen_por_nivel(self):
        from types import SimpleNamespace

        from citas.riesgo import resumen_evaluacion
        falta, llego = SimpleNamespace(estado='no_asistio'), SimpleNamespace(estado='completada')
        evaluadas = ([(falta, 70, 'alto')] * 2 + [(llego, 70, 'alto')]
                     + [(falta, 50, 'medio')] + [(llego, 20, 'bajo')] * 3 + [(falta, 20, 'bajo')])
        resumen = resumen_evaluacion(evaluadas)
        alto, medio, bajo = resumen['niveles']
        self.assertEqual((alto['citas'], alto['faltas'], alto['tasa']), (3, 2, 66.7))
        self.assertEqual((bajo['citas'], bajo['faltas'], bajo['tasa']), (4, 1, 25.0))
        self.assertEqual(medio['de_las_faltas'], 25)
        self.assertEqual(resumen['anticipadas'], 75)          # 3 de las 4 faltas, en alto o medio
        self.assertEqual(resumen['aciertos'], 75)             # 2 + 1 faltas avisadas + 3 que llegaron, de 8
        self.assertEqual(resumen['veces'], 2.7)               # 66,7 % contra 25 %

    def test_la_pantalla_muestra_los_niveles(self):
        self.crear_cita('no_asistio', dias=-10)
        self.crear_cita('completada', dias=-5)
        respuesta = self.client.get('/riesgo/evaluacion/')
        self.assertContains(respuesta, '¿Cuántos faltaron en cada nivel de riesgo?')
        self.assertEqual(respuesta.context['resumen']['total'], 2)

    def test_sin_citas_resueltas_avisa(self):
        self.assertContains(self.client.get('/riesgo/evaluacion/'), 'No hay citas resueltas')

    def test_recepcion_no_la_ve(self):
        from django.contrib.auth.models import Group
        recepcion = User.objects.create_user('recep')
        recepcion.groups.add(Group.objects.get(name='Recepción'))
        self.client.force_login(recepcion)
        self.assertEqual(self.client.get('/riesgo/evaluacion/').status_code, 403)
