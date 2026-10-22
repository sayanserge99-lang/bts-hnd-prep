from django.apps import AppConfig


class SujetsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sujets"
    verbose_name = "Sujets"

    def ready(self):
        from . import signals  # noqa: F401
