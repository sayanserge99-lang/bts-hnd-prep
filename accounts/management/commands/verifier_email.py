"""Test d'envoi des e-mails, lancé au démarrage du site en production (Dockerfile) et à la main :
    docker compose -f compose.prod.yaml --env-file .env.production exec web python manage.py verifier_email

Se connecte au fournisseur SMTP (réglages EMAIL_* de .env.production) puis envoie un e-mail de test aux
administrateurs (DJANGO_ADMINS). Sans e-mails, ni réinitialisation de mot de passe, ni reçus, ni alertes : un échec
est écrit en clair dans les journaux, sans le mot de passe. Il n'empêche pas le site de démarrer, sauf avec --strict.
"""

import smtplib

from django.conf import settings
from django.core.mail import get_connection, send_mail
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

CONSOLE = "django.core.mail.backends.console.EmailBackend"


class Command(BaseCommand):
    help = "Vérifie l'envoi des e-mails (connexion SMTP, puis e-mail de test aux administrateurs)."

    def add_arguments(self, parser):
        parser.add_argument("--destinataire", help="Adresse du test (par défaut : DJANGO_ADMINS).")
        parser.add_argument("--strict", action="store_true", help="Échouer (code de sortie 1) si l'envoi ne marche pas.")

    def handle(self, *args, destinataire=None, strict=False, **options):
        if settings.EMAIL_BACKEND == CONSOLE:
            self.stdout.write("EMAIL_BACKEND = console : les e-mails sont affichés dans les journaux, rien à vérifier.")
            return
        serveur = f"{settings.EMAIL_HOST}:{settings.EMAIL_PORT}"
        destinataires = [destinataire] if destinataire else [adresse for _, adresse in settings.ADMINS]
        try:
            connexion = get_connection(fail_silently=False)
            connexion.open()
            if destinataires:
                send_mail(
                    "BTS-HND Prep : test d'envoi des e-mails",
                    f"Le site a démarré le {timezone.localtime():%d/%m/%Y à %H:%M} et peut envoyer des e-mails "
                    f"(serveur {serveur}).\nCet e-mail est envoyé à chaque démarrage, pour vérifier le fournisseur.",
                    None,
                    destinataires,
                    connection=connexion,
                )
            connexion.close()
        except (smtplib.SMTPException, OSError) as erreur:  # refus, mauvais identifiants, serveur injoignable
            # Le message d'erreur du serveur, jamais le mot de passe (EMAIL_HOST_PASSWORD).
            message = f"ÉCHEC de l'envoi des e-mails ({serveur}, utilisateur « {settings.EMAIL_HOST_USER} ») : {erreur}"
            if strict:
                raise CommandError(message) from erreur
            self.stderr.write(message)
            return
        if destinataires:
            self.stdout.write(self.style.SUCCESS(f"E-mails OK : test envoyé par {serveur} à {', '.join(destinataires)}."))
        else:
            self.stdout.write(self.style.WARNING(
                f"Connexion SMTP OK ({serveur}), mais DJANGO_ADMINS est vide : aucun e-mail de test envoyé."
            ))
