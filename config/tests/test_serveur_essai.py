"""Serveur d'essai (Oracle gratuit) : bandeau, aucun moteur de recherche, données de démonstration sans mot de passe
connu de tous, et jamais avec le paiement."""

import os
import subprocess
import sys

import pytest
from django.core.management import CommandError, call_command
from django.urls import reverse

from accounts.models import Utilisateur

pytestmark = pytest.mark.django_db


def test_bandeau_et_moteurs_de_recherche(client, settings):
    page = client.get(reverse("accueil")).content.decode()
    assert "Serveur d’essai" not in page and "noindex" not in page
    assert "Disallow: /\n" not in client.get("/robots.txt").content.decode()

    settings.SERVEUR_ESSAI = True
    page = client.get(reverse("accueil")).content.decode()
    assert "Serveur d’essai : comptes et sujets fictifs" in page and 'content="noindex, nofollow"' in page
    assert client.get("/robots.txt").content.decode() == "User-agent: *\nDisallow: /\n"


def test_donnees_de_demo_sur_le_serveur_d_essai_sans_mot_de_passe_public(settings, tmp_path):
    settings.DEBUG = False
    with pytest.raises(CommandError):
        call_command("donnees_demo", stdout=open(os.devnull, "w"))

    settings.SERVEUR_ESSAI = True
    sortie = tmp_path / "sortie.txt"
    with open(sortie, "w", encoding="utf-8") as flux:
        call_command("donnees_demo", stdout=flux)
    texte = sortie.read_text(encoding="utf-8")
    enseignante = Utilisateur.objects.get(email="enseignant.demo@example.com")
    assert not enseignante.check_password("Demo-BTS-2027")
    assert not Utilisateur.objects.get(email="etudiant.demo@example.com").check_password("Demo-BTS-2027")
    mot_de_passe = texte.split("enseignant.demo@example.com (mot de passe ")[1].split(")")[0]
    assert enseignante.check_password(mot_de_passe)


def test_le_serveur_d_essai_refuse_de_demarrer_avec_le_paiement():
    environnement = {**os.environ, "DJANGO_SERVEUR_ESSAI": "1", "EXPLOITANT_STRUCTURE": "BTS-HND Prep SARL",
                     "EXPLOITANT_NIU": "M012345678901A"}
    resultat = subprocess.run([sys.executable, "-c", "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup()"],
                              env=environnement, capture_output=True, text=True)
    assert resultat.returncode != 0 and "incompatible avec le paiement" in resultat.stderr
