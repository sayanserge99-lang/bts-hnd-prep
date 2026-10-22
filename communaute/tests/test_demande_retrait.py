"""Procédure de retrait (CDC 10.1) : masquage immédiat, puis acceptation ou refus par un modérateur."""

import pytest
from django.conf import settings
from django.core import mail
from django.urls import reverse

from communaute.models import DemandeRetrait
from sujets.models import Sujet

pytestmark = pytest.mark.django_db

PUBLIE = Sujet.Statut.PUBLIE
MASQUE = Sujet.Statut.MASQUE


@pytest.fixture
def sujet(creer_sujet, session_terminee):
    return creer_sujet(session_terminee, titre="Comptabilité générale", statut=PUBLIE)


def demander(client, sujet, ip=None, **champs):
    entetes = {"HTTP_X_REAL_IP": ip} if ip else {}
    donnees = {
        "sujet": sujet.pk,
        "demandeur_nom": "Éditions du Littoral",
        "demandeur_email": "droits@example.com",
        "motif": "Nous sommes l'éditeur de ce sujet.",
        "certifie_titulaire": "on",
        **champs,
    }
    return client.post(f"{reverse('demande_de_retrait')}?sujet={sujet.pk}", donnees, **entetes)


def test_le_formulaire_vise_le_sujet_de_la_fiche(client, sujet):
    contenu = client.get(reverse("demande_de_retrait"), {"sujet": sujet.pk}).content.decode()
    assert sujet.titre in contenu
    assert 'name="certifie_titulaire"' in contenu


def test_sans_sujet_la_page_explique_la_marche_a_suivre(client):
    contenu = client.get(reverse("demande_de_retrait")).content.decode()
    assert "Demander le retrait de ce document" in contenu


def test_la_fiche_propose_la_demande_de_retrait(client, sujet):
    contenu = client.get(reverse("sujets:detail", args=[sujet.pk])).content.decode()
    assert f"{reverse('demande_de_retrait')}?sujet={sujet.pk}" in contenu


def test_une_demande_masque_le_sujet_tout_de_suite(client, sujet):
    reponse = demander(client, sujet)

    assert reponse.status_code == 302
    sujet.refresh_from_db()
    assert sujet.statut == MASQUE
    assert client.get(reverse("sujets:detail", args=[sujet.pk])).status_code == 404
    assert client.get(reverse("sujets:pdf", args=[sujet.pk])).status_code == 404
    # Accusé de réception envoyé au demandeur.
    assert mail.outbox[0].to == ["droits@example.com"]


def test_la_certification_est_obligatoire(client, sujet):
    demander(client, sujet, certifie_titulaire="")

    assert not DemandeRetrait.objects.exists()
    sujet.refresh_from_db()
    assert sujet.statut == PUBLIE


def test_impossible_de_viser_un_sujet_non_publie(client, creer_sujet, session_en_cours):
    brouillon = creer_sujet(session_en_cours)
    demander(client, brouillon)
    assert not DemandeRetrait.objects.exists()
    brouillon.refresh_from_db()
    assert brouillon.statut == Sujet.Statut.BROUILLON


def test_le_nombre_de_demandes_par_jour_est_limite(client, creer_sujet, session_terminee):
    sujets = [creer_sujet(session_terminee, titre=f"Sujet {n}", statut=PUBLIE) for n in range(4)]
    for cible in sujets:
        demander(client, cible)

    assert DemandeRetrait.objects.count() == settings.DEMANDES_RETRAIT_PAR_JOUR
    sujets[-1].refresh_from_db()
    assert sujets[-1].statut == PUBLIE


def test_derriere_nginx_la_limite_suit_l_adresse_du_visiteur(client, settings, creer_sujet, session_terminee):
    settings.DERRIERE_PROXY = True
    sujets = [creer_sujet(session_terminee, titre=f"Sujet {n}", statut=PUBLIE) for n in range(5)]

    # Toutes les requêtes arrivent de Nginx (même REMOTE_ADDR) ; seul X-Real-IP distingue les visiteurs.
    for cible in sujets[:3]:
        demander(client, cible, ip="203.0.113.7")
    demander(client, sujets[3], ip="198.51.100.20")
    demander(client, sujets[4], ip="203.0.113.7")

    assert DemandeRetrait.objects.count() == 4
    assert not DemandeRetrait.objects.filter(sujet=sujets[4]).exists()


def test_accepter_supprime_le_document_et_garde_la_trace(client, sujet):
    demander(client, sujet)
    demande = DemandeRetrait.objects.get()
    chemin = sujet.fichier.path

    demande.accepter()

    sujet.refresh_from_db()
    assert sujet.statut == MASQUE
    assert not sujet.fichier
    assert not __import__("os").path.exists(chemin)
    assert DemandeRetrait.objects.get().statut == DemandeRetrait.Statut.ACCEPTEE


def test_refuser_republie_le_sujet(client, sujet):
    demander(client, sujet)

    DemandeRetrait.objects.get().refuser()

    sujet.refresh_from_db()
    assert sujet.statut == PUBLIE


def test_refuser_ne_publie_jamais_un_sujet_de_session_en_cours(creer_sujet, session_en_cours):
    brouillon = creer_sujet(session_en_cours)
    demande = DemandeRetrait.objects.create(
        demandeur_nom="X", demandeur_email="x@example.com", sujet=brouillon, motif="Test"
    )

    demande.refuser()

    brouillon.refresh_from_db()
    assert brouillon.statut == Sujet.Statut.BROUILLON


def test_actions_de_l_admin(admin_client, client, sujet):
    demander(client, sujet)
    demande = DemandeRetrait.objects.get()

    admin_client.post(
        reverse("admin:communaute_demanderetrait_changelist"),
        {"action": "refuser", "_selected_action": [demande.pk]},
    )

    sujet.refresh_from_db()
    assert sujet.statut == PUBLIE
