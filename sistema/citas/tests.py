"""Pruebas de las citas y del modelo de puntuación del riesgo.

Django levanta una base de datos aparte para correrlas, así que no tocan
los datos reales del sistema.
"""

from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from mascotas.models import Cliente, Especie, Mascota, Tenencia
from .models import Cita, TipoAtencion
from . import riesgo


class BaseCitas(TestCase):
    """Arma una clínica mínima que sirve de punto de partida a las pruebas."""

    def setUp(self):
        self.vet = User.objects.create_user('vet', first_name='Paz',
                                            last_name='Herrera')
        self.tutor = User.objects.create_user('tutor', first_name='Ana',
                                              last_name='Soto')
        self.especie = Especie.objects.create(nombre='Perro')
        self.mascota = Mascota.objects.create(
            nombre='Bruno', especie=self.especie, sexo='macho')
        self.cliente = Cliente.objects.create(
            rut='15234871-1', nombres='Ana', apellidos='Soto')
        Tenencia.objects.create(cliente=self.cliente, mascota=self.mascota,
                                es_principal=True)
        self.control = TipoAtencion.objects.create(
            nombre='Control', duracion_minutos=30, precio=20000)

        # El modelo no permite dos citas del mismo veterinario a la misma
        # fecha y hora, así que cada una recibe un bloque distinto.
        self._bloque = 0

    def crear_cita(self, estado='pendiente', dias=7, tipo=None, mascota=None,
                   anticipacion=None):
        """Crea una cita y, si se pide, le fija los días de anticipación.

        fecha_creacion es auto_now_add, de modo que al crear queda siempre en
        hoy. Para probar la anticipación hay que sobrescribirla después.
        """
        self._bloque += 1
        hora = (datetime.min + timedelta(hours=8, minutes=5 * self._bloque)).time()

        mascota = mascota or self.mascota
        cita = Cita.objects.create(
            veterinario=self.vet,
            mascota=mascota,
            cliente=mascota.responsable,
            tipo_atencion=tipo or self.control,
            fecha=timezone.localdate() + timedelta(days=dias),
            hora=hora,
            estado=estado,
        )
        if anticipacion is not None:
            creada = cita.fecha - timedelta(days=anticipacion)
            Cita.objects.filter(pk=cita.pk).update(
                fecha_creacion=timezone.make_aware(
                    datetime.combine(creada, datetime.min.time())))
            cita.refresh_from_db()
        return cita


class CitaTest(BaseCitas):
    """El modelo Cita y lo que aporta este proyecto sobre el sistema base."""

    def test_el_estado_no_asistio_existe(self):
        """Es el aporte central: distinguir una falta de una cancelación."""
        estados = dict(Cita.ESTADOS)
        self.assertIn('no_asistio', estados)
        self.assertIn('cancelada', estados)
        self.assertNotEqual(estados['no_asistio'], estados['cancelada'])

    def test_valor_perdido_solo_cuando_el_tutor_no_se_presenta(self):
        self.assertEqual(self.crear_cita(estado='no_asistio').valor_perdido,
                         self.control.precio)
        self.assertEqual(self.crear_cita(estado='completada').valor_perdido, 0)
        self.assertEqual(self.crear_cita(estado='cancelada').valor_perdido, 0)

    def test_dias_anticipacion(self):
        self.assertEqual(self.crear_cita(anticipacion=10).dias_anticipacion, 10)
        self.assertEqual(self.crear_cita(anticipacion=0).dias_anticipacion, 0)


class EstadisticasTest(BaseCitas):
    """Las tasas históricas que alimentan el modelo."""

    def test_sin_historial_la_tasa_global_es_cero(self):
        self.assertEqual(riesgo.estadisticas()['global'], 0)

    def test_la_tasa_global_considera_solo_citas_resueltas(self):
        for _ in range(3):
            self.crear_cita(estado='completada')
        self.crear_cita(estado='no_asistio')
        self.crear_cita(estado='pendiente')   # no debería contar
        self.crear_cita(estado='cancelada')   # tampoco

        self.assertAlmostEqual(riesgo.estadisticas()['global'], 0.25)

    def test_registra_el_historial_por_tutor(self):
        self.crear_cita(estado='no_asistio')
        self.crear_cita(estado='completada')

        faltas, total = riesgo.estadisticas()['tutor'][self.cliente.pk]
        self.assertEqual((faltas, total), (1, 2))


