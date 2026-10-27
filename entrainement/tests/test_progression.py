"""Suivi de progression (CDC 3.6) : historique, taux par matière et chapitre, points faibles, compte à rebours."""

from datetime import date, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import ProfilEtude, Utilisateur
from catalogue.models import Chapitre, Session
from entrainement import progression, quiz
from entrainement.models import Choix, Question, ReponseQuestion, Tentative

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

    assert "Avant la session 2099" in contenu and "jours" in contenu
    assert "Vos points faibles" in contenu
    assert "Amortissements" in contenu
    assert "25 %" in contenu
    assert "S'entraîner" in contenu  # quiz conseillé sur le chapitre faible
    assert "1 / 4" in contenu  # dernières activités : 1 juste sur 4


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

    assert "Maîtrise par matière" in contenu
    assert "S'entraîner" not in contenu  # pas de liste de points faibles en gratuit
    assert "Réussite par chapitre" not in contenu
    assert "inclus dans le Pass session" in contenu


def test_la_progression_exige_une_connexion(client):
    assert client.get(reverse("entrainement:progression")).status_code == 302


def test_mon_espace_mene_au_tableau_de_bord_et_ses_derniers_resultats(client, etudiant, chapitres, compta_generale):
    """CDC 3.1 : les derniers résultats sont sur le tableau de bord, que le profil (maquette) propose en raccourci."""
    repondre(etudiant, chapitres["Amortissements"], justes=2, fausses=2, matiere=compta_generale)
    client.force_login(etudiant)

    assert reverse("entrainement:progression") in client.get(reverse("accounts:profil")).content.decode()
    tableau = client.get(reverse("entrainement:progression")).content.decode()
    assert "Dernières activités" in tableau and "2 / 4" in tableau


# --- Tableau de bord (maquette) : taux global, série, 30 derniers jours ---------------------------------------

def _terminee_il_y_a(utilisateur, chapitre, matiere, jours):
    tentative = repondre(utilisateur, chapitre, justes=1, fausses=0, matiere=matiere)
    moment = timezone.now() - timedelta(days=jours)
    Tentative.objects.filter(pk=tentative.pk).update(debut=moment, fin=moment)
    ReponseQuestion.objects.filter(tentative=tentative).update(repondu_le=moment)
    return tentative


def test_bilan_global(etudiant, chapitres, compta_generale):
    repondre(etudiant, chapitres["Amortissements"], justes=3, fausses=1, matiere=compta_generale)
    repondre(etudiant, chapitres["Régularisations"], justes=0, fausses=4, matiere=compta_generale)
    bilan = progression.bilan(etudiant)
    assert (bilan.total, bilan.justes, bilan.pourcentage) == (8, 3, 38)


def test_serie_de_jours_consecutifs(etudiant, chapitres, compta_generale):
    for jours in (0, 1, 2, 4):  # le trou du 3e jour arrête la série
        _terminee_il_y_a(etudiant, chapitres["Amortissements"], compta_generale, jours)
    assert progression.serie_en_cours(etudiant) == 3


def test_la_serie_court_encore_si_rien_aujourd_hui(etudiant, chapitres, compta_generale):
    for jours in (1, 2):
        _terminee_il_y_a(etudiant, chapitres["Amortissements"], compta_generale, jours)
    assert progression.serie_en_cours(etudiant) == 2
    Tentative.objects.update(fin=timezone.now() - timedelta(days=3))
    assert progression.serie_en_cours(etudiant) == 0


def test_maitrise_sur_les_30_derniers_jours(etudiant, chapitres, compta_generale):
    _terminee_il_y_a(etudiant, chapitres["Amortissements"], compta_generale, 45)
    assert progression.taux_par_matiere(etudiant) and not progression.taux_par_matiere(etudiant, 30)


def test_jour_relatif():
    maintenant = timezone.now()
    assert progression.jour_relatif(maintenant) == "Aujourd'hui"
    assert progression.jour_relatif(maintenant - timedelta(days=1)) == "Hier"
    assert progression.jour_relatif(maintenant - timedelta(days=3)) == "Il y a 3 jours"
