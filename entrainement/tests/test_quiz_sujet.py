"""Quiz sur une épreuve et import de questions en lot (CSV)."""

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from accounts.models import AffectationModerateur, ProfilEtude, Utilisateur
from catalogue.models import Chapitre, Matiere
from entrainement import quiz
from entrainement.importation import COLONNES, Importateur, modele_csv
from entrainement.models import Question, Quiz
from entrainement.tests.test_quiz import creer_question
from sujets.importation import ImportImpossible
from sujets.models import Sujet

pytestmark = pytest.mark.django_db


@pytest.fixture
def chapitre(compta_generale):
    return Chapitre.objects.create(matiere=compta_generale, titre="Amortissements", ordre=1)


@pytest.fixture
def etudiant(comptabilite):
    utilisateur = Utilisateur.objects.create_user(email="awa@example.com", password="Revision-2027")
    ProfilEtude.objects.create(utilisateur=utilisateur, examen=comptabilite.examen, specialite=comptabilite)
    return utilisateur


@pytest.fixture
def sujet_publie(creer_sujet, session_terminee):
    return creer_sujet(session_terminee, statut=Sujet.Statut.PUBLIE)


@pytest.fixture
def sujet_en_cours(creer_sujet, session_en_cours):
    return creer_sujet(session_en_cours)  # brouillon : sa session n'est pas terminée


# --- Quiz sur cette épreuve --------------------------------------------------------------------------

def test_quiz_sur_cette_epreuve(client, etudiant, chapitre, sujet_publie):
    for numero in range(3):
        creer_question(chapitre, sujet=sujet_publie, enonce=f"Question {numero} ?")
    creer_question(chapitre, enonce="Question sans sujet ?")
    client.force_login(etudiant)

    fiche = client.get(reverse("sujets:detail", args=[sujet_publie.pk])).content.decode()
    assert "Quiz sur cette épreuve" in fiche and "3 questions" in fiche

    reponse = client.post(reverse("entrainement:lancer_sujet", args=[sujet_publie.pk]))
    tentative = etudiant.tentatives.get()
    assert reponse.url == reverse("entrainement:tentative", args=[tentative.pk])
    assert tentative.quiz.mode == Quiz.Mode.SUJET and tentative.quiz.sujet == sujet_publie
    # Toutes les questions du sujet, et seulement elles.
    assert set(tentative.ordre) == set(sujet_publie.questions.values_list("pk", flat=True))


def test_pas_de_bouton_sans_question(client, sujet_publie):
    assert "Quiz sur cette épreuve" not in client.get(reverse("sujets:detail", args=[sujet_publie.pk])).content.decode()


def test_le_visiteur_est_invite_a_se_connecter(client, chapitre, sujet_publie):
    creer_question(chapitre, sujet=sujet_publie)
    contenu = client.get(reverse("sujets:detail", args=[sujet_publie.pk])).content.decode()
    assert "Se connecter pour faire le quiz" in contenu


def test_les_questions_d_un_sujet_non_publie_ne_sortent_nulle_part(client, etudiant, chapitre, sujet_en_cours):
    """Règle absolue (CDC 4.2) : une question tirée d'un sujet de la session en cours ne fuit pas par les quiz."""
    secrete = creer_question(chapitre, sujet=sujet_en_cours, enonce="Question de la session en cours ?")
    client.force_login(etudiant)

    assert client.post(reverse("entrainement:lancer_sujet", args=[sujet_en_cours.pk])).status_code == 404
    assert quiz.lancer_quiz_rapide(etudiant, chapitre.matiere) is None
    assert secrete not in Question.objects.visibles()
    # La matière reste « bientôt disponible » : la question n'est pas comptée.
    assert "Questions bientôt disponibles" in client.get(reverse("entrainement:accueil")).content.decode()

    # Une fois la session terminée et le sujet publié, ses questions entrent dans les quiz.
    session = sujet_en_cours.session
    session.date_fin_officielle = session.date_debut
    session.save()
    Sujet.objects.filter(pk=sujet_en_cours.pk).update(statut=Sujet.Statut.PUBLIE)
    assert secrete in Question.objects.visibles()


