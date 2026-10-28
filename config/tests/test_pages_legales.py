"""Pages légales (CDC 10) : brouillons FR et EN, champs à compléter visibles, liens depuis l'inscription."""

import pytest
from django.conf import settings
from django.urls import reverse

pytestmark = pytest.mark.django_db

PAGES = ["confidentialite", "conditions_utilisation", "mentions_legales"]


@pytest.mark.parametrize("nom", PAGES)
@pytest.mark.parametrize("langue, a_completer", [("fr", "[À COMPLÉTER"), ("en", "[TO BE COMPLETED")])
def test_chaque_page_existe_dans_les_deux_langues(client, nom, langue, a_completer):
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = langue
    page = client.get(reverse(nom)).content.decode()
    assert f'<html lang="{langue}">' in page
    assert a_completer in page  # structure, NIU, adresse, contact, hébergeur restent à remplir
    assert "<mark>" in page


@pytest.mark.parametrize("langue, mots", [
    ("fr", ["Copie locale des réponses d'examen blanc", "IndexedDB", "à la déconnexion", "Sentry"]),
    ("en", ["Local copy of mock exam answers", "IndexedDB", "when you sign out", "Sentry"]),
])
def test_la_confidentialite_decrit_la_copie_locale_des_reponses(client, langue, mots):
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = langue
    page = client.get(reverse("confidentialite")).content.decode().replace("&#x27;", "'")
    for mot in mots:
        assert mot in page, mot


def test_les_mentions_legales_demandent_structure_niu_adresse_contact_hebergeur(client):
    page = client.get(reverse("mentions_legales")).content.decode()
    for champ in ("structure", "NIU", "adresse", "e-mail", "hébergeur"):
        assert "[À COMPLÉTER" in page and champ in page, champ


def test_l_inscription_mene_aux_conditions_d_utilisation(client):
    page = client.get(reverse("accounts:inscription")).content.decode().replace("&#x27;", "'")
    assert reverse("conditions_utilisation") in page
    assert "J'accepte les conditions d'utilisation et la politique de confidentialité." in page
