from django.contrib.auth.models import Group, User
from django.test import TestCase

from mascotas.models import Cliente, Especie, Mascota, Tenencia

CLAVE = 'Huellita.2026'


def datos_registro(**cambios):
    datos = {'rut': '15.234.871-1', 'nombres': 'Ana', 'apellidos': 'Soto', 'email': 'ana@correo.cl',
             'telefono': '+56 9 1234 5678', 'password1': CLAVE, 'password2': CLAVE, 'consentimiento': 'on'}
    datos.update(cambios)
    return datos


class RegistroTest(TestCase):

    def test_un_cliente_nuevo_crea_su_cuenta_y_entra_al_portal(self):
        respuesta = self.client.post('/registro/', datos_registro())
        self.assertRedirects(respuesta, '/mi-prevet/')
        cliente = Cliente.objects.get(rut='15234871-1')
        self.assertEqual(cliente.usuario.username, '15234871-1')
        self.assertTrue(cliente.consentimiento_datos)
        self.assertEqual(cliente.usuario.perfil.rol, 'dueno')

    def test_se_vincula_a_la_ficha_existente_si_coincide_el_telefono(self):
        Cliente.objects.create(rut='15234871-1', nombres='Ana', apellidos='Soto', telefono='912345678')
        self.client.post('/registro/', datos_registro(email='otro@correo.cl'))
        self.assertEqual(Cliente.objects.filter(rut='15234871-1').count(), 1)
        self.assertIsNotNone(Cliente.objects.get(rut='15234871-1').usuario)

    def test_no_se_vincula_si_no_coincide_correo_ni_telefono(self):
        Cliente.objects.create(rut='15234871-1', nombres='Ana', apellidos='Soto', telefono='987654321',
                               email='ana@clinica.cl')
        respuesta = self.client.post('/registro/', datos_registro())
        self.assertContains(respuesta, 'no coinciden')
        self.assertIsNone(Cliente.objects.get(rut='15234871-1').usuario)

    def test_rut_invalido_y_claves_distintas(self):
        respuesta = self.client.post('/registro/', datos_registro(rut='15.234.871-5', password2='otra'))
        self.assertFalse(User.objects.exists())
        self.assertTrue(respuesta.context['form'].errors['rut'])
        self.assertTrue(respuesta.context['form'].errors['password2'])

    def test_sin_consentimiento_no_se_crea(self):
        datos = datos_registro()
        del datos['consentimiento']
        self.client.post('/registro/', datos)
        self.assertFalse(User.objects.exists())

    def test_entra_con_el_rut_con_puntos_o_sin_puntos(self):
        self.client.post('/registro/', datos_registro())
        self.client.logout()
        for usuario in ('15.234.871-1', '152348711', '15234871-1'):
            with self.subTest(usuario=usuario):
                self.assertTrue(self.client.login(username=usuario, password=CLAVE))
                self.client.logout()