def test_un_sujet_masque_masque_ses_questions(chapitre, sujet_publie):
    """Demande de retrait : le sujet est masqué, ses questions quittent les quiz avec lui."""
    question = creer_question(chapitre, sujet=sujet_publie)
    Sujet.objects.filter(pk=sujet_publie.pk).update(statut=Sujet.Statut.MASQUE)
    assert question not in Question.objects.visibles()


def test_le_sujet_doit_etre_de_la_matiere_du_chapitre(bts, chapitre, creer_sujet, session_terminee):
    autre = Matiere.objects.create(examen=bts, nom="Marketing")
    question = Question(chapitre=chapitre, sujet=creer_sujet(session_terminee, matiere=autre), enonce="?", type="choix_unique", langue="fr")
    with pytest.raises(ValidationError):
        question.full_clean()


# --- Import CSV ----------------------------------------------------------------------------------------

def tableau(*lignes):
    """Un CSV au format Excel français (point-virgule, BOM)."""
    rangees = [";".join(COLONNES)]
    for ligne in lignes:
        valeurs = {"examen": "BTS", "matiere": "Comptabilité générale", "chapitre": "Amortissements", **ligne}
        rangees.append(";".join(valeurs.get(colonne, "") for colonne in COLONNES))
    return ("﻿" + "\n".join(rangees)).encode("utf-8")


def test_import_de_chaque_type(chapitre, sujet_publie):
    contenu = tableau(
        {"type": "choix_unique", "enonce": "Annuité ?", "choix_a": "200 000", "choix_b": "240 000", "bonnes": "B", "annee_sujet": "2025"},
        {"type": "choix_multiple", "enonce": "Immobilisations ?", "choix_a": "Machine", "choix_b": "Stock", "choix_c": "Bâtiment", "bonnes": "A,C"},
        {"type": "vrai_faux", "enonce": "Un terrain s'amortit.", "bonnes": "faux", "explication": "Non."},
        {"type": "reponse_courte", "enonce": "Taux linéaire sur 5 ans ?", "reponse_attendue": "20 %|20%|0,2", "difficulte": "3"},
    )
    assert [ligne.statut for ligne in Importateur().importer(contenu)] == ["pret"] * 4
    assert not Question.objects.exists()  # simulation : rien n'est enregistré

    rapport = Importateur().importer(contenu, simulation=False)
    assert [ligne.statut for ligne in rapport] == ["importe"] * 4
    unique, multiple, vrai_faux, courte = Question.objects.order_by("pk")
    assert not any(question.publiee for question in (unique, multiple, vrai_faux, courte))  # brouillons
    assert unique.sujet == sujet_publie and list(unique.choix.filter(est_correct=True).values_list("texte", flat=True)) == ["240 000"]
    assert sorted(multiple.choix.filter(est_correct=True).values_list("texte", flat=True)) == ["Bâtiment", "Machine"]
    assert list(vrai_faux.choix.values_list("texte", "est_correct")) == [("Vrai", False), ("Faux", True)]
    assert courte.reponse_attendue == "20 %|20%|0,2" and courte.difficulte == 3
    assert all(not question.problemes() for question in (unique, multiple, vrai_faux, courte))


