"""Pruebas de las fichas de pacientes."""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from .models import Cliente, Especie, Mascota, Raza, Tenencia


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

        self.assertEqual(Raza.objects.filter(nombre='Mestizo', especie__in=[self.perro, self.gato]).count(), 2)


class VistaMascotasTest(BaseMascotas):

    def setUp(self):
        super().setUp()
        Mascota.objects.create(nombre='Bruno', especie=self.perro,
                               sexo='macho')
        Mascota.objects.create(nombre='Kira', especie=self.gato,
                               sexo='hembra')
        # Las pantallas exigen permisos: el usuario de prueba entra como Administración.
        from django.contrib.auth.models import Group
        self.tutor.groups.add(Group.objects.get(name='Administración'))
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


class SeccionClientesTest(TestCase):
    """Directorio de clientes y ficha con su historial."""

    def setUp(self):
        from datetime import timedelta

        from django.contrib.auth.models import Group, User
        from django.utils import timezone

        from citas.models import Cita, TipoAtencion
        from .models import Cliente, Especie, Mascota, Tenencia

        self.usuario = User.objects.create_user('recep')
        self.usuario.groups.add(Group.objects.get(name='Recepción'))
        self.client.force_login(self.usuario)

        vet = User.objects.create_user('vet', first_name='Paz', last_name='Herrera')
        perro = Especie.objects.create(nombre='Perro')
        control = TipoAtencion.objects.create(nombre='Control', duracion_minutos=30, precio=20000)
        self.ana = Cliente.objects.create(rut='15234871-1', nombres='Ana', apellidos='Soto', telefono='912345678')
        self.luis = Cliente.objects.create(rut='22333444-K', nombres='Luis', apellidos='Rojas')
        bruno = Mascota.objects.create(nombre='Bruno', especie=perro, sexo='macho')
        Tenencia.objects.create(cliente=self.ana, mascota=bruno, es_principal=True)

        hoy = timezone.localdate()
        for i, estado in enumerate(['no_asistio', 'no_asistio', 'completada', 'pendiente']):
            dias = 5 if estado == 'pendiente' else -10 + i
            Cita.objects.create(veterinario=vet, mascota=bruno, cliente=self.ana, tipo_atencion=control,
                                fecha=hoy + timedelta(days=dias), hora=f'1{i}:00', estado=estado)

    def test_busca_por_rut_o_por_la_mascota(self):
        for texto in ('15.234.871-1', '15234871', 'bruno'):
            with self.subTest(texto=texto):
                pagina = self.client.get(f'/clientes/?q={texto}').context['pagina']
                self.assertEqual([c.pk for c in pagina], [self.ana.pk])

    def test_filtra_reincidentes(self):
        pagina = self.client.get('/clientes/?filtro=reincidentes').context['pagina']
        self.assertEqual([c.pk for c in pagina], [self.ana.pk])
        self.assertTrue(pagina[0].reincidente)
        self.assertEqual(pagina[0].tasa, 67)        # 2 faltas de 3 citas resueltas

    def test_la_ficha_resume_el_historial(self):
        respuesta = self.client.get(f'/clientes/{self.ana.pk}/')
        resumen = respuesta.context['resumen']
        self.assertEqual((resumen['total'], resumen['atendidas'], resumen['faltas']), (4, 1, 2))
        self.assertEqual(resumen['perdido_txt'], '40.000')
        self.assertEqual(len(respuesta.context['proximas']), 1)
        self.assertTrue(respuesta.context['whatsapp'].startswith('https://wa.me/56912345678'))

    def test_cliente_sin_citas_no_rompe_la_ficha(self):
        respuesta = self.client.get(f'/clientes/{self.luis.pk}/')
        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.context['resumen']['tasa'])


