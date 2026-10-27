"""Pages d'erreur du site (et non les pages brutes de Django) : introuvable, refus, expiration, panne."""

import pytest
from django.core.exceptions import PermissionDenied
from django.test import Client
from django.urls import path

from config import urls as site_urls

pytestmark = pytest.mark.django_db


def plante(request):
    raise RuntimeError("panne volontaire")


def interdit(request):
    raise PermissionDenied


# Les adresses d'essai, plus celles du site : les gabarits d'erreur ont besoin des liens du menu.
urlpatterns = [path("plante/", plante), path("interdit/", interdit), *site_urls.urlpatterns]


def test_page_introuvable(client):
    reponse = client.get("/cette-page-n-existe-pas/")
    contenu = reponse.content.decode()
    assert reponse.status_code == 404
    assert "Page introuvable" in contenu and "Retour à l'accueil" in contenu
    assert "non affiliée au MINESUP" in contenu  # le pied de page du site : c'est bien notre gabarit


def test_panne_du_serveur(settings):
    settings.ROOT_URLCONF = __name__
    client = Client(raise_request_exception=False)
    reponse = client.get("/plante/")
    contenu = reponse.content.decode()
    assert reponse.status_code == 500
    assert "Un problème est survenu" in contenu and "Something went wrong" in contenu
    assert "panne volontaire" not in contenu and "Traceback" not in contenu  # rien d'interne n'est montré


def test_acces_refuse(settings, client):
    settings.ROOT_URLCONF = __name__
    reponse = client.get("/interdit/")
    assert reponse.status_code == 403 and "Accès refusé" in reponse.content.decode()


def test_formulaire_expire():
    # Formulaire envoyé sans jeton CSRF valide (page restée ouverte trop longtemps, ou autre site).
    client = Client(enforce_csrf_checks=True)
    reponse = client.post("/compte/connexion/", {"username": "a@example.com", "password": "x"})
    assert reponse.status_code == 403 and "La page a expiré" in reponse.content.decode()
