from django.apps import AppConfig


class CitasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'citas'
    verbose_name = 'Agenda y citas'

    def ready(self):
        # Conecta el registro de cambios de las citas (PV-ADM-05).
        from . import auditoria  # noqa: F401