class FotosMascotaTest(TestCase):
    """Las fotos se achican, se guardan en la base y se pueden cambiar o quitar."""

    def setUp(self):
        from django.contrib.auth.models import Group

        from .models import Cliente, Especie, Mascota, Tenencia
        self.usuario = User.objects.create_user('recep')
        self.usuario.groups.add(Group.objects.get(name='Recepción'))
        self.client.force_login(self.usuario)
        self.cliente = Cliente.objects.create(rut='15234871-1', nombres='Ana', apellidos='Soto')
        self.perro = Especie.objects.create(nombre='Perro')
        self.bruno = Mascota.objects.create(nombre='Bruno', especie=self.perro, sexo='macho')
        Tenencia.objects.create(cliente=self.cliente, mascota=self.bruno, es_principal=True)

    def imagen(self, ancho=2000, alto=1500, formato='PNG'):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        datos = BytesIO()
        modo = 'RGBA' if formato == 'PNG' else 'RGB'
        Image.new(modo, (ancho, alto), (236, 133, 161)).save(datos, formato)
        return SimpleUploadedFile(f'foto.{formato.lower()}', datos.getvalue(), content_type=f'image/{formato.lower()}')

    def test_sube_la_foto_achicada_y_en_jpeg(self):
        from io import BytesIO

        from PIL import Image
        respuesta = self.client.post(f'/mascotas/{self.bruno.pk}/foto/subir/', {'foto': self.imagen()})
        self.assertEqual(respuesta.status_code, 302)
        self.bruno.refresh_from_db()
        self.assertEqual(self.bruno.foto_version, 1)
        foto = self.client.get(f'/mascotas/{self.bruno.pk}/foto/')
        self.assertEqual(foto['Content-Type'], 'image/jpeg')
        self.assertEqual(max(Image.open(BytesIO(foto.content)).size), 900)

    def test_cambiar_la_foto_sube_la_version(self):
        self.client.post(f'/mascotas/{self.bruno.pk}/foto/subir/', {'foto': self.imagen()})
        self.client.post(f'/mascotas/{self.bruno.pk}/foto/subir/', {'foto': self.imagen(300, 300, 'JPEG')})
        self.bruno.refresh_from_db()
        self.assertEqual(self.bruno.foto_version, 2)

    def test_quitar_la_foto(self):
        self.client.post(f'/mascotas/{self.bruno.pk}/foto/subir/', {'foto': self.imagen()})
        self.client.post(f'/mascotas/{self.bruno.pk}/foto/quitar/')
        self.bruno.refresh_from_db()
        self.assertEqual(self.bruno.foto_version, 0)
        self.assertEqual(self.client.get(f'/mascotas/{self.bruno.pk}/foto/').status_code, 404)

    def test_un_archivo_que_no_es_imagen_se_rechaza(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        falso = SimpleUploadedFile('foto.jpg', b'no soy una imagen', content_type='image/jpeg')
        respuesta = self.client.post(f'/mascotas/{self.bruno.pk}/foto/subir/', {'foto': falso})
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context['form'].errors)

    def test_registrar_mascota_con_foto(self):
        from .models import Mascota
        self.client.post(f'/clientes/{self.cliente.pk}/mascotas/nueva/', {
            'especie': self.perro.pk, 'nombre': 'Luna', 'sexo': 'hembra', 'relacion': 'dueno',
            'foto': self.imagen(800, 600)})
        luna = Mascota.objects.get(nombre='Luna')
        self.assertEqual(luna.foto_version, 1)