class PortalTest(TestCase):

    def setUp(self):
        self.client.post('/registro/', datos_registro())
        self.ana = Cliente.objects.get(rut='15234871-1')
        perro = Especie.objects.get(nombre='Canino')
        self.bruno = Mascota.objects.create(nombre='Bruno', especie=perro, sexo='macho')
        Tenencia.objects.create(cliente=self.ana, mascota=self.bruno, es_principal=True)
        otro = Cliente.objects.create(rut='22333444-K', nombres='Luis', apellidos='Rojas')
        self.ajena = Mascota.objects.create(nombre='Toby', especie=perro, sexo='macho')
        Tenencia.objects.create(cliente=otro, mascota=self.ajena, es_principal=True)

    def test_el_inicio_lleva_al_portal_y_muestra_solo_lo_suyo(self):
        self.assertRedirects(self.client.get('/'), '/mi-prevet/')
        respuesta = self.client.get('/mi-prevet/')
        self.assertContains(respuesta, 'Bruno')
        self.assertNotContains(respuesta, 'Toby')

    def test_no_entra_a_las_pantallas_de_la_clinica(self):
        for url in ('/citas/', '/clientes/', '/mascotas/', '/riesgo/', '/administracion/personal/',
                    f'/mascotas/{self.bruno.pk}/foto/', '/admin/'):
            with self.subTest(url=url):
                self.assertIn(self.client.get(url).status_code, (302, 403))

    def test_no_puede_editar_una_mascota_ajena(self):
        self.assertEqual(self.client.get(f'/mi-prevet/mascotas/{self.ajena.pk}/').status_code, 404)
        self.assertEqual(self.client.get(f'/mi-prevet/mascotas/{self.ajena.pk}/foto/subir/').status_code, 404)

    def test_edita_sus_datos_y_los_de_su_mascota(self):
        self.client.post('/mi-prevet/datos/', {'nombres': 'Ana', 'apellidos': 'Soto', 'telefono': '911112222',
                                                'email': 'ana@correo.cl', 'canal_preferido': 'llamada',
                                                'comuna': 'Colina', 'region': 'Metropolitana'})
        self.ana.refresh_from_db()
        self.assertEqual((self.ana.telefono, self.ana.comuna), ('911112222', 'Colina'))
        self.client.post(f'/mi-prevet/mascotas/{self.bruno.pk}/', {
            'especie': self.bruno.especie_id, 'nombre': 'Bruno', 'sexo': 'macho', 'peso_kg': '18',
            'tiene_microchip': 'False', 'esterilizada': 'unknown', 'alergias': 'Pollo'})
        self.bruno.refresh_from_db()
        self.assertEqual(self.bruno.alergias, 'Pollo')

    def test_agrega_una_mascota_a_su_nombre(self):
        self.client.post('/mi-prevet/mascotas/nueva/', {
            'especie': self.bruno.especie_id, 'nombre': 'Luna', 'sexo': 'hembra', 'relacion': 'dueno',
            'tiene_microchip': 'False', 'esterilizada': 'unknown'})
        self.assertTrue(Tenencia.objects.filter(cliente=self.ana, mascota__nombre='Luna').exists())

    def test_el_personal_no_usa_el_portal(self):
        staff = User.objects.create_user('recep', password=CLAVE)
        staff.groups.add(Group.objects.get(name='Recepción'))
        self.client.force_login(staff)
        self.assertRedirects(self.client.get('/mi-prevet/'), '/', fetch_redirect_response=False)


