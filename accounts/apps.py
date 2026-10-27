from django.apps import AppConfig
from django.db.models.signals import m2m_changed, post_migrate


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "Comptes"

    def ready(self):
        from . import checks  # noqa: F401  (enregistre les vérifications)
        from .models import Utilisateur
        from .signals import ouvrir_l_administration, synchroniser_administrateur

        post_migrate.connect(synchroniser_administrateur, dispatch_uid="accounts.synchroniser_administrateur")
        m2m_changed.connect(
            ouvrir_l_administration, sender=Utilisateur.groups.through, dispatch_uid="accounts.ouvrir_l_administration"
        )