def test_lignes_refusees_avec_leur_motif(chapitre):
    rapport = Importateur().importer(tableau(
        {"type": "choix_unique", "enonce": "Sans bonne réponse ?", "choix_a": "A", "choix_b": "B"},
        {"type": "choix_unique", "enonce": "Lettre inconnue ?", "choix_a": "A", "choix_b": "B", "bonnes": "D"},
        {"type": "choix_unique", "enonce": "Deux bonnes ?", "choix_a": "A", "choix_b": "B", "bonnes": "A,B"},
        {"type": "qcm_bizarre", "enonce": "Type ?"},
        {"type": "vrai_faux", "enonce": "Peut-être ?", "bonnes": "peut-être"},
        {"type": "reponse_courte", "enonce": "Sans réponse ?"},
        {"type": "choix_unique", "enonce": "Chapitre ?", "chapitre": "Inconnu", "choix_a": "A", "choix_b": "B", "bonnes": "A"},
        {"type": "choix_unique", "enonce": "Sujet ?", "choix_a": "A", "choix_b": "B", "bonnes": "A", "annee_sujet": "2019"},
    ), simulation=False)
    assert [ligne.statut for ligne in rapport] == ["erreur"] * 8
    assert all(ligne.message for ligne in rapport)
    assert "chapitre inconnu" in rapport[6].message and "importez d'abord le sujet" in rapport[7].message
    assert not Question.objects.exists()


def test_les_doublons_sont_ignores(chapitre):
    creer_question(chapitre, enonce="Qu'est-ce qu'un amortissement ?")
    rapport = Importateur().importer(tableau(
        {"type": "vrai_faux", "enonce": "qu'est-ce  qu'un amortissement ?", "bonnes": "vrai"},
        {"type": "vrai_faux", "enonce": "Nouvelle ?", "bonnes": "vrai"},
        {"type": "vrai_faux", "enonce": "Nouvelle ?", "bonnes": "faux"},
    ), simulation=False)
    assert [ligne.statut for ligne in rapport] == ["doublon", "importe", "doublon"]


def test_tableau_sans_les_colonnes_obligatoires():
    with pytest.raises(ImportImpossible):
        Importateur().importer("examen;enonce\nBTS;Question ?".encode())


def test_le_modele_se_reimporte_tel_quel(chapitre, sujet_publie):
    sujet_publie.session.annee = 2024
    sujet_publie.session.save()
    rapport = Importateur().importer(modele_csv().encode("utf-8"))
    assert [ligne.statut for ligne in rapport] == ["pret", "pret"], [ligne.message for ligne in rapport]


def test_un_moderateur_n_importe_que_dans_ses_matieres(chapitre, bts):
    marketing = Matiere.objects.create(examen=bts, nom="Marketing")
    Chapitre.objects.create(matiere=marketing, titre="Prix")
    moderateur = Utilisateur.objects.create_user(email="mod@example.com", password="Moderation-2027")
    moderateur.groups.add(Group.objects.get(name="Modérateur"))
    AffectationModerateur.objects.create(moderateur=moderateur, matiere=chapitre.matiere)

    rapport = Importateur(moderateur).importer(tableau(
        {"type": "vrai_faux", "enonce": "Compta ?", "bonnes": "vrai"},
        {"type": "vrai_faux", "enonce": "Marketing ?", "bonnes": "vrai", "matiere": "Marketing", "chapitre": "Prix"},
    ))
    assert [ligne.statut for ligne in rapport] == ["pret", "erreur"]


def test_page_d_import_dans_l_admin(client, chapitre):
    admin = Utilisateur.objects.create_superuser(email="admin@example.com", password="Administration-2027")
    client.force_login(admin)
    assert reverse("admin:entrainement_question_importer") in client.get(reverse("admin:entrainement_question_changelist")).content.decode()
    assert client.get(reverse("admin:entrainement_question_modele_import")).content.decode("utf-8-sig").startswith("examen;matiere")

    reponse = client.post(reverse("admin:entrainement_question_importer"), {
        "tableau": SimpleUploadedFile("questions.csv", tableau({"type": "vrai_faux", "enonce": "Vrai ?", "bonnes": "vrai"})),
    })
    assert "Résultat de l'import" in reponse.content.decode()
    assert Question.objects.filter(publiee=False).count() == 1
