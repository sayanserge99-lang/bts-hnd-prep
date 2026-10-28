"""Bêta : bannière en haut des pages et « Donner mon avis » (enregistré en base, lu dans l'administration)."""

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import Utilisateur
from communaute.models import AvisBeta
from config import securite

pytestmark = pytest.mark.django_db


def donner(client, **champs):
    return client.post(reverse("avis_beta"), {"type": "probleme", "message": "Le bouton Suivante ne marche pas.",
                                              "page": "/sujets/", **champs})


def test_la_banniere_est_sur_les_pages_et_mene_au_formulaire_avec_la_page(client):
    page = client.get(reverse("sujets:liste")).content.decode()
    assert "Bêta" in page and "Donner mon avis" in page
    assert f'{reverse("avis_beta")}?page=/sujets/' in page.replace("%2F", "/")


def test_la_banniere_se_retire_par_un_reglage(client, settings):
    settings.BETA = False
    assert "Donner mon avis" not in client.get(reverse("accueil")).content.decode()


def test_l_avis_est_enregistre_et_l_etudiant_revient_a_sa_page(client):
    etudiant = Utilisateur.objects.create_user(email="awa@example.com", password="Revision-2027")
    client.force_login(etudiant)
    reponse = donner(client)
    assert reponse.status_code == 302 and reponse.url == "/sujets/"
    avis = AvisBeta.objects.get()
    assert avis.type == "probleme" and avis.page == "/sujets/" and avis.utilisateur == etudiant
    assert "Merci pour votre avis" in client.get(reponse.url).content.decode()


def test_sans_compte_ni_e_mail(client):
    assert donner(client).status_code == 302
    assert AvisBeta.objects.get().utilisateur is None
    assert 'name="email"' not in client.get(reverse("avis_beta")).content.decode()


def test_jamais_de_retour_vers_un_autre_site(client):
    reponse = donner(client, page="//exemple-malveillant.com/")
    assert reponse.url == "/" and AvisBeta.objects.get().page == ""


def test_robots_message_trop_court_et_limite(client):
    donner(client, site_web="http://spam.example")
    assert not AvisBeta.objects.exists()
    assert donner(client, message="ok").status_code == 200 and not AvisBeta.objects.exists()
    for _ in range(securite.AVIS_BETA_PAR_IP.maximum + 2):
        donner(client)
    assert AvisBeta.objects.count() == securite.AVIS_BETA_PAR_IP.maximum


def test_visible_dans_l_administration(client):
    AvisBeta.objects.create(type="idee", message="Ajouter les sujets de 2019.", page="/")
    admin = Utilisateur.objects.create_user(email="admin@example.com", password="Admin-BTS-2027", is_staff=True)
    admin.groups.add(Group.objects.get(name="Administrateur"))
    client.force_login(admin)
    page = client.get(reverse("admin:communaute_avisbeta_changelist")).content.decode()
    assert "Ajouter les sujets de 2019." in page

