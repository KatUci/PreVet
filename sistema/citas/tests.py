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


class AgendarTest(TestCase):
    """El flujo completo: RUT del cliente, una de sus mascotas y la hora."""

    CLAVE = 'Huellitas.2026!'

    def setUp(self):
        from django.contrib.auth.models import Group
        from usuarios.models import Perfil
        from .models import HorarioAtencion

        self.vet = User.objects.create_user('vet', first_name='Paz', last_name='Herrera')
        Perfil.objects.create(usuario=self.vet, rol='veterinario')
        # Atiende de lunes a viernes, de 09:00 a 13:00.
        for dia in range(5):
            HorarioAtencion.objects.create(veterinario=self.vet, dia_semana=dia,
                                           hora_inicio='09:00', hora_fin='13:00')

        self.recepcion = User.objects.create_user('recepcion', password=self.CLAVE)
        self.recepcion.groups.add(Group.objects.get(name='Recepción'))

        canino = Especie.objects.create(nombre='Perro')
        self.ana = Cliente.objects.create(rut='15234871-1', nombres='Ana', apellidos='Soto')
        self.bruno = Mascota.objects.create(nombre='Bruno', especie=canino, sexo='macho')
        Tenencia.objects.create(cliente=self.ana, mascota=self.bruno, es_principal=True)
        self.otro = Cliente.objects.create(rut='16890342-1', nombres='Matías', apellidos='Silva')
        self.ajena = Mascota.objects.create(nombre='Kira', especie=canino, sexo='hembra')
        Tenencia.objects.create(cliente=self.otro, mascota=self.ajena, es_principal=True)

        self.control = TipoAtencion.objects.create(nombre='Control', duracion_minutos=30, precio=20000)
        self.client.login(username='recepcion', password=self.CLAVE)

        # El próximo lunes, para que siempre sea un día con horario.
        hoy = timezone.localdate()
        self.lunes = hoy + timedelta(days=7 - hoy.weekday())

    def url(self, rut='15.234.871-1'):
        return f'/citas/nueva/?rut={rut}'

    def datos(self, **cambios):
        datos = {'mascota': self.bruno.pk, 'tipo_atencion': self.control.pk,
                 'veterinario': self.vet.pk, 'fecha': self.lunes.isoformat(),
                 'hora': '10:00', 'notas': ''}
        datos.update(cambios)
        return datos

    def test_sin_permiso_de_agendar_recibe_403(self):
        User.objects.create_user('sinpermiso', password=self.CLAVE)
        self.client.login(username='sinpermiso', password=self.CLAVE)
        self.assertEqual(self.client.get('/citas/nueva/').status_code, 403)

    def test_rut_invalido(self):
        respuesta = self.client.get(self.url('12.345.678-9'))
        self.assertContains(respuesta, 'dígito verificador no corresponde')

    def test_rut_sin_cliente_ofrece_registrarlo(self):
        respuesta = self.client.get(self.url('12.345.678-5'))
        self.assertContains(respuesta, 'Registrar cliente')

    def test_solo_aparecen_las_mascotas_del_cliente(self):
        respuesta = self.client.get(self.url())
        self.assertContains(respuesta, 'Bruno')
        self.assertNotContains(respuesta, 'Kira')

    def test_agenda_la_hora_a_nombre_del_cliente(self):
        respuesta = self.client.post(self.url(), self.datos())
        self.assertRedirects(respuesta, '/citas/')
        cita = Cita.objects.get()
        self.assertEqual(cita.cliente, self.ana)
        self.assertEqual(cita.mascota, self.bruno)
        self.assertEqual(cita.estado, 'pendiente')

    def test_no_acepta_una_mascota_de_otro_cliente(self):
        self.client.post(self.url(), self.datos(mascota=self.ajena.pk))
        self.assertFalse(Cita.objects.exists())

    def test_no_acepta_fechas_pasadas(self):
        ayer = timezone.localdate() - timedelta(days=1)
        respuesta = self.client.post(self.url(), self.datos(fecha=ayer.isoformat()))
        self.assertContains(respuesta, 'ya pasó')
        self.assertFalse(Cita.objects.exists())

    def test_fuera_del_horario_del_profesional(self):
        respuesta = self.client.post(self.url(), self.datos(hora='15:00'))
        self.assertContains(respuesta, 'atiende ese día de 09:00 a 13:00')
        self.assertFalse(Cita.objects.exists())

    def test_no_permite_tomar_una_hora_ocupada(self):
        self.client.post(self.url(), self.datos())
        respuesta = self.client.post(self.url(), self.datos())
        self.assertContains(respuesta, 'ya está tomada')
        self.assertEqual(Cita.objects.count(), 1)