class DatosCompletosTest(TestCase):
    """Datos reales de clientes y mascotas: validaciones y panel de administración."""

    def setUp(self):
        from django.contrib.auth.models import Group

        from .models import Cliente, Especie
        self.usuario = User.objects.create_user('recep', is_staff=True)
        self.usuario.groups.add(Group.objects.get(name='Administración'))
        self.client.force_login(self.usuario)
        self.cliente = Cliente.objects.create(rut='15234871-1', nombres='Ana', apellidos='Soto')
        self.canino = Especie.objects.get(nombre='Canino')

    def datos_mascota(self, **cambios):
        datos = {'especie': self.canino.pk, 'nombre': 'Toby', 'sexo': 'macho', 'relacion': 'dueno',
                 'microchip': '', 'peso_kg': '', 'esterilizada': 'unknown'}
        datos.update(cambios)
        return datos

    def test_las_razas_frecuentes_quedan_cargadas(self):
        self.assertTrue(self.canino.razas.filter(nombre='Golden Retriever').exists())
        self.assertGreater(self.canino.razas.count(), 40)

    def test_microchip_de_15_digitos_y_unico(self):
        from .models import Mascota
        url = f'/clientes/{self.cliente.pk}/mascotas/nueva/'
        respuesta = self.client.post(url, self.datos_mascota(tiene_microchip='True', microchip='12345'))
        self.assertContains(respuesta, '15 dígitos')
        self.client.post(url, self.datos_mascota(tiene_microchip='True', microchip='985112003456789', peso_kg='12.5',
                                                 alergias='Penicilina', esterilizada='true'))
        toby = Mascota.objects.get(nombre='Toby')
        self.assertEqual((toby.microchip, float(toby.peso_kg), toby.alergias, toby.esterilizada),
                         ('985112003456789', 12.5, 'Penicilina', True))
        repetido = self.client.post(url, self.datos_mascota(nombre='Otro', tiene_microchip='True', microchip='985112003456789'))
        self.assertContains(repetido, 'otra mascota registrada con este microchip')

    def test_peso_fuera_de_rango(self):
        respuesta = self.client.post(f'/clientes/{self.cliente.pk}/mascotas/nueva/', self.datos_mascota(peso_kg='0'))
        self.assertContains(respuesta, 'Revisa el peso')

    def test_el_consentimiento_guarda_su_fecha(self):
        self.client.post(f'/clientes/{self.cliente.pk}/editar/', {
            'rut': '15234871-1', 'nombres': 'Ana', 'apellidos': 'Soto', 'comuna': 'Colina',
            'region': 'Metropolitana', 'canal_preferido': 'llamada', 'consentimiento_datos': 'on'})
        self.cliente.refresh_from_db()
        self.assertEqual((self.cliente.comuna, self.cliente.canal_preferido), ('Colina', 'llamada'))
        self.assertIsNotNone(self.cliente.fecha_consentimiento)

    def test_telefono_de_emergencia_pide_el_nombre(self):
        respuesta = self.client.post(f'/clientes/{self.cliente.pk}/editar/', {
            'rut': '15234871-1', 'nombres': 'Ana', 'apellidos': 'Soto', 'telefono_emergencia': '912345678'})
        self.assertContains(respuesta, 'de quién es el teléfono de emergencia')

    def test_el_panel_de_administracion_abre(self):
        self.usuario.is_superuser = True
        self.usuario.save()
        for url in ('/admin/mascotas/cliente/', '/admin/mascotas/mascota/', '/admin/citas/cita/',
                    f'/admin/mascotas/cliente/{self.cliente.pk}/change/', '/admin/mascotas/tenencia/'):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_microchip_si_sin_numero_y_no_borra_el_numero(self):
        from .models import Mascota
        url = f'/clientes/{self.cliente.pk}/mascotas/nueva/'
        self.client.post(url, self.datos_mascota(nombre='Con', tiene_microchip='True'))
        self.client.post(url, self.datos_mascota(nombre='Sin', tiene_microchip='False', microchip='985112003456789'))
        con, sin = Mascota.objects.get(nombre='Con'), Mascota.objects.get(nombre='Sin')
        self.assertEqual((con.tiene_microchip, con.microchip), (True, ''))
        self.assertEqual((sin.tiene_microchip, sin.microchip), (False, ''))


class FichaMascotaTest(TestCase):
    """PV-FIC-02: historial clínico en la ficha de la mascota."""

    def setUp(self):
        from datetime import timedelta
        from django.contrib.auth.models import Group, User
        from django.utils import timezone
        from citas.models import Atencion, Cita, TipoAtencion

        self.vet = User.objects.create_user('vet', first_name='Paz', last_name='Herrera')
        self.vet.groups.add(Group.objects.get(name='Veterinarios'))
        self.recepcion = User.objects.create_user('recepcion')
        self.recepcion.groups.add(Group.objects.get(name='Recepción'))

        perro = Especie.objects.create(nombre='Perro')
        self.ana = Cliente.objects.create(rut='15234871-1', nombres='Ana', apellidos='Soto')
        self.bruno = Mascota.objects.create(nombre='Bruno', especie=perro, sexo='macho')
        Tenencia.objects.create(cliente=self.ana, mascota=self.bruno, es_principal=True)
        control = TipoAtencion.objects.create(nombre='Control', duracion_minutos=30, precio=20000)
        hoy = timezone.localdate()

        def atendida(dias, motivo, hora):
            cita = Cita.objects.create(veterinario=self.vet, mascota=self.bruno, cliente=self.ana,
                                       tipo_atencion=control, fecha=hoy - timedelta(days=dias),
                                       hora=hora, estado='completada')
            Atencion.objects.create(cita=cita, motivo=motivo, diagnostico=f'Diagnóstico de {motivo}')

        atendida(40, 'Vacuna antirrábica', '10:00')
        atendida(5, 'Cojera', '11:00')
        atendida(90, 'Primera consulta', '12:00')

    def test_veterinario_ve_el_historial_ordenado_de_lo_mas_reciente(self):
        self.client.force_login(self.vet)
        respuesta = self.client.get(f'/mascotas/{self.bruno.pk}/')
        self.assertEqual(respuesta.status_code, 200)
        motivos = [a.motivo for a in respuesta.context['atenciones']]
        self.assertEqual(motivos, ['Cojera', 'Vacuna antirrábica', 'Primera consulta'])
        self.assertContains(respuesta, 'Diagnóstico de Cojera')

    def test_recepcion_ve_la_ficha_pero_no_los_diagnosticos(self):
        self.client.force_login(self.recepcion)
        respuesta = self.client.get(f'/mascotas/{self.bruno.pk}/')
        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.context['atenciones'])
        self.assertNotContains(respuesta, 'Diagnóstico de Cojera')
        self.assertContains(respuesta, 'Ana Soto')

    def test_sin_permiso_no_entra(self):
        from django.contrib.auth.models import User
        nadie = User.objects.create_user('nadie')
        self.client.force_login(nadie)
        self.assertEqual(self.client.get(f'/mascotas/{self.bruno.pk}/').status_code, 403)

    def test_el_listado_enlaza_a_la_ficha(self):
        self.client.force_login(self.recepcion)
        self.assertContains(self.client.get('/mascotas/'), f'/mascotas/{self.bruno.pk}/"')


