"""QCM (CDC 3.4) : banque de questions, quiz rapide, correction immédiate, révision des erreurs."""

import pytest
from django.urls import reverse

from accounts.models import ProfilEtude, Utilisateur
from catalogue.models import Chapitre, Matiere, SpecialiteMatiere
from entrainement import quiz
from entrainement.correction import est_correcte, normaliser
from entrainement.models import Choix, Question, ReponseQuestion, Tentative

pytestmark = pytest.mark.django_db


@pytest.fixture
def chapitre(compta_generale):
    return Chapitre.objects.create(matiere=compta_generale, titre="Amortissements", ordre=1)


def creer_question(chapitre, type_question="choix_unique", choix=(("Bonne", True), ("Mauvaise", False)), publiee=True, **champs):
    question = Question.objects.create(
        chapitre=chapitre, type=type_question, enonce=champs.pop("enonce", "Question ?"), langue="fr", publiee=publiee, **champs
    )
    for texte, correct in choix:
        Choix.objects.create(question=question, texte=texte, est_correct=correct)
    return question


@pytest.fixture
def etudiant(comptabilite):
    utilisateur = Utilisateur.objects.create_user(email="awa@example.com", password="Revision-2027")
    ProfilEtude.objects.create(utilisateur=utilisateur, examen=comptabilite.examen, specialite=comptabilite)
    return utilisateur


def bonne(question):
    return question.choix.get(est_correct=True).pk


def mauvaise(question):
    return question.choix.filter(est_correct=False).first().pk


def repondre(client, tentative, question, **donnees):
    return client.post(reverse("entrainement:repondre", args=[tentative.pk]), {"question": question.pk, **donnees})


# --- Correction ------------------------------------------------------------------

def test_reponse_courte_tolerante():
    assert normaliser(" 1 200,5 ") == normaliser("1200.5")
    assert normaliser("Dégressif") == normaliser("degressif")


def test_correction_de_chaque_type(chapitre):
    unique = creer_question(chapitre)
    assert est_correcte(unique, [bonne(unique)])
    assert not est_correcte(unique, [mauvaise(unique)])

    multiple = creer_question(chapitre, "choix_multiple", (("A", True), ("B", True), ("C", False)))
    a, b, c = multiple.choix.values_list("pk", flat=True)
    assert est_correcte(multiple, [a, b])
    assert not est_correcte(multiple, [a])  # incomplet
    assert not est_correcte(multiple, [a, b, c])  # une en trop

    courte = creer_question(chapitre, "reponse_courte", (), reponse_attendue="40|40 %|0,4")
    assert est_correcte(courte, "40 %") and est_correcte(courte, "0.4")
    assert not est_correcte(courte, "20")


def test_coherence_avant_publication(chapitre):
    assert creer_question(chapitre, choix=(("A", True), ("B", True))).problemes()
    assert creer_question(chapitre, "choix_multiple", (("A", False), ("B", False))).problemes()
    assert creer_question(chapitre, "vrai_faux", (("Vrai", True),)).problemes()
    assert creer_question(chapitre, "reponse_courte", ()).problemes()
    assert not creer_question(chapitre).problemes()


# --- Parcours ------------------------------------------------------------------------

def test_l_entrainement_exige_une_connexion(client):
    assert client.get(reverse("entrainement:accueil")).status_code == 302


def test_accueil_propose_les_matieres_de_la_specialite(client, etudiant, chapitre, bts, marketing):
    creer_question(chapitre)
    autre = Matiere.objects.create(examen=bts, nom="Marketing fondamental")
    SpecialiteMatiere.objects.create(specialite=marketing, matiere=autre, coefficient=4)
    creer_question(Chapitre.objects.create(matiere=autre, titre="Mix", ordre=1))
    client.force_login(etudiant)

    contenu = client.get(reverse("entrainement:accueil")).content.decode()
    assert "Comptabilité générale" in contenu
    assert "Marketing fondamental" not in contenu


def test_quiz_rapide_dix_questions_publiees_de_la_matiere(etudiant, chapitre, compta_generale):
    for numero in range(12):
        creer_question(chapitre, enonce=f"Q{numero}")
    brouillon = creer_question(chapitre, publiee=False)

    tentative = quiz.lancer_quiz_rapide(etudiant, compta_generale)

    assert len(tentative.ordre) == quiz.QUESTIONS_PAR_QUIZ
    assert brouillon.pk not in tentative.ordre


def test_sans_question_le_quiz_n_est_pas_lance(client, etudiant, compta_generale):
    client.force_login(etudiant)
    reponse = client.post(reverse("entrainement:lancer"), {"matiere": compta_generale.pk}, follow=True)
    assert "Aucune question disponible" in reponse.content.decode()
    assert not Tentative.objects.exists()


def test_la_bonne_reponse_n_est_pas_dans_la_page_avant_de_repondre(client, etudiant, chapitre, compta_generale):
    creer_question(chapitre, explication="Explication secrète")
    client.force_login(etudiant)
    client.post(reverse("entrainement:lancer"), {"matiere": compta_generale.pk})

    contenu = client.get(reverse("entrainement:tentative", args=[Tentative.objects.get().pk])).content.decode()
    assert "Explication secrète" not in contenu
    assert "est_correct" not in contenu and "✓" not in contenu


