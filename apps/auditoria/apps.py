from django.apps import AppConfig


class AuditoriaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.auditoria'

    def ready(self):
        from . import signals  # noqa: F401  (conecta las señales de seguridad)
