"""Examens blancs (CDC 3.5) : durée réelle, sauvegarde continue, reprise, soumission automatique, auto-évaluation."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import ProfilEtude, Utilisateur
from catalogue.models import Chapitre
from entrainement import examen_blanc
from entrainement.models import Choix, CritereBareme, ExamenBlanc, Question, ReponseQuestion, Tentative
from sujets.models import Corrige, Sujet

pytestmark = pytest.mark.django_db


@pytest.fixture
def sujet(creer_sujet, session_terminee, comptabilite):
    sujet = creer_sujet(session_terminee, titre="Comptabilité générale", statut=Sujet.Statut.PUBLIE, duree=240)
    sujet.specialites.add(comptabilite)
    return sujet


@pytest.fixture
def questions(compta_generale):
    chapitre = Chapitre.objects.create(matiere=compta_generale, titre="Amortissements", ordre=1)
    creees = []
    for numero in range(2):
        question = Question.objects.create(
            chapitre=chapitre, type="choix_unique", enonce=f"Question {numero}", langue="fr", publiee=True,
            explication=f"Explication {numero}",
        )
        Choix.objects.create(question=question, texte="Bonne", est_correct=True)
        Choix.objects.create(question=question, texte="Mauvaise", est_correct=False)
        creees.append(question)
    return creees


@pytest.fixture
def examen(sujet, questions):
    examen = ExamenBlanc.objects.create(titre="Examen blanc 2025", sujet=sujet, duree=240, points_qcm=6, publie=True)
    examen.questions.set(questions)
    CritereBareme.objects.create(examen_blanc=examen, libelle="Exercice 1", points=7, ordre=1)
    CritereBareme.objects.create(examen_blanc=examen, libelle="Exercice 2", points=7, ordre=2)
    return examen


@pytest.fixture
def etudiant(comptabilite):
    utilisateur = Utilisateur.objects.create_user(email="awa@example.com", password="Revision-2027")
    ProfilEtude.objects.create(utilisateur=utilisateur, examen=comptabilite.examen, specialite=comptabilite)
    return utilisateur


def bonne(question):
    return question.choix.get(est_correct=True).pk


def mauvaise(question):
    return question.choix.get(est_correct=False).pk


def demarrer(client, examen):
    client.post(reverse("entrainement:demarrer_examen", args=[examen.pk]))
    return Tentative.objects.get(examen_blanc=examen)


def faire_expirer(tentative):
    """Simule la fin du temps et de la marge de transmission."""
    Tentative.objects.filter(pk=tentative.pk).update(fin_prevue=timezone.now() - timedelta(minutes=10))
    tentative.refresh_from_db()


# --- Durée et reprise -------------------------------------------------------------------

def test_le_depart_fixe_l_heure_de_fin_sur_le_serveur(client, etudiant, examen):
    client.force_login(etudiant)
    tentative = demarrer(client, examen)

    duree = tentative.fin_prevue - tentative.debut
    assert duree == timedelta(minutes=240)
    page = client.get(reverse("entrainement:epreuve", args=[tentative.pk])).content.decode()
    assert 'data-secondes="14' in page  # environ 14 400 secondes restantes


def test_repartir_reprend_la_meme_epreuve_sans_remettre_le_temps_a_zero(client, etudiant, examen):
    client.force_login(etudiant)
    premiere = demarrer(client, examen)
    Tentative.objects.filter(pk=premiere.pk).update(fin_prevue=timezone.now() + timedelta(minutes=30))

    client.post(reverse("entrainement:demarrer_examen", args=[examen.pk]))

    assert Tentative.objects.filter(examen_blanc=examen).count() == 1
    assert examen_blanc.secondes_restantes(Tentative.objects.get()) <= 30 * 60


def test_les_reponses_enregistrees_reviennent_apres_une_coupure(client, etudiant, examen, questions):
    client.force_login(etudiant)
    tentative = demarrer(client, examen)

    reponse = client.post(
        reverse("entrainement:enregistrer", args=[tentative.pk]),
        {f"q-{questions[0].pk}": bonne(questions[0]), "copie": "Annuité : 2 400 000"},
        headers={"HX-Request": "true"},
    )
    assert "Enregistré à" in reponse.content.decode()

    # Rechargement de la page, comme après une coupure réseau.
    page = client.get(reverse("entrainement:epreuve", args=[tentative.pk])).content.decode()
    assert "Annuité : 2 400 000" in page
    assert f'value="{bonne(questions[0])}" class="mt-1 h-5 w-5 shrink-0 accent-vert" checked' in page


def test_la_sauvegarde_est_refusee_une_fois_le_temps_ecoule(client, etudiant, examen):
    client.force_login(etudiant)
    tentative = demarrer(client, examen)
    faire_expirer(tentative)

    reponse = client.post(reverse("entrainement:enregistrer", args=[tentative.pk]), {"copie": "trop tard"})
    assert reponse.status_code == 409


def test_epreuve_abandonnee_rendue_automatiquement_avec_les_reponses_enregistrees(client, etudiant, examen, questions):
    client.force_login(etudiant)
    tentative = demarrer(client, examen)
    client.post(reverse("entrainement:enregistrer", args=[tentative.pk]), {f"q-{questions[0].pk}": bonne(questions[0])})
    faire_expirer(tentative)

    reponse = client.get(reverse("entrainement:epreuve", args=[tentative.pk]))

    assert reponse.url == reverse("entrainement:auto_evaluation", args=[tentative.pk])
    tentative.refresh_from_db()
    assert tentative.fin is not None
    assert tentative.reponses["justes_qcm"] == 1


# --- Remise et correction -----------------------------------------------------------------

def test_la_page_d_epreuve_ne_contient_ni_corrige_ni_bonnes_reponses(client, etudiant, examen):
    Corrige.objects.create(
        sujet=examen.sujet, statut="verifie", publication="publie", auteur="M. Mbarga", titulaire_droits="X",
        partie_gratuite="Corrigé secret de l'exercice 1",
    )
    client.force_login(etudiant)
    page = client.get(reverse("entrainement:epreuve", args=[demarrer(client, examen).pk])).content.decode()

    assert "Corrigé secret" not in page
    assert "Explication 0" not in page


def test_rendre_corrige_le_qcm_puis_montre_le_corrige(client, etudiant, examen, questions):
    Corrige.objects.create(
        sujet=examen.sujet, statut="verifie", publication="publie", auteur="M. Mbarga", titulaire_droits="X",
        partie_gratuite="Corrigé de l'exercice 1",
    )
    client.force_login(etudiant)
    tentative = demarrer(client, examen)

    client.post(
        reverse("entrainement:rendre", args=[tentative.pk]),
        {f"q-{questions[0].pk}": bonne(questions[0]), f"q-{questions[1].pk}": mauvaise(questions[1]), "rendre": "1"},
    )

    tentative.refresh_from_db()
    assert tentative.fin is not None
    assert tentative.reponses["points_qcm"] == "3.00"  # 1 juste sur 2, partie QCM sur 6 points
    assert ReponseQuestion.objects.filter(tentative=tentative).count() == 2
    page = client.get(reverse("entrainement:auto_evaluation", args=[tentative.pk])).content.decode()
    assert "Corrigé de l&#x27;exercice 1" in page or "Corrigé de l'exercice 1" in page
    assert "Explication 1" in page


def test_une_question_sans_reponse_compte_faux(client, etudiant, examen):
    client.force_login(etudiant)
    tentative = demarrer(client, examen)
    client.post(reverse("entrainement:rendre", args=[tentative.pk]), {"rendre": "1"})

    tentative.refresh_from_db()
    assert tentative.reponses["justes_qcm"] == 0
    assert not ReponseQuestion.objects.filter(tentative=tentative, correcte=True).exists()


def test_pas_de_modification_apres_la_remise(client, etudiant, examen, questions):
    client.force_login(etudiant)
    tentative = demarrer(client, examen)
    client.post(reverse("entrainement:rendre", args=[tentative.pk]), {"rendre": "1"})

    reponse = client.post(reverse("entrainement:enregistrer", args=[tentative.pk]), {f"q-{questions[0].pk}": bonne(questions[0])})
    assert reponse.status_code == 409
    client.post(reverse("entrainement:rendre", args=[tentative.pk]), {f"q-{questions[0].pk}": bonne(questions[0])})
    tentative.refresh_from_db()
    assert tentative.reponses["justes_qcm"] == 0


# --- Auto-évaluation ------------------------------------------------------------------------

def test_auto_evaluation_bornee_par_le_bareme_et_note_sur_20(client, etudiant, examen, questions):
    client.force_login(etudiant)
    tentative = demarrer(client, examen)
    client.post(
        reverse("entrainement:rendre", args=[tentative.pk]),
        {f"q-{questions[0].pk}": bonne(questions[0]), f"q-{questions[1].pk}": bonne(questions[1])},
    )
    premier, second = examen.criteres.all()

    client.post(
        reverse("entrainement:auto_evaluation", args=[tentative.pk]),
        {f"critere-{premier.pk}": "5,5", f"critere-{second.pk}": "12"},  # 12 > 7 : ramené à 7
    )

    tentative.refresh_from_db()
    # QCM 6/6 + 5,5 + 7 = 18,5 sur 20 points
    assert tentative.note == Decimal("18.50")
    assert "18.5" in client.get(reverse("entrainement:resultat_examen", args=[tentative.pk])).content.decode().replace(",", ".")


# --- Accès ----------------------------------------------------------------------------------

def test_un_examen_non_publie_ou_au_sujet_non_publie_est_invisible(client, etudiant, examen):
    client.force_login(etudiant)
    Sujet.objects.filter(pk=examen.sujet_id).update(statut=Sujet.Statut.MASQUE)
    assert client.get(reverse("entrainement:consignes", args=[examen.pk])).status_code == 404
    assert examen.titre not in client.get(reverse("entrainement:examens")).content.decode()


def test_l_epreuve_d_un_autre_est_inaccessible(client, etudiant, examen):
    client.force_login(etudiant)
    tentative = demarrer(client, examen)
    intrus = Utilisateur.objects.create_user(email="intrus@example.com", password="Revision-2027")
    client.force_login(intrus)

    assert client.get(reverse("entrainement:epreuve", args=[tentative.pk])).status_code == 404
    assert client.post(reverse("entrainement:enregistrer", args=[tentative.pk]), {"copie": "x"}).status_code == 404


def test_paiement_ouvert_reserve_aux_abonnes(client, settings, etudiant, examen):
    settings.PAIEMENT_ACTIF = True
    client.force_login(etudiant)

    client.post(reverse("entrainement:demarrer_examen", args=[examen.pk]))
    assert not Tentative.objects.exists()


def test_l_admin_refuse_un_examen_publie_sur_un_sujet_non_publie(creer_sujet, session_en_cours):
    from django.core.exceptions import ValidationError

    brouillon = creer_sujet(session_en_cours)
    with pytest.raises(ValidationError):
        ExamenBlanc(titre="X", sujet=brouillon, duree=60, publie=True).full_clean()
