"""Pruebas de la importación desde Excel o CSV (PV-DAT-01 y PV-DAT-02)."""
import io

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import Workbook

from citas.models import Cita, TipoAtencion
from mascotas.models import Cliente, Especie, Mascota, Tenencia
from usuarios.models import Perfil


def excel(filas, nombre='datos.xlsx'):
    libro = Workbook()
    for fila in filas:
        libro.active.append(fila)
    archivo = io.BytesIO()
    libro.save(archivo)
    return SimpleUploadedFile(nombre, archivo.getvalue())


def csv(texto, nombre='datos.csv'):
    return SimpleUploadedFile(nombre, texto.encode('utf-8'))


class ImportarTest(TestCase):

    def setUp(self):
        from django.contrib.auth.models import Group
        self.jefa = User.objects.create_user('jefa')
        self.jefa.groups.add(Group.objects.get(name='Administración'))
        self.client.force_login(self.jefa)
        self.perro = Especie.objects.create(nombre='Perro')
        self.vet = User.objects.create_user('paz', first_name='Paz', last_name='Herrera')
        Perfil.objects.create(usuario=self.vet, rol='veterinario')
        self.control = TipoAtencion.objects.create(nombre='Control', duracion_minutos=30, precio=20000)

    def importar(self, tipo, archivo):
        return self.client.post('/importar/', {'tipo': tipo, 'archivo': archivo})

    # ---------- PV-DAT-01 ----------

    def test_carga_clientes_y_mascotas(self):
        respuesta = self.importar('clientes', excel([
            ['RUT', 'Nombres', 'Apellidos', 'Teléfono', 'Correo', 'Mascota', 'Tipo de mascota', 'Sexo', 'Fecha de nacimiento'],
            ['15.234.871-1', 'Ana', 'Soto', '912345678', '', 'Bruno', 'Perro', 'Macho', '15-03-2020'],
            ['15.234.871-1', 'Ana', 'Soto', '912345678', '', 'Luna', 'perro', 'Hembra', ''],
        ]))
        self.assertEqual(respuesta.context['resultado']['clientes'], 1)
        self.assertEqual(respuesta.context['resultado']['mascotas'], 2)
        ana = Cliente.objects.get(rut='15234871-1')
        self.assertEqual(sorted(m.nombre for m in ana.mascotas.all()), ['Bruno', 'Luna'])

    def test_importar_dos_veces_no_duplica(self):
        filas = [['RUT', 'Nombres', 'Apellidos', 'Mascota', 'Tipo de mascota', 'Sexo'],
                 ['15.234.871-1', 'Ana', 'Soto', 'Bruno', 'Perro', 'Macho']]
        self.importar('clientes', excel(filas))
        respuesta = self.importar('clientes', excel(filas))
        self.assertEqual(respuesta.context['resultado']['omitidas'], 1)
        self.assertEqual(Mascota.objects.count(), 1)

    def test_las_filas_con_error_se_informan_y_las_demas_se_cargan(self):
        respuesta = self.importar('clientes', csv(
            'RUT;Nombres;Apellidos;Mascota;Tipo de mascota;Sexo\n'
            '11.111.111-2;Rut;Malo;Toby;Perro;Macho\n'
            '15.234.871-1;Ana;Soto;Bruno;Dinosaurio;Macho\n'
            '16.890.342-1;Matías;Silva;Kira;Perro;Hembra\n'))
        resultado = respuesta.context['resultado']
        self.assertEqual(resultado['total_errores'], 2)
        self.assertTrue(resultado['errores'][0].startswith('Fila 2'))
        self.assertIn('Dinosaurio', resultado['errores'][1])
        # La fila con error no deja al cliente a medias.
        self.assertFalse(Cliente.objects.filter(rut='15234871-1').exists())
        self.assertTrue(Mascota.objects.filter(nombre='Kira').exists())

    def test_avisa_si_faltan_columnas(self):
        respuesta = self.importar('clientes', excel([['Nombre'], ['Ana']]))
        self.assertIn('RUT', respuesta.context['error'])

    def test_solo_administracion(self):
        from django.contrib.auth.models import Group
        recepcion = User.objects.create_user('recepcion')
        recepcion.groups.add(Group.objects.get(name='Recepción'))
        self.client.force_login(recepcion)
        self.assertEqual(self.client.get('/importar/').status_code, 403)

    def test_descarga_la_plantilla(self):
        respuesta = self.client.get('/importar/plantilla/citas/')
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('plantilla_citas', respuesta['Content-Disposition'])

    # ---------- PV-DAT-02 ----------

    def crear_ana(self):
        ana = Cliente.objects.create(rut='15234871-1', nombres='Ana', apellidos='Soto')
        bruno = Mascota.objects.create(nombre='Bruno', especie=self.perro, sexo='macho')
        Tenencia.objects.create(cliente=ana, mascota=bruno, es_principal=True)
        return ana

    def test_carga_citas_con_su_estado(self):
        self.crear_ana()
        respuesta = self.importar('citas', excel([
            ['RUT', 'Mascota', 'Fecha', 'Hora', 'Profesional', 'Tipo de atención', 'Estado'],
            ['15.234.871-1', 'Bruno', '02-09-2026', '10:30', 'Paz Herrera', 'Control', 'No asistió'],
            ['15.234.871-1', 'bruno', '09-09-2026', '11:00', 'paz', 'control', 'Asistió'],
            ['15.234.871-1', 'Bruno', '16-09-2026', '11:00', 'Paz Herrera', 'Control', 'Cancelada'],
        ]))
        self.assertEqual(respuesta.context['resultado']['citas'], 3)
        estados = sorted(Cita.objects.values_list('estado', flat=True))
        self.assertEqual(estados, ['cancelada', 'completada', 'no_asistio'])

    def test_cita_repetida_no_se_duplica(self):
        self.crear_ana()
        filas = [['RUT', 'Mascota', 'Fecha', 'Hora', 'Profesional', 'Tipo de atención', 'Estado'],
                 ['15.234.871-1', 'Bruno', '02-09-2026', '10:30', 'Paz Herrera', 'Control', 'Asistió']]
        self.importar('citas', excel(filas))
        self.importar('citas', excel(filas))
        self.assertEqual(Cita.objects.count(), 1)

    def test_cita_de_cliente_que_no_existe(self):
        respuesta = self.importar('citas', excel([
            ['RUT', 'Mascota', 'Fecha', 'Hora', 'Profesional', 'Tipo de atención', 'Estado'],
            ['15.234.871-1', 'Bruno', '02-09-2026', '10:30', 'Paz Herrera', 'Control', 'Asistió'],
        ]))
        self.assertIn('impórtalo primero', respuesta.context['resultado']['errores'][0])
        self.assertFalse(Cita.objects.exists())

    def test_cita_futura_no_puede_venir_como_inasistencia(self):
        self.crear_ana()
        respuesta = self.importar('citas', excel([
            ['RUT', 'Mascota', 'Fecha', 'Hora', 'Profesional', 'Tipo de atención', 'Estado'],
            ['15.234.871-1', 'Bruno', '01-01-2099', '10:30', 'Paz Herrera', 'Control', 'No asistió'],
        ]))
        self.assertEqual(respuesta.context['resultado']['total_errores'], 1)
