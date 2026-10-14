"""Pruebas de las fichas de pacientes."""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from .models import Especie, Mascota, Raza


class BaseMascotas(TestCase):

    def setUp(self):
        self.tutor = User.objects.create_user('tutor', first_name='Ana',
                                              last_name='Soto')
        self.perro = Especie.objects.create(nombre='Perro')
        self.gato = Especie.objects.create(nombre='Gato')


class EdadTest(BaseMascotas):
    """La edad se calcula al vuelo, no se guarda: así nunca queda desactualizada."""

    def mascota_nacida_hace(self, dias):
        return Mascota.objects.create(
            nombre='Bruno', especie=self.perro, sexo='macho',
            fecha_nacimiento=date.today() - timedelta(days=dias))

    def test_sin_fecha_de_nacimiento_no_inventa_una_edad(self):
        m = Mascota.objects.create(nombre='Kira', especie=self.gato,
                                   sexo='hembra')
        self.assertIsNone(m.edad)

    def test_menos_de_un_ano_se_expresa_en_meses(self):
        self.assertEqual(self.mascota_nacida_hace(100).edad, '3 meses')

    def test_un_ano_justo(self):
        self.assertEqual(self.mascota_nacida_hace(366).edad, '1 año')

    def test_anos_y_meses(self):
        self.assertIn('2 años', self.mascota_nacida_hace(800).edad)

    def test_recien_nacida_no_da_edad_negativa(self):
        self.assertEqual(self.mascota_nacida_hace(0).edad, '0 meses')


class RazaTest(BaseMascotas):

    def test_una_raza_puede_repetirse_entre_especies_distintas(self):
        Raza.objects.create(especie=self.perro, nombre='Mestizo')
        Raza.objects.create(especie=self.gato, nombre='Mestizo')

        self.assertEqual(Raza.objects.filter(nombre='Mestizo').count(), 2)


class VistaMascotasTest(BaseMascotas):

    def setUp(self):
        super().setUp()
        Mascota.objects.create(nombre='Bruno', especie=self.perro,
                               sexo='macho')
        Mascota.objects.create(nombre='Kira', especie=self.gato,
                               sexo='hembra')
        self.client.force_login(self.tutor)

    def test_la_ficha_exige_haber_iniciado_sesion(self):
        self.client.logout()
        respuesta = self.client.get('/mascotas/')
        self.assertEqual(respuesta.status_code, 302)

    def test_muestra_todos_los_pacientes(self):
        respuesta = self.client.get('/mascotas/')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['total'], 2)

    def test_el_buscador_filtra_por_nombre(self):
        respuesta = self.client.get('/mascotas/?buscar=bru')
        self.assertEqual(respuesta.context['total'], 1)
        self.assertContains(respuesta, 'Bruno')

    def test_las_mascotas_inactivas_no_aparecen(self):
        Mascota.objects.filter(nombre='Kira').update(activo=False)
        self.assertEqual(self.client.get('/mascotas/').context['total'], 1)


class ClienteTest(TestCase):
    """El RUT se valida con su dígito verificador y se guarda siempre igual."""

    def test_rut_valido_se_guarda_limpio(self):
        from .models import Cliente
        c = Cliente(rut='12.345.678-5', nombres='Ana', apellidos='Soto')
        c.full_clean()
        c.save()
        self.assertEqual(c.rut, '12345678-5')
        self.assertEqual(c.rut_formateado, '12.345.678-5')

    def test_rut_con_digito_verificador_incorrecto(self):
        from django.core.exceptions import ValidationError
        from .models import Cliente
        c = Cliente(rut='12.345.678-9', nombres='Ana', apellidos='Soto')
        with self.assertRaises(ValidationError):
            c.full_clean()

    def test_rut_con_k(self):
        from .rut import calcular_dv
        self.assertEqual(calcular_dv('10000013'), 'K')


class TenenciaTest(TestCase):
    """Muchos a muchos: un cliente con varias mascotas y al revés."""

    def setUp(self):
        from .models import Cliente
        canino = Especie.objects.create(nombre='Perro')
        self.ana = Cliente.objects.create(rut='15234871-1', nombres='Ana', apellidos='Soto')
        self.matias = Cliente.objects.create(rut='16890342-1', nombres='Matías', apellidos='Silva')
        self.bruno = Mascota.objects.create(nombre='Bruno', especie=canino, sexo='macho')
        self.kira = Mascota.objects.create(nombre='Kira', especie=canino, sexo='hembra')

    def test_un_cliente_con_varias_mascotas_y_una_mascota_con_varios_clientes(self):
        from .models import Tenencia
        Tenencia.objects.create(cliente=self.ana, mascota=self.bruno, es_principal=True)
        Tenencia.objects.create(cliente=self.ana, mascota=self.kira, es_principal=True)
        Tenencia.objects.create(cliente=self.matias, mascota=self.bruno,
                                relacion=Tenencia.Relacion.FAMILIAR)

        self.assertEqual(self.ana.mascotas.count(), 2)
        self.assertEqual(self.bruno.tutores.count(), 2)
        self.assertEqual(self.bruno.responsable, self.ana)

    def test_solo_un_responsable_principal_por_mascota(self):
        from django.db import IntegrityError, transaction
        from .models import Tenencia
        Tenencia.objects.create(cliente=self.ana, mascota=self.bruno, es_principal=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Tenencia.objects.create(cliente=self.matias, mascota=self.bruno, es_principal=True)
