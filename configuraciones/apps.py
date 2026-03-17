from django.apps import AppConfig

class ConfiguracionesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'configuraciones'

    def ready(self):
        import configuraciones.signals
