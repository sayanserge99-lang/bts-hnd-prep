from django.conf import settings
from django.core.checks import Tags, Warning, register

SMTP = "django.core.mail.backends.smtp.EmailBackend"


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


@register(deploy=True)
def envoi_des_emails(app_configs, **kwargs):
    """Sans fournisseur SMTP, ni réinitialisation de mot de passe, ni reçus, ni alertes de l'équipe."""
    avertissements = []
    if settings.EMAIL_BACKEND == SMTP and settings.EMAIL_HOST in ("", "localhost"):
        avertissements.append(Warning(
            "Aucun fournisseur d'e-mails : EMAIL_HOST est vide ou vaut localhost.",
            hint="Renseignez EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD dans .env.production, "
                 "puis lancez python manage.py verifier_email.",
            id="accounts.W002",
        ))
    if not settings.ADMINS:
        avertissements.append(Warning(
            "DJANGO_ADMINS est vide : personne ne reçoit les alertes (demandes de retrait, test d'envoi au démarrage).",
            hint='Exemple : DJANGO_ADMINS=Serge Alain <adresse@exemple.com>',
            id="accounts.W003",
        ))
    return avertissements