class PedirHoraTest(PortalTest):
    """El cliente agenda él mismo una hora para una de sus mascotas."""

    def setUp(self):
        super().setUp()
        from datetime import timedelta

        from django.utils import timezone

        from citas.models import HorarioAtencion, TipoAtencion
        from usuarios.models import Perfil

        self.vet = User.objects.create_user('vet', first_name='Paz', last_name='Herrera')
        Perfil.objects.create(usuario=self.vet, rol='veterinario')
        for dia in range(6):
            HorarioAtencion.objects.create(veterinario=self.vet, dia_semana=dia,
                                           hora_inicio='09:00', hora_fin='13:00')
        self.control = TipoAtencion.objects.create(nombre='Control', duracion_minutos=30, precio=20000)
        hoy = timezone.localdate()
        self.lunes = hoy + timedelta(days=7 - hoy.weekday())

    def datos(self, **cambios):
        datos = {'mascota': self.bruno.pk, 'tipo_atencion': self.control.pk, 'veterinario': self.vet.pk,
                 'fecha': self.lunes.isoformat(), 'hora': '10:00', 'notas': 'Vacuna'}
        datos.update(cambios)
        return datos

    def test_la_pantalla_muestra_sus_mascotas_y_los_horarios(self):
        respuesta = self.client.get('/mi-prevet/pedir-hora/')
        self.assertContains(respuesta, 'Bruno')
        self.assertNotContains(respuesta, 'Toby')
        self.assertContains(respuesta, '<b>Lun a Sáb</b>', html=False)
        self.assertContains(respuesta, '09:00 a 13:00')

    def test_pide_hora_y_queda_a_su_nombre(self):
        from citas.models import Cita
        respuesta = self.client.post('/mi-prevet/pedir-hora/', self.datos())
        self.assertRedirects(respuesta, '/mi-prevet/')
        cita = Cita.objects.get()
        self.assertEqual((cita.cliente, cita.mascota, cita.estado), (self.ana, self.bruno, 'pendiente'))
        self.assertContains(self.client.get('/mi-prevet/'), 'Control con Paz Herrera')

    def test_no_puede_pedir_hora_para_una_mascota_ajena(self):
        from citas.models import Cita
        self.client.post('/mi-prevet/pedir-hora/', self.datos(mascota=self.ajena.pk))
        self.assertFalse(Cita.objects.exists())

    def test_no_puede_pedir_fuera_del_horario_ni_una_hora_tomada(self):
        from citas.models import Cita
        respuesta = self.client.post('/mi-prevet/pedir-hora/', self.datos(hora='15:00'))
        self.assertContains(respuesta, 'atiende ese día de 09:00 a 13:00')
        self.client.post('/mi-prevet/pedir-hora/', self.datos())
        respuesta = self.client.post('/mi-prevet/pedir-hora/', self.datos())
        self.assertContains(respuesta, 'ya está tomada')
        self.assertEqual(Cita.objects.count(), 1)

    def test_no_puede_pedir_una_hora_de_hoy_que_ya_paso(self):
        from datetime import datetime, time
        from unittest import mock

        from django.utils import timezone

        from citas.models import Cita, HorarioAtencion
        hoy = timezone.localdate()
        HorarioAtencion.objects.get_or_create(veterinario=self.vet, dia_semana=hoy.weekday(), hora_inicio='09:00',
                                              defaults={'hora_fin': '13:00'})
        a_las_ocho_pm = timezone.make_aware(datetime.combine(hoy, time(20, 0)))
        with mock.patch('django.utils.timezone.localtime', side_effect=lambda *a, **k: a_las_ocho_pm):
            respuesta = self.client.post('/mi-prevet/pedir-hora/', self.datos(fecha=hoy.isoformat()))
        self.assertContains(respuesta, 'Esa hora ya pasó')
        self.assertFalse(Cita.objects.exists())

    def test_consulta_las_horas_libres(self):
        respuesta = self.client.get('/citas/disponibles/', {'veterinario': self.vet.pk,
                                                            'fecha': self.lunes.isoformat()})
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('09:00', respuesta.json()['libres'])


class ProfesionalesEnElPortalTest(TestCase):
    """El cliente ve el horario de cada profesional y quién atiende urgencias."""

    def test_ve_horarios_y_urgencias(self):
        from django.utils import timezone
        from citas.models import HorarioAtencion
        from usuarios.models import Perfil
        vet = User.objects.create_user('vet', first_name='Paz', last_name='Herrera')
        Perfil.objects.create(usuario=vet, rol='veterinario')
        HorarioAtencion.objects.create(veterinario=vet, dia_semana=timezone.localdate().weekday(),
                                       hora_inicio='09:00', hora_fin='13:00')
        vet.groups.add(Group.objects.get_or_create(name='Urgencias')[0])
        ana = User.objects.create_user('15234871-1')
        Perfil.objects.create(usuario=ana, rol='dueno')
        Cliente.objects.create(rut='15234871-1', nombres='Ana', apellidos='Soto', usuario=ana)
        self.client.force_login(ana)
        respuesta = self.client.get('/mi-prevet/')
        self.assertContains(respuesta, 'Nuestros profesionales')
        self.assertContains(respuesta, 'Paz Herrera')
        self.assertContains(respuesta, 'Urgencias')
        self.assertContains(respuesta, 'Atiende hoy')


