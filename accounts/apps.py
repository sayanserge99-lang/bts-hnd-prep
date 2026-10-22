from django.apps import AppConfig
from django.db.models.signals import post_migrate


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "Comptes"

    def ready(self):
        from .signals import synchroniser_administrateur

        post_migrate.connect(synchroniser_administrateur, dispatch_uid="accounts.synchroniser_administrateur")
