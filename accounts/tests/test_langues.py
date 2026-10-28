"""Bilinguisme (CDC 4) : interface entièrement traduite, changement de langue en un clic."""

import re
import shutil
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.urls import reverse

from accounts.models import Utilisateur

FICHIER_PO = Path(settings.BASE_DIR) / "locale" / "en" / "LC_MESSAGES" / "django.po"


def sans_traduction(fichier_po):
    """Entrées du catalogue sans traduction anglaise (vides ou « fuzzy »), hors entrées obsolètes (#~)."""
    manquants = []
    for bloc in fichier_po.read_text(encoding="utf-8").split("\n\n")[1:]:
        if bloc.lstrip().startswith("#~"):
            continue
        if "#, fuzzy" in bloc:
            manquants.append(bloc)
        msgid = re.search(r'^msgid "(.*)"', bloc, re.MULTILINE)
        traductions = re.findall(r'^msgstr(?:\[\d\])? "(.*)"((?:\n".*")*)', bloc, re.MULTILINE)
        if msgid and any(not (debut or suite.strip()) for debut, suite in traductions):
            manquants.append(msgid.group(1))
    return manquants


def test_tous_les_textes_ont_une_traduction_anglaise():
    """Échoue si un texte a été ajouté sans être traduit (relancer makemessages puis compléter le .po)."""
    assert sans_traduction(FICHIER_PO) == []


@pytest.mark.skipif(not shutil.which("msgmerge"), reason="gettext absent (apt install gettext)")
def test_chaque_chaine_marquee_a_sa_traduction_anglaise(tmp_path, settings, monkeypatch):
    """Extrait les chaînes marquées du code actuel (makemessages, sur une copie du projet) et vérifie que chacune
    a sa traduction anglaise : une chaîne marquée mais absente du .po, ou ajoutée sans traduction, fait échouer."""
    copie = tmp_path / "projet"
    shutil.copytree(
        settings.BASE_DIR, copie,
        ignore=shutil.ignore_patterns(".git", ".venv", "node_modules", "media", "static", "staticfiles", "tests_js",
                                      "assets", "__pycache__", "*.mo", "*.pdf", "*.png", "*.jpg", "*.webp"),
    )
    settings.LOCALE_PATHS = [copie / "locale"]
    monkeypatch.chdir(copie)
    call_command("makemessages", locale=["en"], verbosity=0)
    assert sans_traduction(copie / "locale" / "en" / "LC_MESSAGES" / "django.po") == []


@pytest.mark.django_db
def test_l_interface_passe_en_anglais(client):
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"
    contenu = client.get(reverse("accueil")).content.decode()

    assert '<html lang="en">' in contenu
    assert "Past papers" in contenu
    assert "Prices will be announced" in contenu
    # La mention d'indépendance reste dans les deux langues.
    assert "non affiliée au MINESUP" in contenu


@pytest.mark.django_db
def test_changer_de_langue_en_un_clic(client):
    reponse = client.post(reverse("set_language"), {"language": "en", "next": "/"})

    assert reponse.status_code == 302
    assert "Past papers" in client.get(reverse("accueil")).content.decode()


@pytest.mark.django_db
def test_la_langue_choisie_est_enregistree_pour_un_utilisateur_connecte(client):
    utilisateur = Utilisateur.objects.create_user(email="ndi@example.com", password="Revision-HND-2027")
    client.force_login(utilisateur)

    client.post(reverse("set_language"), {"language": "en", "next": "/"})

    utilisateur.refresh_from_db()
    assert utilisateur.langue == "en"