class EtiquetasDeAlertaTest(TestCase):
    """PV-CLI-04: etiquetas de alerta en clientes y mascotas."""

    def setUp(self):
        from django.contrib.auth.models import Group
        from .models import Etiqueta
        self.recepcion = User.objects.create_user('recepcion')
        self.recepcion.groups.add(Group.objects.get(name='Recepción'))
        self.client.force_login(self.recepcion)
        perro = Especie.objects.create(nombre='Perro')
        self.ana = Cliente.objects.create(rut='15234871-1', nombres='Ana', apellidos='Soto')
        self.bruno = Mascota.objects.create(nombre='Bruno', especie=perro, sexo='macho')
        Tenencia.objects.create(cliente=self.ana, mascota=self.bruno, es_principal=True)
        self.muerde = Etiqueta.objects.get(nombre='Muerde: usar bozal')
        self.deuda = Etiqueta.objects.get(nombre='Deuda pendiente')

    def test_vienen_etiquetas_iniciales_de_cada_tipo(self):
        from .models import Etiqueta
        self.assertTrue(Etiqueta.objects.filter(para='cliente').exists())
        self.assertTrue(Etiqueta.objects.filter(para='mascota').exists())

    def test_asignar_a_la_mascota_y_al_cliente(self):
        self.client.post(f'/mascotas/{self.bruno.pk}/etiquetas/', {'etiquetas': [self.muerde.pk]})
        self.client.post(f'/clientes/{self.ana.pk}/etiquetas/', {'etiquetas': [self.deuda.pk]})
        self.assertEqual(list(self.bruno.etiquetas.all()), [self.muerde])
        self.assertEqual(list(self.ana.etiquetas.all()), [self.deuda])

    def test_no_se_mezclan_los_tipos(self):
        """Una etiqueta de cliente no se puede pegar a una mascota."""
        self.client.post(f'/mascotas/{self.bruno.pk}/etiquetas/', {'etiquetas': [self.deuda.pk]})
        self.assertFalse(self.bruno.etiquetas.exists())

    def test_desmarcar_las_quita(self):
        self.bruno.etiquetas.add(self.muerde)
        self.client.post(f'/mascotas/{self.bruno.pk}/etiquetas/', {})
        self.assertFalse(self.bruno.etiquetas.exists())

    def test_se_ven_en_las_fichas(self):
        self.bruno.etiquetas.add(self.muerde)
        self.ana.etiquetas.add(self.deuda)
        self.assertContains(self.client.get(f'/mascotas/{self.bruno.pk}/'), 'Muerde: usar bozal')
        self.assertContains(self.client.get(f'/clientes/{self.ana.pk}/'), 'Deuda pendiente')
        self.assertContains(self.client.get('/mascotas/'), 'Muerde: usar bozal')

    def test_el_tutor_no_ve_ni_edita_etiquetas_en_su_portal(self):
        from django.contrib.auth.models import User as U
        self.bruno.etiquetas.add(self.muerde)
        self.ana.etiquetas.add(self.deuda)
        cuenta = U.objects.create_user('152348711')
        self.ana.usuario = cuenta
        self.ana.save()
        self.client.force_login(cuenta)
        respuesta = self.client.get('/mi-prevet/')
        self.assertContains(respuesta, 'Bruno')               # sí ve a su mascota...
        self.assertNotContains(respuesta, 'Muerde')           # ...pero no las alertas internas
        self.assertNotContains(respuesta, 'Deuda pendiente')
        self.assertEqual(self.client.post(f'/clientes/{self.ana.pk}/etiquetas/', {}).status_code, 403)

    def test_solo_administracion_mantiene_el_catalogo(self):
        self.assertEqual(self.client.get('/mascotas/etiquetas/nueva/').status_code, 403)
        from django.contrib.auth.models import Group
        self.recepcion.groups.set([Group.objects.get(name='Administración')])
        respuesta = self.client.post('/mascotas/etiquetas/nueva/', {'nombre': 'Alérgico a anestesia', 'para': 'mascota', 'tono': 'mal', 'activo': 'on'})
        self.assertEqual(respuesta.status_code, 302)