def test_un_quiz_complet_avec_correction_immediate(client, etudiant, chapitre, compta_generale):
    q1 = creer_question(chapitre, enonce="Première", explication="Parce que.")
    q2 = creer_question(chapitre, enonce="Seconde")
    client.force_login(etudiant)
    client.post(reverse("entrainement:lancer"), {"matiere": compta_generale.pk})
    tentative = Tentative.objects.get()
    premiere, seconde = (Question.objects.get(pk=pk) for pk in tentative.ordre)

    correction = repondre(client, tentative, premiere, choix=bonne(premiere)).content.decode()
    assert "Bonne réponse" in correction
    assert "Question suivante" in correction

    correction = repondre(client, tentative, seconde, choix=mauvaise(seconde)).content.decode()
    assert "pas la bonne réponse" in correction
    assert "Voir mon résultat" in correction

    tentative.refresh_from_db()
    assert tentative.fin is not None
    assert tentative.note == 10
    assert "1 bonne(s) réponse(s) sur 2" in client.get(reverse("entrainement:resultat", args=[tentative.pk])).content.decode()
    assert {q1.pk, q2.pk} == set(tentative.ordre)


def test_pas_de_seconde_chance_ni_de_saut_de_question(client, etudiant, chapitre, compta_generale):
    creer_question(chapitre)
    creer_question(chapitre)
    client.force_login(etudiant)
    client.post(reverse("entrainement:lancer"), {"matiere": compta_generale.pk})
    tentative = Tentative.objects.get()
    premiere, seconde = (Question.objects.get(pk=pk) for pk in tentative.ordre)

    repondre(client, tentative, seconde, choix=bonne(seconde))  # pas encore son tour
    assert not ReponseQuestion.objects.exists()

    repondre(client, tentative, premiere, choix=mauvaise(premiere))
    repondre(client, tentative, premiere, choix=bonne(premiere))  # déjà corrigée
    assert ReponseQuestion.objects.get(question=premiere).correcte is False


def test_une_reponse_vide_est_redemandee(client, etudiant, chapitre, compta_generale):
    question = creer_question(chapitre)
    client.force_login(etudiant)
    client.post(reverse("entrainement:lancer"), {"matiere": compta_generale.pk})

    contenu = repondre(client, Tentative.objects.get(), question).content.decode()
    assert "Choisissez une réponse" in contenu
    assert not ReponseQuestion.objects.exists()


def test_la_tentative_d_un_autre_est_inaccessible(client, etudiant, chapitre, compta_generale):
    creer_question(chapitre)
    tentative = quiz.lancer_quiz_rapide(etudiant, compta_generale)
    intrus = Utilisateur.objects.create_user(email="intrus@example.com", password="Revision-2027")
    client.force_login(intrus)

    assert client.get(reverse("entrainement:tentative", args=[tentative.pk])).status_code == 404


def test_htmx_ne_renvoie_que_la_correction(client, etudiant, chapitre, compta_generale):
    question = creer_question(chapitre)
    client.force_login(etudiant)
    client.post(reverse("entrainement:lancer"), {"matiere": compta_generale.pk})

    reponse = client.post(
        reverse("entrainement:repondre", args=[Tentative.objects.get().pk]),
        {"question": question.pk, "choix": bonne(question)},
        headers={"HX-Request": "true"},
    )
    assert "<html" not in reponse.content.decode()
    assert "Bonne réponse" in reponse.content.decode()


# --- Révision des erreurs ----------------------------------------------------------

def test_revision_des_seules_erreurs_encore_non_corrigees(etudiant, chapitre, compta_generale):
    ratee = creer_question(chapitre, enonce="Ratée")
    reussie = creer_question(chapitre, enonce="Réussie")
    rattrapee = creer_question(chapitre, enonce="Rattrapée")
    premiere = quiz.creer_tentative(etudiant, [ratee, reussie, rattrapee], "rapide", compta_generale)
    for question, correcte in ((ratee, False), (reussie, True), (rattrapee, False)):
        ReponseQuestion.objects.create(tentative=premiere, question=question, reponse=[], correcte=correcte)
    seconde = quiz.creer_tentative(etudiant, [rattrapee], "rapide", compta_generale)
    ReponseQuestion.objects.create(tentative=seconde, question=rattrapee, reponse=[], correcte=True)

    assert list(quiz.erreurs_a_reviser(etudiant)) == [ratee]
    assert quiz.lancer_revision(etudiant, compta_generale).ordre == [ratee.pk]


# --- Limite de l'offre gratuite ------------------------------------------------------

def test_quiz_illimites_tant_que_le_paiement_est_ferme(etudiant):
    assert quiz.quiz_restants_aujourd_hui(etudiant) is None


def test_quiz_limites_par_jour_une_fois_le_paiement_ouvert(client, settings, etudiant, chapitre, compta_generale):
    settings.PAIEMENT_ACTIF = True
    settings.QUIZ_GRATUITS_PAR_JOUR = 2
    creer_question(chapitre)
    client.force_login(etudiant)

    for _ in range(3):
        client.post(reverse("entrainement:lancer"), {"matiere": compta_generale.pk})

    assert Tentative.objects.count() == 2


# --- Administration ------------------------------------------------------------------

def test_l_admin_refuse_de_publier_une_question_incoherente(admin_client, chapitre):
    incoherente = creer_question(chapitre, choix=(("A", True), ("B", True)), publiee=False)
    correcte = creer_question(chapitre, publiee=False)

    admin_client.post(
        reverse("admin:entrainement_question_changelist"),
        {"action": "publier", "_selected_action": [incoherente.pk, correcte.pk]},
    )

    incoherente.refresh_from_db()
    correcte.refresh_from_db()
    assert not incoherente.publiee
    assert correcte.publiee
