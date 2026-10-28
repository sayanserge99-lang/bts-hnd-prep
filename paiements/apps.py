from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PaiementsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "paiements"
    verbose_name = _("Paiements")

    def ready(self):
        from . import checks  # noqa: F401  (enregistre les vérifications)
