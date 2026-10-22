"""Mode hors ligne (CDC 4) : service worker, manifeste, sujets gardés, quiz téléchargés et synchronisés."""

import json
import re

import pytest
from django.contrib.staticfiles import finders
from django.urls import reverse

from accounts.models import ProfilEtude, Utilisateur
from catalogue.models import Chapitre
from entrainement.models import Choix, Question, ReponseQuestion, Tentative
from sujets.models import Sujet

pytestmark = pytest.mark.django_db


@pytest.fixture
def etudiant(comptabilite):
    utilisateur = Utilisateur.objects.create_user(email="awa@example.com", password="Revision-2027")
    ProfilEtude.objects.create(utilisateur=utilisateur, examen=comptabilite.examen, specialite=comptabilite)
    return utilisateur


@pytest.fixture
def questions(compta_generale):
    chapitre = Chapitre.objects.create(matiere=compta_generale, titre="Amortissements", ordre=1)
    unique = Question.objects.create(chapitre=chapitre, type="choix_unique", enonce="Taux $t$ ?", langue="fr",
                                     publiee=True, explication="Parce que **20 %**.")
    Choix.objects.create(question=unique, texte="20 %", est_correct=True)
    Choix.objects.create(question=unique, texte="40 %", est_correct=False)
    courte = Question.objects.create(chapitre=chapitre, type="reponse_courte", enonce="Compte ?", langue="fr",
                                     publiee=True, reponse_attendue="681|six cent quatre-vingt-un")
    return unique, courte


def telecharger(client, matiere):
    return client.post(reverse("entrainement:quiz_hors_ligne"), {"matiere": matiere.pk})


def synchroniser(client, tentative_id, reponses):
    return client.post(
        reverse("entrainement:synchroniser_hors_ligne", args=[tentative_id]),
        json.dumps({"reponses": reponses}), content_type="application/json",
    )


# --- Service worker, manifeste, page hors ligne ------------------------------------------

def test_le_service_worker_est_servi_a_la_racine(client):
    reponse = client.get("/sw.js")

    assert reponse["Content-Type"].startswith("application/javascript")
    assert reponse["Service-Worker-Allowed"] == "/"
    contenu = reponse.content.decode()
    for adresse in ("/hors-ligne/", "/static/css/app.css", "/static/js/hors-ligne.js"):
        assert f'"{adresse}"' in contenu
    # Ni les pages personnelles ni l'administration ne sont gardées.
    assert 'startsWith("/admin/")' in contenu and "/compte/" not in contenu.split("function pagePublique")[1].split("}")[0]


def test_le_manifeste_rend_le_site_installable(client):
    manifeste = json.loads(client.get("/manifest.webmanifest").content)

    assert manifeste["display"] == "standalone"
    assert manifeste["start_url"].startswith("/")
    tailles = {icone["sizes"] for icone in manifeste["icons"]}
    assert {"192x192", "512x512"} <= tailles
    for icone in manifeste["icons"]:
        assert finders.find(icone["src"].removeprefix("/static/")), icone["src"]


def test_page_hors_ligne_et_liens(client, etudiant):
    assert client.get(reverse("hors_ligne")).status_code == 200
    accueil = client.get(reverse("accueil")).content.decode()
    assert 'rel="manifest"' in accueil and "js/hors-ligne.js" in accueil


def test_la_fiche_propose_de_garder_le_sujet_avec_son_pdf(client, creer_sujet, session_terminee):
    sujet = creer_sujet(session_terminee, statut=Sujet.Statut.PUBLIE)
    contenu = client.get(reverse("sujets:detail", args=[sujet.pk])).content.decode()

    urls = json.loads(re.search(r"data-urls='([^']+)'", contenu).group(1))
    assert urls == [f"/sujets/{sujet.pk}/", f"/sujets/{sujet.pk}/?onglet=corrige", f"/sujets/{sujet.pk}/pdf/"]


# --- Téléchargement d'un quiz -------------------------------------------------------------

def test_telecharger_un_quiz_exige_une_connexion(client, questions, compta_generale):
    assert telecharger(client, compta_generale).status_code == 302


