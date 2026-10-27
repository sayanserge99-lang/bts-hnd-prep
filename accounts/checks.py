from django.conf import settings
from django.core.checks import Tags, Warning, register


@register(Tags.security, deploy=True)
def adresse_admin_par_defaut(app_configs, **kwargs):
    """« admin/ » est la première adresse que les robots essaient : à changer avant la mise en ligne."""
    if settings.ADMIN_URL == "admin/":
        return [Warning(
            "L'administration est à l'adresse par défaut /admin/.",
            hint="Réglez DJANGO_ADMIN_URL dans .env.production (par exemple gestion-7f3k/).",
            id="accounts.W001",
        )]
    return []
