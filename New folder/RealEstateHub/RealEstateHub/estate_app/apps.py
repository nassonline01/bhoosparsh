from django.apps import AppConfig


class EstateAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'estate_app'
    
    def ready(self):
        """Import signals when app is ready"""
        import estate_app.signals