class AsociarMascotaTest(TestCase):
    """PV-CLI-06: asociar a un cliente una mascota ya registrada con otro tutor."""

    def setUp(self):
        from django.contrib.auth.models import Group
        self.recepcion = User.objects.create_user('recepcion')
        self.recepcion.groups.add(Group.objects.get(name='Recepción'))
        self.client.force_login(self.recepcion)
        perro = Especie.objects.create(nombre='Perro')
        self.ana = Cliente.objects.create(rut='15234871-1', nombres='Ana', apellidos='Soto')
        self.pedro = Cliente.objects.create(rut='16890342-1', nombres='Pedro', apellidos='Soto')
        self.bruno = Mascota.objects.create(nombre='Bruno', especie=perro, sexo='macho')
        Tenencia.objects.create(cliente=self.ana, mascota=self.bruno, es_principal=True)

    def test_busca_por_nombre_de_la_mascota_o_rut_del_tutor(self):
        url = f'/clientes/{self.pedro.pk}/mascotas/asociar/'
        self.assertEqual(list(self.client.get(url, {'q': 'brun'}).context['resultados']), [self.bruno])
        self.assertEqual(list(self.client.get(url, {'q': '15.234.871-1'}).context['resultados']), [self.bruno])

    def test_no_ofrece_las_que_ya_son_del_cliente(self):
        respuesta = self.client.get(f'/clientes/{self.ana.pk}/mascotas/asociar/', {'q': 'Bruno'})
        self.assertEqual(list(respuesta.context['resultados']), [])

    def test_asociar_agrega_un_tutor_sin_cambiar_al_responsable(self):
        self.client.post(f'/clientes/{self.pedro.pk}/mascotas/asociar/',
                         {'mascota': self.bruno.pk, 'relacion': 'familiar'})
        vinculo = Tenencia.objects.get(cliente=self.pedro, mascota=self.bruno)
        self.assertEqual(vinculo.relacion, 'familiar')
        self.assertFalse(vinculo.es_principal)
        self.assertEqual(self.bruno.responsable, self.ana)
        self.assertEqual(Mascota.objects.count(), 1)            # no se duplicó la ficha

    def test_sin_responsable_pasa_a_ser_el_principal(self):
        Tenencia.objects.filter(mascota=self.bruno).update(es_principal=False)
        self.client.post(f'/clientes/{self.pedro.pk}/mascotas/asociar/',
                         {'mascota': self.bruno.pk, 'relacion': 'dueno'})
        self.assertTrue(Tenencia.objects.get(cliente=self.pedro, mascota=self.bruno).es_principal)

    def test_asociar_dos_veces_no_duplica(self):
        for _ in range(2):
            self.client.post(f'/clientes/{self.pedro.pk}/mascotas/asociar/',
                             {'mascota': self.bruno.pk, 'relacion': 'familiar'})
        self.assertEqual(Tenencia.objects.filter(cliente=self.pedro, mascota=self.bruno).count(), 1)

    def test_relacion_invalida(self):
        self.client.post(f'/clientes/{self.pedro.pk}/mascotas/asociar/',
                         {'mascota': self.bruno.pk, 'relacion': 'vecino'})
        self.assertFalse(Tenencia.objects.filter(cliente=self.pedro).exists())

    def test_el_nuevo_tutor_puede_agendar_para_la_mascota(self):
        self.client.post(f'/clientes/{self.pedro.pk}/mascotas/asociar/',
                         {'mascota': self.bruno.pk, 'relacion': 'familiar'})
        self.assertIn(self.pedro, self.bruno.tutores.all())

    def test_veterinario_no_asocia(self):
        from django.contrib.auth.models import Group
        self.recepcion.groups.set([Group.objects.get(name='Veterinarios')])
        respuesta = self.client.post(f'/clientes/{self.pedro.pk}/mascotas/asociar/',
                                     {'mascota': self.bruno.pk, 'relacion': 'familiar'})
        self.assertEqual(respuesta.status_code, 403)
