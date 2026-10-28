"""Test d'envoi des e-mails au démarrage (manage.py verifier_email) et avertissements de mise en ligne."""

from io import StringIO

import pytest
from django.core import mail
from django.core.checks import run_checks
from django.core.management import CommandError, call_command


def lancer(*args):
    sortie, erreurs = StringIO(), StringIO()
    call_command("verifier_email", *args, stdout=sortie, stderr=erreurs)
    return sortie.getvalue(), erreurs.getvalue()


def test_un_e_mail_de_test_part_aux_administrateurs(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.ADMINS = [("Serge Alain", "serge@example.com")]
    sortie, _ = lancer()
    assert len(mail.outbox) == 1 and mail.outbox[0].to == ["serge@example.com"]
    assert "test d'envoi" in mail.outbox[0].subject and "E-mails OK" in sortie


def test_un_fournisseur_injoignable_est_signale_sans_le_mot_de_passe(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    settings.EMAIL_HOST, settings.EMAIL_PORT, settings.EMAIL_TIMEOUT = "127.0.0.1", 1, 2  # rien n'écoute là
    settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD = "envoi@example.com", "mot-de-passe-secret"
    settings.ADMINS = [("Serge Alain", "serge@example.com")]

    _, erreurs = lancer()  # sans --strict : le site démarre quand même
    assert "ÉCHEC de l'envoi des e-mails (127.0.0.1:1" in erreurs and "mot-de-passe-secret" not in erreurs

    with pytest.raises(CommandError, match="ÉCHEC") as erreur:
        lancer("--strict")
    assert "mot-de-passe-secret" not in str(erreur.value)


def test_en_developpement_rien_a_verifier(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    sortie, _ = lancer()
    assert "rien à vérifier" in sortie and not mail.outbox


def test_la_mise_en_ligne_avertit_sans_fournisseur_ni_destinataire_des_alertes(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    settings.EMAIL_HOST, settings.ADMINS = "localhost", []
    codes = {message.id for message in run_checks(include_deployment_checks=True)}
    assert {"accounts.W002", "accounts.W003"} <= codes
    settings.EMAIL_HOST, settings.ADMINS = "smtp-relay.example.com", [("Équipe", "equipe@example.com")]
    codes = {message.id for message in run_checks(include_deployment_checks=True)}
    assert not {"accounts.W002", "accounts.W003"} & codes


def test_le_demarrage_de_production_lance_le_test_sans_bloquer_le_site():
    from pathlib import Path

    from django.conf import settings as reglages

    dockerfile = (Path(reglages.BASE_DIR) / "Dockerfile").read_text(encoding="utf-8")
    assert "(python manage.py verifier_email || true) && gunicorn" in dockerfile
