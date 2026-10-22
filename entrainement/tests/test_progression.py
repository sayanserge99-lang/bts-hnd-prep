"""Suivi de progression (CDC 3.6) : historique, taux par matière et chapitre, points faibles, compte à rebours."""

from datetime import date, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import ProfilEtude, Utilisateur
from catalogue.models import Chapitre, Session
from entrainement import progression, quiz
from entrainement.models import Choix, Question, ReponseQuestion

pytestmark = pytest.mark.django_db


@pytest.fixture
def etudiant(comptabilite):
    utilisateur = Utilisateur.objects.create_user(email="awa@example.com", password="Revision-2027")
    ProfilEtude.objects.create(utilisateur=utilisateur, examen=comptabilite.examen, specialite=comptabilite)
    return utilisateur


@pytest.fixture
def chapitres(compta_generale):
    return {
        titre: Chapitre.objects.create(matiere=compta_generale, titre=titre, ordre=ordre)
        for ordre, titre in enumerate(["Amortissements", "Régularisations", "Provisions", "Bilan"], start=1)
    }


def question_de(chapitre):
    question = Question.objects.create(chapitre=chapitre, type="choix_unique", enonce="Q", langue="fr", publiee=True)
    Choix.objects.create(question=question, texte="A", est_correct=True)
    Choix.objects.create(question=question, texte="B", est_correct=False)
    return question


def repondre(utilisateur, chapitre, justes, fausses, matiere):
    """Enregistre `justes` bonnes réponses et `fausses` mauvaises dans un quiz terminé."""
    questions = [question_de(chapitre) for _ in range(justes + fausses)]
    tentative = quiz.creer_tentative(utilisateur, questions, "rapide", matiere)
    for numero, question in enumerate(questions):
        ReponseQuestion.objects.create(tentative=tentative, question=question, reponse=[], correcte=numero < justes)
    quiz.terminer(tentative)
    return tentative


def test_taux_par_matiere_et_par_chapitre(etudiant, chapitres, compta_generale):
    repondre(etudiant, chapitres["Amortissements"], justes=3, fausses=1, matiere=compta_generale)
    repondre(etudiant, chapitres["Régularisations"], justes=1, fausses=3, matiere=compta_generale)

    (matiere,) = progression.taux_par_matiere(etudiant)
    assert (matiere.justes, matiere.total, matiere.pourcentage) == (4, 8, 50)
    par_chapitre = {t.objet.titre: t.pourcentage for t in progression.taux_par_chapitre(etudiant)}
    assert par_chapitre == {"Amortissements": 75, "Régularisations": 25}


def test_les_reponses_des_autres_ne_comptent_pas(etudiant, chapitres, compta_generale):
    autre = Utilisateur.objects.create_user(email="autre@example.com", password="Revision-2027")
    repondre(autre, chapitres["Amortissements"], justes=0, fausses=5, matiere=compta_generale)
    assert progression.taux_par_chapitre(etudiant) == []


def test_points_faibles_les_trois_moins_maitrises_avec_assez_de_reponses(etudiant, chapitres, compta_generale):
    repondre(etudiant, chapitres["Amortissements"], justes=1, fausses=3, matiere=compta_generale)  # 25 %
    repondre(etudiant, chapitres["Régularisations"], justes=2, fausses=2, matiere=compta_generale)  # 50 %
    repondre(etudiant, chapitres["Provisions"], justes=3, fausses=1, matiere=compta_generale)  # 75 %
    repondre(etudiant, chapitres["Bilan"], justes=0, fausses=2, matiere=compta_generale)  # 0 %, mais 2 réponses seulement

    faibles = [t.objet.titre for t in progression.points_faibles(etudiant)]

    assert faibles == ["Amortissements", "Régularisations", "Provisions"]


def test_un_chapitre_reussi_a_100_pourcent_n_est_pas_un_point_faible(etudiant, chapitres, compta_generale):
    repondre(etudiant, chapitres["Amortissements"], justes=4, fausses=0, matiere=compta_generale)
    assert progression.points_faibles(etudiant) == []


def test_compte_a_rebours_session_prevue_sinon_prochaine_session(etudiant, bts):
    aujourd_hui = timezone.localdate()
    prochaine = Session.objects.create(
        examen=bts, annee=aujourd_hui.year + 1, date_debut=aujourd_hui + timedelta(days=40),
        date_fin_officielle=aujourd_hui + timedelta(days=80),
    )
    assert progression.prochaine_session(etudiant) == prochaine
    assert progression.jours_restants(prochaine) == 40

    prevue = Session.objects.create(
        examen=bts, annee=aujourd_hui.year + 2, date_debut=aujourd_hui + timedelta(days=400),
        date_fin_officielle=aujourd_hui + timedelta(days=440),
    )
    etudiant.profil.session_prevue = prevue
    etudiant.profil.save()
    assert progression.prochaine_session(etudiant) == prevue


def test_pas_de_compte_a_rebours_sans_session_a_venir(etudiant, session_terminee):
    assert progression.prochaine_session(etudiant) is None


def test_page_de_progression(client, etudiant, chapitres, compta_generale, bts):
    Session.objects.create(examen=bts, annee=2099, date_debut=date(2099, 4, 20), date_fin_officielle=date(2099, 6, 30))
    repondre(etudiant, chapitres["Amortissements"], justes=1, fausses=3, matiere=compta_generale)
    client.force_login(etudiant)

    contenu = client.get(reverse("entrainement:progression")).content.decode()

    assert "jours avant la session" in contenu
    assert "Mes points faibles" in contenu
    assert "Amortissements" in contenu
    assert "25 %" in contenu
    assert "Quiz conseillé sur ce chapitre" in contenu
    assert "5/20" in contenu  # historique : 1 juste sur 4


def test_le_quiz_conseille_vise_le_chapitre_faible(client, etudiant, chapitres, compta_generale):
    repondre(etudiant, chapitres["Amortissements"], justes=1, fausses=3, matiere=compta_generale)
    question_de(chapitres["Régularisations"])
    client.force_login(etudiant)

    client.post(
        reverse("entrainement:lancer"),
        {"matiere": compta_generale.pk, "chapitre": chapitres["Amortissements"].pk},
    )

    derniere = etudiant.tentatives.latest("debut")
    assert set(Question.objects.filter(pk__in=derniere.ordre).values_list("chapitre", flat=True)) == {
        chapitres["Amortissements"].pk
    }


def test_paiement_ouvert_statistiques_basiques_en_gratuit(client, settings, etudiant, chapitres, compta_generale):
    settings.PAIEMENT_ACTIF = True
    repondre(etudiant, chapitres["Amortissements"], justes=1, fausses=3, matiere=compta_generale)
    client.force_login(etudiant)

    contenu = client.get(reverse("entrainement:progression")).content.decode()

    assert "Réussite par matière" in contenu
    assert "Mes points faibles" not in contenu
    assert "Réussite par chapitre" not in contenu
    assert "inclus dans le Pass session" in contenu


def test_la_progression_exige_une_connexion(client):
    assert client.get(reverse("entrainement:progression")).status_code == 302


def test_mon_espace_montre_les_derniers_resultats(client, etudiant, chapitres, compta_generale):
    repondre(etudiant, chapitres["Amortissements"], justes=2, fausses=2, matiere=compta_generale)
    client.force_login(etudiant)

    contenu = client.get(reverse("accounts:profil")).content.decode()
    assert "Mes derniers résultats" in contenu
    assert "10/20" in contenu
