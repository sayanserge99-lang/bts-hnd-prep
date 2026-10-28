from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class EntrainementConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "entrainement"
    verbose_name = _("Entraînement")
