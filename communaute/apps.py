from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CommunauteConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "communaute"
    verbose_name = _("Communauté")
