from django.contrib.auth.models import Group, Permission, User
from django.test import TestCase
from django.urls import reverse

from .forms import PersonalForm
from .models import Perfil, Personal
from .permisos import es_administrador

CLAVE = 'Huellitas.2026!'


def crear_usuario(username, rol=None, **extra):
    user = User.objects.create_user(username, password=CLAVE,
                                    first_name=username.capitalize(), **extra)
    if rol:
        Perfil.objects.create(usuario=user, rol=rol)
    return user


class GruposInicialesTests(TestCase):
    """La migración de datos deja creados los tres grupos de partida."""

    def test_existen_los_tres_grupos(self):
        nombres = set(Group.objects.values_list('name', flat=True))
        self.assertTrue({'Veterinarios', 'Recepción', 'Administración'} <= nombres)

    def test_recepcion_agenda_pero_no_elimina_citas(self):
        recepcion = Group.objects.get(name='Recepción')
        codenames = set(recepcion.permissions.values_list('codename', flat=True))
        self.assertIn('add_cita', codenames)
        self.assertNotIn('delete_cita', codenames)


class PersonalModeloTests(TestCase):

    def test_personal_no_incluye_a_los_duenos(self):
        crear_usuario('paz', Perfil.Rol.VETERINARIO)
        crear_usuario('ana', Perfil.Rol.DUENO)
        self.assertEqual(list(Personal.objects.values_list('username', flat=True)), ['paz'])

    def test_quien_es_administrador(self):
        self.assertTrue(es_administrador(crear_usuario('jefa', Perfil.Rol.ADMINISTRADOR)))
        self.assertFalse(es_administrador(crear_usuario('vet', Perfil.Rol.VETERINARIO)))
        self.assertFalse(es_administrador(crear_usuario('sin_perfil')))
        self.assertTrue(es_administrador(User.objects.create_superuser('root', password=CLAVE)))


class AccesoAdministracionTests(TestCase):

    def test_sin_sesion_va_al_login(self):
        respuesta = self.client.get(reverse('personal'))
        self.assertRedirects(respuesta, '/login/?next=/administracion/personal/')

    def test_personal_comun_recibe_403(self):
        crear_usuario('vet', Perfil.Rol.VETERINARIO)
        self.client.login(username='vet', password=CLAVE)
        self.assertEqual(self.client.get(reverse('personal')).status_code, 403)
        self.assertEqual(self.client.get(reverse('grupos')).status_code, 403)

    def test_administrador_entra(self):
        crear_usuario('jefa', Perfil.Rol.ADMINISTRADOR)
        self.client.login(username='jefa', password=CLAVE)
        for nombre in ('personal', 'personal_nuevo', 'grupos', 'grupo_nuevo'):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 200, nombre)


class CrearPersonalTests(TestCase):

    def setUp(self):
        self.jefa = crear_usuario('jefa', Perfil.Rol.ADMINISTRADOR)
        self.client.login(username='jefa', password=CLAVE)

    def datos(self, **cambios):
        datos = {
            'first_name': 'Carolina', 'last_name': 'Fuentes', 'username': 'cfuentes',
            'email': 'carolina@clinica.cl', 'rol': Perfil.Rol.RECEPCIONISTA,
            'telefono': '+56 9 1234 5678', 'direccion': '',
            'password1': CLAVE, 'password2': CLAVE,
        }
        datos.update(cambios)
        return datos

    def test_crea_usuario_perfil_y_grupo_por_defecto(self):
        respuesta = self.client.post(reverse('personal_nuevo'), self.datos())
        self.assertRedirects(respuesta, reverse('personal'))

        user = User.objects.get(username='cfuentes')
        self.assertTrue(user.check_password(CLAVE))
        self.assertEqual(user.perfil.rol, Perfil.Rol.RECEPCIONISTA)
        self.assertEqual(list(user.groups.values_list('name', flat=True)), ['Recepción'])
        self.assertFalse(user.is_staff)

    def test_administracion_puede_entrar_al_panel(self):
        self.client.post(reverse('personal_nuevo'), self.datos(rol=Perfil.Rol.ADMINISTRADOR))
        self.assertTrue(User.objects.get(username='cfuentes').is_staff)

    def test_contrasenas_distintas(self):
        respuesta = self.client.post(reverse('personal_nuevo'), self.datos(password2='otra-cosa-123'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(User.objects.filter(username='cfuentes').exists())
        self.assertContains(respuesta, 'Las contraseñas no coinciden.')

    def test_contrasena_demasiado_simple(self):
        respuesta = self.client.post(reverse('personal_nuevo'),
                                     self.datos(password1='123', password2='123'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(User.objects.filter(username='cfuentes').exists())

    def test_editar_sin_cambiar_contrasena(self):
        persona = crear_usuario('paz', Perfil.Rol.VETERINARIO)
        self.client.post(reverse('personal_editar', args=[persona.pk]), {
            'first_name': 'Paz', 'last_name': 'Herrera', 'username': 'paz', 'email': '',
            'rol': Perfil.Rol.VETERINARIO, 'telefono': '222', 'direccion': '', 'is_active': 'on',
        })
        persona.refresh_from_db()
        self.assertEqual(persona.perfil.telefono, '222')
        self.assertTrue(persona.check_password(CLAVE))

    def test_no_puede_quitarse_el_acceso(self):
        form = PersonalForm(data={
            'first_name': 'Jefa', 'last_name': 'X', 'username': 'jefa',
            'rol': Perfil.Rol.ADMINISTRADOR,
        }, instance=self.jefa, editor=self.jefa)
        self.assertFalse(form.is_valid())
        self.assertIn('is_active', form.errors)


class GruposTests(TestCase):

    def setUp(self):
        crear_usuario('jefa', Perfil.Rol.ADMINISTRADOR)
        self.client.login(username='jefa', password=CLAVE)

    def test_crear_grupo_con_permisos(self):
        ver = Permission.objects.get(codename='view_cita')
        agregar = Permission.objects.get(codename='add_mascota')
        self.client.post(reverse('grupo_nuevo'), {
            'name': 'Fin de semana', 'permissions': [ver.pk, agregar.pk],
        })
        grupo = Group.objects.get(name='Fin de semana')
        self.assertEqual(set(grupo.permissions.all()), {ver, agregar})

    def test_formulario_muestra_permisos_en_espanol(self):
        respuesta = self.client.get(reverse('grupo_nuevo'))
        self.assertContains(respuesta, 'Citas')
        self.assertContains(respuesta, 'Agregar')
