from django.apps import AppConfig


class TreesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "trees"

    def ready(self):
        from . import gamification
