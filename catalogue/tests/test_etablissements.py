"""Établissements (IAI, HINTEL…), ordre des spécialités, toutes les matières dans Entraînement."""

import pytest
from django.urls import reverse

from accounts.models import ProfilEtude, Utilisateur
from catalogue.models import Chapitre, Matiere, SpecialiteMatiere, Specialite
from catalogue.statistiques import tableau_de_bord
from entrainement import quiz
from entrainement.models import Choix, Question, ReponseQuestion
from partenaires.models import Etablissement
from sujets.models import Sujet

pytestmark = pytest.mark.django_db

MOT_DE_PASSE = "Revision-BTS-2027"


@pytest.fixture
def iai():
    return Etablissement.objects.create(nom="IAI-Cameroun", ville="Yaoundé", region="centre")


@pytest.fixture
def hintel():
    # Ville inconnue : un établissement peut être ajouté sans adresse.
    return Etablissement.objects.create(nom="HINTEL")


def etudiant(email, specialite, etablissement=None):
    utilisateur = Utilisateur.objects.create_user(email=email, password=MOT_DE_PASSE)
    ProfilEtude.objects.create(utilisateur=utilisateur, examen=specialite.examen, specialite=specialite, etablissement=etablissement)
    return utilisateur


# --- Ordre des spécialités ---------------------------------------------------------------------

def test_la_specialite_prioritaire_s_affiche_en_premier(client, bts, comptabilite, marketing):
    informatique = Specialite.objects.create(examen=bts, code="IG", nom="Informatique de gestion / Génie logiciel",
                                             filiere="commerciale", ordre=1)

    contenu = client.get(reverse("accueil")).content.decode()
    assert contenu.index(informatique.nom) < contenu.index(comptabilite.nom) < contenu.index(marketing.nom)
    options = client.get(reverse("options_specialites"), {"examen": "BTS"}).content.decode()
    assert options.index(informatique.nom) < options.index(comptabilite.nom)


# --- Établissement dans le profil ---------------------------------------------------------------

def test_inscription_avec_etablissement(client, comptabilite, iai):
    client.post(reverse("accounts:inscription"), {
        "first_name": "Awa", "last_name": "Ngono", "email": "awa@example.com", "langue": "fr",
        "specialite": comptabilite.pk, "etablissement": iai.pk,
        "password1": MOT_DE_PASSE, "password2": MOT_DE_PASSE, "accepte_conditions": "on",
    })
    assert Utilisateur.objects.get().profil.etablissement == iai


def test_l_etablissement_est_facultatif(client, comptabilite, iai):
    page = client.get(reverse("accounts:inscription")).content.decode()
    assert "Choisir dans la liste" in page and "(facultatif)" in page and "IAI-Cameroun" in page

    client.post(reverse("accounts:inscription"), {
        "first_name": "Awa", "last_name": "Ngono", "email": "awa@example.com", "langue": "fr",
        "specialite": comptabilite.pk, "password1": MOT_DE_PASSE, "password2": MOT_DE_PASSE, "accepte_conditions": "on",
    })
    assert Utilisateur.objects.get().profil.etablissement is None


def test_changer_d_etablissement_dans_son_profil(client, comptabilite, iai, hintel):
    utilisateur = etudiant("awa@example.com", comptabilite, iai)
    client.force_login(utilisateur)
    client.post(reverse("accounts:modifier_profil"), {
        "first_name": "Awa", "last_name": "Ngono", "langue": "fr", "specialite": comptabilite.pk, "etablissement": hintel.pk,
    })
    utilisateur.profil.refresh_from_db()
    assert utilisateur.profil.etablissement == hintel


# --- Statistiques par établissement -----------------------------------------------------------

def test_statistiques_par_etablissement_par_ordre_alphabetique(comptabilite, compta_generale, iai, hintel):
    awa = etudiant("awa@example.com", comptabilite, iai)
    etudiant("ben@example.com", comptabilite, iai)
    etudiant("chloe@example.com", comptabilite, hintel)
    etudiant("dan@example.com", comptabilite)
    chapitre = Chapitre.objects.create(matiere=compta_generale, titre="Amortissements", ordre=1)
    questions = []
    for _ in range(4):
        question = Question.objects.create(chapitre=chapitre, type="choix_unique", enonce="Q", langue="fr", publiee=True)
        Choix.objects.create(question=question, texte="A", est_correct=True)
        questions.append(question)
    tentative = quiz.creer_tentative(awa, questions, "rapide", compta_generale)
    for numero, question in enumerate(questions):
        ReponseQuestion.objects.create(tentative=tentative, question=question, reponse=[], correcte=numero < 3)
    quiz.terminer(tentative)

    lignes = tableau_de_bord()["par_etablissement"]

    assert [str(ligne["etablissement"] or "") for ligne in lignes] == ["HINTEL", "IAI-Cameroun (Yaoundé)", ""]
    ligne_iai = lignes[1]
    assert (ligne_iai["inscrits"], ligne_iai["actifs"], ligne_iai["reussite"]) == (2, 1, 75)
    assert lignes[0]["reussite"] is None  # aucune réponse


# --- Catalogue : filtre « fourni par » ------------------------------------------------------------

def test_filtre_du_catalogue_par_etablissement_d_origine(client, creer_sujet, session_terminee, iai):
    fourni = creer_sujet(session_terminee, titre="Sujet de l'IAI", statut=Sujet.Statut.PUBLIE, fourni_par=iai)
    autre = creer_sujet(session_terminee, titre="Autre sujet", statut=Sujet.Statut.PUBLIE, type_epreuve="pratique")

    liste = client.get(reverse("sujets:liste"), {"examen": "BTS"}).content.decode()
    assert 'name="fourni_par"' in liste
    resultats = client.get(reverse("sujets:liste"), {"examen": "BTS", "fourni_par": iai.pk}, headers={"HX-Request": "true"}).content.decode()
    assert "Sujet de l&#x27;IAI" in resultats or "Sujet de l'IAI" in resultats
    assert autre.titre not in resultats
    assert "IAI-Cameroun" in client.get(reverse("sujets:detail", args=[fourni.pk])).content.decode()


def test_pas_de_filtre_sans_etablissement_fournisseur(client, creer_sujet, session_terminee):
    creer_sujet(session_terminee, statut=Sujet.Statut.PUBLIE)
    assert 'name="fourni_par"' not in client.get(reverse("sujets:liste"), {"examen": "BTS"}).content.decode()


# --- Entraînement : toutes les matières --------------------------------------------------------------

def test_toutes_les_matieres_de_la_specialite_apparaissent(client, bts, comptabilite, compta_generale):
    sans_question = Matiere.objects.create(examen=bts, nom="Droit des affaires")
    SpecialiteMatiere.objects.create(specialite=comptabilite, matiere=sans_question, coefficient=2)
    chapitre = Chapitre.objects.create(matiere=compta_generale, titre="Amortissements", ordre=1)
    question = Question.objects.create(chapitre=chapitre, type="choix_unique", enonce="Q", langue="fr", publiee=True)
    Choix.objects.create(question=question, texte="A", est_correct=True)
    client.force_login(etudiant("awa@example.com", comptabilite))

    contenu = client.get(reverse("entrainement:accueil")).content.decode()

    assert "Droit des affaires" in contenu
    assert "Questions bientôt disponibles" in contenu
    # Celle qui a des questions passe d'abord.
    assert contenu.index("Comptabilité générale") < contenu.index("Droit des affaires")