class EditarMascotaDesdeElPortalTest(TestCase):
    """El cliente corrige los datos de su mascota, por ejemplo el nombre."""

    def setUp(self):
        from usuarios.models import Perfil
        self.ana_user = User.objects.create_user('15234871-1')
        Perfil.objects.create(usuario=self.ana_user, rol='dueno')
        self.ana = Cliente.objects.create(rut='15234871-1', nombres='Ana', apellidos='Soto', usuario=self.ana_user)
        self.perro = Especie.objects.create(nombre='Perro')
        self.bruno = Mascota.objects.create(nombre='Bruon', especie=self.perro, sexo='macho')
        Tenencia.objects.create(cliente=self.ana, mascota=self.bruno, es_principal=True)
        self.client.force_login(self.ana_user)

    def test_cada_mascota_tiene_su_boton_editar(self):
        respuesta = self.client.get('/mi-prevet/')
        self.assertContains(respuesta, f'href="/mi-prevet/mascotas/{self.bruno.pk}/"')
        self.assertContains(respuesta, '✏️ Editar')

    def test_corrige_el_nombre(self):
        respuesta = self.client.post(f'/mi-prevet/mascotas/{self.bruno.pk}/',
                                     {'especie': self.perro.pk, 'nombre': 'Bruno', 'sexo': 'macho', 'tiene_microchip': ''})
        self.assertRedirects(respuesta, '/mi-prevet/')
        self.bruno.refresh_from_db()
        self.assertEqual(self.bruno.nombre, 'Bruno')

    def test_no_puede_editar_la_mascota_de_otro(self):
        otra = Mascota.objects.create(nombre='Kira', especie=self.perro, sexo='hembra')
        self.assertEqual(self.client.get(f'/mi-prevet/mascotas/{otra.pk}/').status_code, 404)


class MisRecetasTest(TestCase):
    """El cliente ve las indicaciones y descarga las recetas de sus mascotas."""

    def setUp(self):
        from django.utils import timezone
        from citas.models import Atencion, Cita, DocumentoAtencion, TipoAtencion
        from usuarios.models import Perfil
        vet = User.objects.create_user('vet', first_name='Paz', last_name='Herrera')
        Perfil.objects.create(usuario=vet, rol='veterinario')
        self.ana_user = User.objects.create_user('15234871-1')
        Perfil.objects.create(usuario=self.ana_user, rol='dueno')
        ana = Cliente.objects.create(rut='15234871-1', nombres='Ana', apellidos='Soto', usuario=self.ana_user)
        perro = Especie.objects.create(nombre='Perro')
        bruno = Mascota.objects.create(nombre='Bruno', especie=perro, sexo='macho')
        Tenencia.objects.create(cliente=ana, mascota=bruno, es_principal=True)
        tipo = TipoAtencion.objects.create(nombre='Control', duracion_minutos=30, precio=20000)
        cita = Cita.objects.create(veterinario=vet, mascota=bruno, cliente=ana, tipo_atencion=tipo,
                                   fecha=timezone.localdate(), hora='10:00', estado='completada')
        atencion = Atencion.objects.create(cita=cita, motivo='Control', diagnostico='Sano',
                                           tratamiento='Antiparasitario 1 comprimido')
        self.receta = DocumentoAtencion.objects.create(atencion=atencion, nombre='receta.pdf',
                                                       archivo=b'%PDF-1.4 receta', tamano=15)

    def test_ve_sus_recetas_y_las_descarga(self):
        self.client.force_login(self.ana_user)
        respuesta = self.client.get('/mi-prevet/')
        self.assertContains(respuesta, 'Mis recetas')
        self.assertContains(respuesta, 'Antiparasitario 1 comprimido')
        descarga = self.client.get(f'/mi-prevet/recetas/{self.receta.pk}/')
        self.assertEqual(descarga.content, b'%PDF-1.4 receta')

    def test_no_descarga_la_receta_de_otro(self):
        from usuarios.models import Perfil
        otro = User.objects.create_user('16890342-1')
        Perfil.objects.create(usuario=otro, rol='dueno')
        Cliente.objects.create(rut='16890342-1', nombres='Matías', apellidos='Silva', usuario=otro)
        self.client.force_login(otro)
        self.assertEqual(self.client.get(f'/mi-prevet/recetas/{self.receta.pk}/').status_code, 404)


class PaginaMisRecetasTest(MisRecetasTest):
    """La página Mis recetas: cada atención con sus indicaciones y la receta para descargar."""

    def test_la_pagina_muestra_las_recetas(self):
        self.client.force_login(self.ana_user)
        respuesta = self.client.get('/mi-prevet/recetas/')
        self.assertContains(respuesta, 'Indicaciones generales')
        self.assertContains(respuesta, 'Antiparasitario 1 comprimido')
        self.assertContains(respuesta, f'/mi-prevet/recetas/{self.receta.pk}/')
        self.assertContains(respuesta, 'Descargar receta')

    def test_el_menu_del_cliente_tiene_mis_recetas(self):
        self.client.force_login(self.ana_user)
        self.assertContains(self.client.get('/mi-prevet/'), 'href="/mi-prevet/recetas/"')