class RegistrarClienteYMascotaTest(TestCase):

    CLAVE = 'Huellitas.2026!'

    def setUp(self):
        from django.contrib.auth.models import Group
        recepcion = User.objects.create_user('recepcion', password=self.CLAVE)
        recepcion.groups.add(Group.objects.get(name='Recepción'))
        self.client.login(username='recepcion', password=self.CLAVE)

    def test_registra_cliente_con_rut_limpio_y_vuelve_a_agendar(self):
        respuesta = self.client.post('/clientes/nuevo/', {
            'rut': '12.345.678-5', 'nombres': 'Ana', 'apellidos': 'Soto'})
        self.assertRedirects(respuesta, '/citas/nueva/?rut=12345678-5', fetch_redirect_response=False)
        self.assertTrue(Cliente.objects.filter(rut='12345678-5').exists())

    def test_no_permite_rut_repetido(self):
        Cliente.objects.create(rut='12345678-5', nombres='Ana', apellidos='Soto')
        respuesta = self.client.post('/clientes/nuevo/', {
            'rut': '12345678-5', 'nombres': 'Otra', 'apellidos': 'Persona'})
        self.assertContains(respuesta, 'Ya hay un cliente registrado con este RUT.')

    def test_no_redirige_a_otros_sitios(self):
        respuesta = self.client.post('/clientes/nuevo/?next=https://sitio-malo.com/', {
            'rut': '12.345.678-5', 'nombres': 'Ana', 'apellidos': 'Soto'})
        self.assertNotIn('sitio-malo', respuesta['Location'])

    def test_registra_mascota_con_tipo_y_raza_y_la_vincula(self):
        from mascotas.models import Raza
        ana = Cliente.objects.create(rut='12345678-5', nombres='Ana', apellidos='Soto')
        ave = Especie.objects.get(nombre='Ave')
        loro = Raza.objects.create(especie=ave, nombre='Loro')
        self.client.post(f'/clientes/{ana.pk}/mascotas/nueva/', {
            'especie': ave.pk, 'raza': loro.pk, 'nombre': 'Pepe', 'sexo': 'macho',
            'fecha_nacimiento': '', 'relacion': 'dueno'})
        pepe = Mascota.objects.get(nombre='Pepe')
        self.assertEqual(pepe.especie, ave)
        self.assertEqual(pepe.responsable, ana)

    def test_raza_de_otro_tipo_no_valida(self):
        from mascotas.models import Raza
        ana = Cliente.objects.create(rut='12345678-5', nombres='Ana', apellidos='Soto')
        felino = Especie.objects.get(nombre='Felino')
        loro = Raza.objects.create(especie=Especie.objects.get(nombre='Ave'), nombre='Loro')
        respuesta = self.client.post(f'/clientes/{ana.pk}/mascotas/nueva/', {
            'especie': felino.pk, 'raza': loro.pk, 'nombre': 'Michi', 'sexo': 'macho',
            'fecha_nacimiento': '', 'relacion': 'dueno'})
        self.assertContains(respuesta, 'no es una raza de felino')
        self.assertFalse(Mascota.objects.filter(nombre='Michi').exists())
