"""Pages publiques de la V1 : accueil, catalogue, fiche sujet et PDF."""

import pytest
from django.urls import reverse

from sujets.models import Sujet

pytestmark = pytest.mark.django_db

PUBLIE = Sujet.Statut.PUBLIE


@pytest.fixture
def publie(creer_sujet, session_terminee, comptabilite):
    sujet = creer_sujet(session_terminee, titre="Comptabilité générale", statut=PUBLIE,
                        texte_extrait="Amortissement dégressif")
    sujet.specialites.add(comptabilite)
    return sujet


@pytest.fixture
def brouillon(creer_sujet, session_en_cours, comptabilite):
    sujet = creer_sujet(session_en_cours, titre="Sujet de la session en cours")
    sujet.specialites.add(comptabilite)
    return sujet


@pytest.fixture
def masque(creer_sujet, session_terminee):
    return creer_sujet(session_terminee, titre="Sujet sous demande de retrait", statut=Sujet.Statut.MASQUE)


def test_accueil(client, publie):
    reponse = client.get(reverse("accueil"))

    assert reponse.status_code == 200
    contenu = reponse.content.decode()
    assert "non affiliée au MINESUP" in contenu
    assert "Paiement bientôt disponible" in contenu
    assert "Comptabilité générale" in contenu


def test_la_liste_ne_montre_que_les_sujets_publies(client, publie, brouillon, masque):
    contenu = client.get(reverse("sujets:liste"), {"examen": "BTS"}).content.decode()

    assert publie.titre in contenu
    assert brouillon.titre not in contenu
    assert masque.titre not in contenu


def test_un_sujet_non_publie_est_introuvable(client, brouillon, masque):
    for sujet in (brouillon, masque):
        assert client.get(reverse("sujets:detail", args=[sujet.pk])).status_code == 404
        assert client.get(reverse("sujets:pdf", args=[sujet.pk])).status_code == 404


def test_les_fichiers_ne_sont_pas_servis_par_leur_url(client, brouillon):
    # Le PDF d'un sujet non publié ne doit pas être lisible en devinant son chemin.
    assert client.get("/" + brouillon.fichier.url.lstrip("/")).status_code == 404


def test_fiche_et_pdf_d_un_sujet_publie(client, publie):
    fiche = client.get(reverse("sujets:detail", args=[publie.pk]))
    assert fiche.status_code == 200
    assert "Coefficient" in fiche.content.decode()
    assert publie.source in fiche.content.decode()

    lecture = client.get(reverse("sujets:pdf", args=[publie.pk]))
    assert lecture["Content-Type"] == "application/pdf"
    assert lecture["Content-Disposition"].startswith("inline")

    telechargement = client.get(reverse("sujets:pdf", args=[publie.pk]), {"telecharger": "1"})
    assert telechargement["Content-Disposition"].startswith("attachment")


def resultats(client, **filtres):
    # Fragment des résultats seul : le nom de la matière figure aussi dans le filtre « Matière ».
    return client.get(reverse("sujets:liste"), {"examen": "BTS", **filtres}, headers={"HX-Request": "true"}).content.decode()


def test_filtre_par_annee(client, publie):
    assert publie.titre in resultats(client, annee="2025")
    assert publie.titre not in resultats(client, annee="2024")


def test_recherche_dans_le_catalogue(client, publie):
    assert publie.titre in resultats(client, q="degressif")
    assert publie.titre not in resultats(client, q="marketing")


def test_htmx_ne_renvoie_que_les_resultats(client, publie):
    reponse = client.get(reverse("sujets:liste"), {"examen": "BTS"}, headers={"HX-Request": "true"})

    contenu = reponse.content.decode()
    assert publie.titre in contenu
    assert "<html" not in contenu


def test_restauration_d_historique_htmx_renvoie_la_page_complete(client, publie):
    reponse = client.get(
        reverse("sujets:liste"), {"examen": "BTS"},
        headers={"HX-Request": "true", "HX-History-Restore-Request": "true"},
    )
    assert "<html" in reponse.content.decode()


def test_options_de_specialites(client, comptabilite):
    contenu = client.get(reverse("options_specialites"), {"examen": "BTS"}).content.decode()
    assert comptabilite.nom in contenu


@pytest.mark.parametrize(
    "nom", ["mentions_legales", "confidentialite", "conditions_de_vente", "demande_de_retrait", "contact"]
)
def test_pages_legales(client, nom):
    assert client.get(reverse(nom)).status_code == 200
