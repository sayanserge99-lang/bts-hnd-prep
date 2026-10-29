"""« Vouliez-vous dire … ? » : fautes de frappe dans la recherche des sujets et du forum."""

import pytest
from django.urls import reverse

from forum.models import Discussion, Reponse
from forum.tests.test_forum import awa, ben, question  # noqa: F401 (fixtures)
from sujets.models import Sujet
from sujets.suggestion import construire, suggestion

pytestmark = pytest.mark.django_db

VOCABULAIRE = construire(["Calculez l'amortissement dégressif du matériel.", "Le bilan fonctionnel, le bilan 2025."])


def test_corrige_une_faute_et_remet_les_accents():
    assert suggestion("amortisement", VOCABULAIRE) == "amortissement"
    assert suggestion("degresif", VOCABULAIRE) == "dégressif"
    assert suggestion("Amortisement degresif 2025", VOCABULAIRE) == "amortissement dégressif 2025"


def test_ne_corrige_pas_ce_que_la_recherche_trouve_deja_ni_ce_qui_est_trop_loin():
    assert suggestion("amortis", VOCABULAIRE) is None  # début de mot : la recherche le trouve
    assert suggestion("bila", VOCABULAIRE) is None  # « bilan » est un début de mot pour la recherche
    assert suggestion("banane", VOCABULAIRE) is None  # aucun mot proche
    assert suggestion("blan", VOCABULAIRE) == "bilan"
    assert suggestion("bln", VOCABULAIRE) is None  # trop court pour deviner


def liste(client, texte):
    return client.get(reverse("sujets:liste"), {"examen": "BTS", "q": texte}).content.decode()


def test_page_des_sujets_propose_le_mot_et_le_lien_trouve(client, creer_sujet, session_terminee):
    creer_sujet(session_terminee, statut=Sujet.Statut.PUBLIE, texte_extrait="Calculez l'amortissement dégressif.")
    page = liste(client, "amortisement degresif")
    assert "0 sujet" in page and "Vouliez-vous dire" in page
    assert "q=amortissement+d%C3%A9gressif" in page
    assert "1 sujet" in liste(client, "amortissement dégressif")
    assert "Vouliez-vous dire" not in liste(client, "amortissement")


def test_aucun_mot_d_un_sujet_non_publie(client, creer_sujet, session_terminee, session_en_cours):
    creer_sujet(session_terminee, statut=Sujet.Statut.PUBLIE, texte_extrait="Calculez l'amortissement.")
    # Règle absolue : rien du sujet de la session en cours ne doit transparaître, même pas un mot.
    creer_sujet(session_en_cours, titre="Inventaire extracomptable", texte_extrait="Inventaire extracomptable")
    assert "Vouliez-vous dire" not in liste(client, "extracomptabel")


def test_la_suggestion_respecte_les_autres_filtres(client, creer_sujet, session_terminee):
    creer_sujet(session_terminee, statut=Sujet.Statut.PUBLIE, texte_extrait="Calculez l'amortissement.")
    page = client.get(reverse("sujets:liste"), {"examen": "BTS", "q": "amortisement", "annee": "1990"}).content.decode()
    assert "Vouliez-vous dire" not in page  # elle ne trouverait rien en 1990


def forum(client, texte):
    return client.get(reverse("forum:recherche"), {"q": texte}).content.decode()


def test_forum_propose_le_mot_d_une_reponse_visible(client, question, ben):
    Reponse.objects.create(discussion=question, auteur=ben, texte="Multiplie le taux linéaire par le coefficient.")
    page = forum(client, "coeficient")
    assert "Vouliez-vous dire" in page and "?q=coefficient" in page


def test_forum_ignore_les_contenus_masques(client, question, ben):
    Reponse.objects.create(discussion=question, auteur=ben, texte="Lien vers un site de tricherie", masquee=True)
    assert "Vouliez-vous dire" not in forum(client, "tricheries")
    Discussion.objects.filter(pk=question.pk).update(masquee=True)
    assert "Vouliez-vous dire" not in forum(client, "annuitée")
