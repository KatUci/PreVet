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
