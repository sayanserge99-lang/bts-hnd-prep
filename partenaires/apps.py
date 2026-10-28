from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PartenairesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "partenaires"
    verbose_name = _("Partenaires")