def test_le_paquet_contient_les_questions_et_leur_correction(client, etudiant, questions, compta_generale):
    client.force_login(etudiant)
    paquet = telecharger(client, compta_generale).json()

    tentative = Tentative.objects.get()
    assert paquet["tentative"] == tentative.pk
    assert len(paquet["questions"]) == 2
    unique = next(q for q in paquet["questions"] if q["type"] == "choix_unique")
    assert [c["correct"] for c in unique["choix"]] == [True, False]
    assert "<math" in unique["enonce"]  # formules rendues comme en ligne
    assert "<strong>20" in unique["explication"]
    courte = next(q for q in paquet["questions"] if q["type"] == "reponse_courte")
    assert courte["acceptees"] == ["681", "six cent quatre-vingt-un"]


def test_le_quiz_telecharge_compte_dans_la_limite_quotidienne(client, settings, etudiant, questions, compta_generale):
    settings.PAIEMENT_ACTIF = True
    settings.QUIZ_GRATUITS_PAR_JOUR = 1
    client.force_login(etudiant)

    assert telecharger(client, compta_generale).status_code == 200
    assert telecharger(client, compta_generale).status_code == 403


# --- Synchronisation ----------------------------------------------------------------------

def test_le_serveur_recorrige_et_termine_le_quiz(client, etudiant, questions, compta_generale):
    unique, courte = questions
    client.force_login(etudiant)
    tentative = telecharger(client, compta_generale).json()["tentative"]
    fausse = unique.choix.get(est_correct=False).pk

    resultat = synchroniser(client, tentative, {str(unique.pk): [fausse], str(courte.pk): " 681 "}).json()

    assert resultat["repondues"] == 2
    assert resultat["note"] == "10.00"
    assert ReponseQuestion.objects.get(question=unique).correcte is False
    assert ReponseQuestion.objects.get(question=courte).correcte is True
    assert Tentative.objects.get(pk=tentative).fin is not None


def test_synchroniser_deux_fois_ne_cree_pas_de_doublon(client, etudiant, questions, compta_generale):
    unique, _ = questions
    client.force_login(etudiant)
    tentative = telecharger(client, compta_generale).json()["tentative"]
    bonne = unique.choix.get(est_correct=True).pk

    synchroniser(client, tentative, {str(unique.pk): [bonne]})
    # Le téléphone renvoie tout, avec une autre réponse : la première compte.
    synchroniser(client, tentative, {str(unique.pk): [unique.choix.get(est_correct=False).pk]})

    assert ReponseQuestion.objects.filter(question=unique).count() == 1
    assert ReponseQuestion.objects.get(question=unique).correcte is True


def test_les_reponses_invalides_sont_ignorees(client, etudiant, questions, compta_generale, bts):
    unique, courte = questions
    client.force_login(etudiant)
    tentative = telecharger(client, compta_generale).json()["tentative"]
    autre = Question.objects.create(chapitre=unique.chapitre, type="choix_unique", enonce="Autre", langue="fr")
    choix_etranger = Choix.objects.create(question=autre, texte="X", est_correct=True).pk

    synchroniser(client, tentative, {
        str(unique.pk): [choix_etranger],  # choix d'une autre question
        str(courte.pk): ["681"],  # liste au lieu d'un texte
        str(autre.pk): [choix_etranger],  # question hors du quiz
    })

    assert not ReponseQuestion.objects.exists()


def test_format_incorrect_et_tentative_d_un_autre(client, etudiant, questions, compta_generale):
    client.force_login(etudiant)
    tentative = telecharger(client, compta_generale).json()["tentative"]
    url = reverse("entrainement:synchroniser_hors_ligne", args=[tentative])

    assert client.post(url, "pas du json", content_type="application/json").status_code == 400
    intrus = Utilisateur.objects.create_user(email="intrus@example.com", password="Revision-2027")
    client.force_login(intrus)
    assert synchroniser(client, tentative, {}).status_code == 404


def test_les_reponses_hors_ligne_comptent_dans_la_progression(client, etudiant, questions, compta_generale):
    from entrainement import progression

    unique, courte = questions
    client.force_login(etudiant)
    tentative = telecharger(client, compta_generale).json()["tentative"]
    synchroniser(client, tentative, {str(unique.pk): [unique.choix.get(est_correct=True).pk], str(courte.pk): "681"})

    (taux,) = progression.taux_par_matiere(etudiant)
    assert taux.pourcentage == 100