class MisVacunasTest(TestCase):
    """El cliente ve en un calendario qué día le toca la vacuna a cada mascota."""

    def setUp(self):
        import datetime
        from mascotas.models import Vacuna
        from usuarios.models import Perfil
        self.ana_user = User.objects.create_user('15234871-1')
        Perfil.objects.create(usuario=self.ana_user, rol='dueno')
        ana = Cliente.objects.create(rut='15234871-1', nombres='Ana', apellidos='Soto', usuario=self.ana_user)
        perro = Especie.objects.create(nombre='Perro')
        bruno = Mascota.objects.create(nombre='Bruno', especie=perro, sexo='macho')
        Tenencia.objects.create(cliente=ana, mascota=bruno, es_principal=True)
        self.sabado = datetime.date(2026, 11, 28)
        Vacuna.objects.create(mascota=bruno, nombre='Antirrábica', fecha_aplicacion=datetime.date(2025, 11, 28),
                              proxima_dosis=self.sabado)
        otra = Mascota.objects.create(nombre='Kira', especie=perro, sexo='hembra')
        Vacuna.objects.create(mascota=otra, nombre='Óctuple', fecha_aplicacion=datetime.date(2025, 11, 28),
                              proxima_dosis=self.sabado)
        self.client.force_login(self.ana_user)

    def test_el_calendario_marca_el_sabado_28(self):
        respuesta = self.client.get('/mi-prevet/vacunas/?mes=2026-11')
        self.assertContains(respuesta, 'Noviembre 2026')
        self.assertContains(respuesta, 'Bruno · Antirrábica')
        self.assertNotContains(respuesta, 'Kira')          # solo sus mascotas

    def test_el_menu_tiene_mis_vacunas(self):
        self.assertContains(self.client.get('/mi-prevet/'), 'href="/mi-prevet/vacunas/"')


class AvisosDeVacunasTest(MisVacunasTest):
    """Cada vacuna muestra qué le toca y su aviso: al día, próxima o atrasada."""

    def setUp(self):
        super().setUp()
        import datetime
        from django.utils import timezone
        from mascotas.models import Mascota, Vacuna
        hoy = timezone.localdate()
        bruno = Mascota.objects.get(nombre='Bruno')
        Vacuna.objects.create(mascota=bruno, nombre='Bordetella', fecha_aplicacion=hoy - datetime.timedelta(days=400),
                              proxima_dosis=hoy - datetime.timedelta(days=5))
        Vacuna.objects.create(mascota=bruno, nombre='Óctuple', fecha_aplicacion=hoy - datetime.timedelta(days=10),
                              proxima_dosis=hoy + datetime.timedelta(days=90))
        # Una Óctuple vieja que ya quedó cubierta por la nueva: no debe aparecer como atrasada.
        Vacuna.objects.create(mascota=bruno, nombre='óctuple', fecha_aplicacion=hoy - datetime.timedelta(days=400),
                              proxima_dosis=hoy - datetime.timedelta(days=20))

    def test_muestra_que_le_toca_y_el_aviso(self):
        respuesta = self.client.get('/mi-prevet/vacunas/')
        self.assertContains(respuesta, 'Bruno · le toca Bordetella')
        self.assertContains(respuesta, 'La fecha programada ya pasó')
        self.assertContains(respuesta, 'Bruno · le toca Óctuple')
        self.assertContains(respuesta, 'Vacunación vigente.')
        dosis = respuesta.context['dosis']
        self.assertEqual([v.estado['clave'] for v in dosis], ['atrasada', 'proxima', 'al_dia'])

    def test_el_personal_ve_el_aviso(self):
        from django.contrib.auth.models import Permission
        vet = User.objects.create_user('vet.prueba')
        vet.user_permissions.add(Permission.objects.get(codename='view_vacuna'))
        self.client.force_login(vet)
        respuesta = self.client.get('/mascotas/vacunas/')
        self.assertContains(respuesta, 'etiqueta-mal">Atrasada')
        self.assertContains(respuesta, 'Bordetella')
        self.assertContains(respuesta, 'Calendario de vacunación canina')
