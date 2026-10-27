"""Sujets ouverts sans compte : 3 sujets différents par jour, puis un compte gratuit."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Utilisateur
from config import securite
from sujets.models import Sujet

pytestmark = pytest.mark.django_db


@pytest.fixture
def sujets(creer_sujet, session_terminee):
    return [creer_sujet(session_terminee, statut=Sujet.Statut.PUBLIE, titre=f"Sujet {n}") for n in range(5)]


def ouvrir(client, sujet, **entetes):
    return client.get(reverse("sujets:pdf", args=[sujet.pk]), headers=entetes)


def test_trois_sujets_puis_un_compte_gratuit(client, sujets, settings):
    for sujet in sujets[: settings.PDF_VISITEUR_PAR_JOUR]:
        assert ouvrir(client, sujet).status_code == 200

    refus = ouvrir(client, sujets[3])

    fiche = reverse("sujets:detail", args=[sujets[3].pk])
    assert refus.status_code == 302 and refus.url.startswith(reverse("accounts:inscription"))
    assert "next=" + fiche.replace("/", "%2F") in refus.url


def test_rouvrir_un_sujet_deja_ouvert_ne_coute_rien(client, sujets):
    # Un lecteur PDF redemande le fichier par morceaux ; l'étudiant revient aussi sur le même sujet.
    for _ in range(10):
        assert ouvrir(client, sujets[0]).status_code == 200
    assert ouvrir(client, sujets[1]).status_code == 200 and ouvrir(client, sujets[2]).status_code == 200


def test_le_compteur_repart_le_lendemain(client, sujets, settings, monkeypatch):
    for sujet in sujets[:3]:
        ouvrir(client, sujet)
    demain = timezone.localdate() + timedelta(days=1)
    monkeypatch.setattr("sujets.quota.timezone.localdate", lambda: demain)
    securite.PDF_VISITEURS_PAR_IP.effacer("127.0.0.1")  # la limite par adresse expire aussi après 24 h
    assert ouvrir(client, sujets[3]).status_code == 200


def test_un_inscrit_n_est_jamais_limite(client, sujets):
    client.force_login(Utilisateur.objects.create_user(email="awa@example.com", password="Revision-2027"))
    assert all(ouvrir(client, sujet).status_code == 200 for sujet in sujets)


def test_effacer_ses_cookies_ne_suffit_pas(client, sujets, settings):
    """Plusieurs visiteurs derrière une même adresse : la limite par adresse finit par arrêter les nouveaux."""
    settings.PDF_VISITEUR_PAR_JOUR = 1
    for _ in range(securite.PDF_VISITEURS_PAR_IP.maximum):
        client.cookies.clear()
        assert ouvrir(client, sujets[0]).status_code == 200
    client.cookies.clear()
    assert ouvrir(client, sujets[0]).status_code == 302


def test_garder_hors_ligne_recoit_un_refus_et_non_la_page_d_inscription(client, sujets):
    for sujet in sujets[:3]:
        ouvrir(client, sujet)
    # fetch() du bouton « Garder hors ligne » : une redirection suivie mettrait la page d'inscription en cache.
    assert ouvrir(client, sujets[3], sec_fetch_mode="cors").status_code == 429


def test_la_fiche_annonce_ce_qui_reste(client, sujets):
    ouvrir(client, sujets[0])
    page = client.get(reverse("sujets:detail", args=[sujets[1].pk])).content.decode()
    assert "encore 2 sujets à ouvrir aujourd" in page
    for sujet in sujets[1:3]:
        ouvrir(client, sujet)
    assert "la limite du jour est atteinte" in client.get(reverse("sujets:detail", args=[sujets[3].pk])).content.decode()


def test_la_regle_de_publication_passe_avant_le_quota(client, creer_sujet, session_en_cours):
    """Un sujet non publié reste introuvable, même avec des ouvertures disponibles."""
    brouillon = creer_sujet(session_en_cours)
    assert ouvrir(client, brouillon).status_code == 404
    assert client.get(reverse("sujets:detail", args=[brouillon.pk])).status_code == 404


def test_apres_l_inscription_on_revient_au_sujet(client, sujets, comptabilite):
    fiche = reverse("sujets:detail", args=[sujets[0].pk])
    page = client.get(reverse("accounts:inscription"), {"next": fiche}).content.decode()
    assert f'name="next" value="{fiche}"' in page
    reponse = client.post(reverse("accounts:inscription"), {
        "first_name": "Awa", "last_name": "Ngo", "email": "awa@example.com", "langue": "fr",
        "password1": "Revision-2027-ok", "password2": "Revision-2027-ok", "accepte_conditions": "on", "examen": "BTS", "specialite": comptabilite.pk, "next": fiche,
    })
    assert reponse.status_code == 302 and reponse.url == fiche


def test_l_inscription_ne_renvoie_pas_vers_un_autre_site(client, comptabilite):
    reponse = client.post(reverse("accounts:inscription"), {
        "first_name": "Awa", "last_name": "Ngo", "email": "awa@example.com", "langue": "fr",
        "password1": "Revision-2027-ok", "password2": "Revision-2027-ok", "accepte_conditions": "on", "examen": "BTS",
        "specialite": comptabilite.pk,
        "next": "https://piege.example/",
    })
    assert reponse.status_code == 302 and reponse.url == reverse("accounts:profil")