class PuntuarTest(BaseCitas):
    """El corazón del proyecto: cómo se arma el puntaje de riesgo."""

    def test_los_pesos_suman_cien(self):
        self.assertEqual(
            riesgo.PESO_TUTOR + riesgo.PESO_ANTICIPACION
            + riesgo.PESO_DIA + riesgo.PESO_TIPO, 100)

    def test_el_puntaje_nunca_supera_cien(self):
        for _ in range(6):
            self.crear_cita(estado='no_asistio', dias=-3)
        cita = self.crear_cita(anticipacion=60)
        puntaje, _, _, _ = riesgo.puntuar(cita, riesgo.estadisticas())
        self.assertLessEqual(puntaje, 100)

    def test_quien_falta_siempre_puntua_mas_que_quien_nunca_falta(self):
        """Es el supuesto principal del modelo y debe quedar demostrado."""
        cumplidor = Cliente.objects.create(rut='16890342-1', nombres='Matías',
                                           apellidos='Silva')
        otra = Mascota.objects.create(nombre='Kira', especie=self.especie,
                                      sexo='hembra')
        Tenencia.objects.create(cliente=cumplidor, mascota=otra, es_principal=True)

        for _ in range(4):
            self.crear_cita(estado='no_asistio', dias=-5)
            self.crear_cita(estado='completada', dias=-5, mascota=otra)

        stats = riesgo.estadisticas()
        riesgoso = riesgo.puntuar(self.crear_cita(anticipacion=7), stats)[0]
        confiable = riesgo.puntuar(
            self.crear_cita(anticipacion=7, mascota=otra), stats)[0]

        self.assertGreater(riesgoso, confiable)

    def test_el_tutor_nuevo_se_trata_como_incertidumbre(self):
        """Sin historial no se asume inocencia: se asume que no se sabe."""
        cita = self.crear_cita(anticipacion=0)
        _, _, _, detalle = riesgo.puntuar(cita, riesgo.estadisticas())
        self.assertIn('Primera visita, sin historial', detalle)

    def test_el_detalle_explica_los_cuatro_factores(self):
        """Un puntaje sin explicación no le sirve a la recepcionista."""
        cita = self.crear_cita(anticipacion=5)
        _, _, _, detalle = riesgo.puntuar(cita, riesgo.estadisticas())
        self.assertEqual(len(detalle), 4)

    def test_cada_nivel_trae_su_accion_recomendada(self):
        cita = self.crear_cita(anticipacion=5)
        _, nivel, accion, _ = riesgo.puntuar(cita, riesgo.estadisticas())
        self.assertIn(nivel, ('alto', 'medio', 'bajo'))
        self.assertEqual(accion, riesgo.ACCIONES[nivel])

    def test_los_umbrales_estan_ordenados(self):
        self.assertGreater(riesgo.UMBRAL_ALTO, riesgo.UMBRAL_MEDIO)


class VistasCitasTest(BaseCitas):
    """La pantalla de citas y la acción de registrar una inasistencia."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.tutor)

    def test_el_listado_exige_haber_iniciado_sesion(self):
        self.client.logout()
        respuesta = self.client.get('/citas/')
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('/login/', respuesta.url)

    def test_el_listado_muestra_las_citas(self):
        self.crear_cita()
        respuesta = self.client.get('/citas/')
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Bruno')

    def test_el_filtro_deja_solo_las_citas_de_ese_estado(self):
        self.crear_cita(estado='no_asistio')
        self.crear_cita(estado='completada')
        self.crear_cita(estado='completada')

        respuesta = self.client.get('/citas/?estado=no_asistio')
        self.assertEqual(respuesta.context['total'], 1)

    def test_cada_filtro_trae_su_propio_conteo(self):
        self.crear_cita(estado='no_asistio')
        self.crear_cita(estado='completada')

        respuesta = self.client.get('/citas/')
        conteos = {f['valor']: f['conteo'] for f in respuesta.context['filtros']}
        self.assertEqual(conteos['no_asistio'], 1)
        self.assertEqual(conteos['completada'], 1)
        self.assertEqual(conteos['cancelada'], 0)

    def test_marcar_no_asistio_cambia_el_estado(self):
        cita = self.crear_cita(estado='pendiente')
        self.client.post(f'/citas/{cita.pk}/no-asistio/')
        cita.refresh_from_db()

        self.assertEqual(cita.estado, 'no_asistio')
        self.assertIsNotNone(cita.fecha_marcada_no_asistio)

    def test_marcar_no_asistio_no_acepta_una_visita_normal(self):
        """Una acción que cambia datos no puede ocurrir al abrir un enlace."""
        cita = self.crear_cita(estado='pendiente')
        self.client.get(f'/citas/{cita.pk}/no-asistio/')
        cita.refresh_from_db()

        self.assertEqual(cita.estado, 'pendiente')


class ClienteDeLaCitaTest(BaseCitas):
    """La cita solo puede quedar a nombre de un cliente vinculado a la mascota."""

    def test_cliente_ajeno_a_la_mascota_no_valida(self):
        from django.core.exceptions import ValidationError
        ajeno = Cliente.objects.create(rut='16890342-1', nombres='Matías', apellidos='Silva')
        cita = Cita(veterinario=self.vet, mascota=self.mascota, cliente=ajeno,
                    tipo_atencion=self.control, fecha=timezone.localdate(),
                    hora=datetime.min.time())
        with self.assertRaises(ValidationError):
            cita.full_clean()
