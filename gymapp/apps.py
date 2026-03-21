from django.apps import AppConfig
import os

class GymappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gymapp'

    def ready(self):
        import gymapp.signals
        from gym.services.zk_listener import start
        start()
