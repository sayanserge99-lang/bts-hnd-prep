"""« Signaler cette question » (maquette, écran 8) : un Signalement visible du modérateur de la matière."""

import pytest
from django.contrib.auth.models import Group
from django.core import mail
from django.db import IntegrityError, transaction
from django.urls import reverse

from accounts.models import AffectationModerateur, ProfilEtude, Utilisateur
from catalogue.models import Chapitre, Matiere
from communaute.models import Signalement
from config import securite
from entrainement import quiz
from entrainement.models import Choix, Question

pytestmark = pytest.mark.django_db


@pytest.fixture
def question(compta_generale):
    chapitre = Chapitre.objects.create(matiere=compta_generale, titre="Amortissements", ordre=1)
    question = Question.objects.create(chapitre=chapitre, type="choix_unique", enonce="Annuité linéaire ?", langue="fr", publiee=True)
    Choix.objects.create(question=question, texte="2 000 000 FCFA", est_correct=True)
    Choix.objects.create(question=question, texte="1 000 000 FCFA", est_correct=False)
    return question


@pytest.fixture
def etudiant(comptabilite):
    utilisateur = Utilisateur.objects.create_user(email="awa@example.com", password="Revision-2027")
    ProfilEtude.objects.create(utilisateur=utilisateur, examen=comptabilite.examen, specialite=comptabilite)
    return utilisateur


def moderateur_de(matiere, email):
    moderateur = Utilisateur.objects.create_user(email=email, password="Moderation-2027", is_staff=True)
    moderateur.groups.add(Group.objects.get(name="Modérateur"))
    AffectationModerateur.objects.create(moderateur=moderateur, matiere=matiere)
    return moderateur


def signaler(client, question, motif="La bonne réponse est fausse : c'est 2 400 000.", **entetes):
    return client.post(reverse("entrainement:signaler_question", args=[question.pk]),
                       {"motif": motif, "suite": "/entrainement/"}, headers=entetes)


def test_le_lien_est_sous_la_question_sans_reveler_la_reponse(client, etudiant, question, compta_generale):
    client.force_login(etudiant)
    tentative = quiz.creer_tentative(etudiant, [question], "rapide", compta_generale)
    page = client.get(reverse("entrainement:tentative", args=[tentative.pk])).content.decode()
    assert "Signaler cette question" in page
    assert reverse("entrainement:signaler_question", args=[question.pk]) in page
    assert "est_correct" not in page and "Bonne réponse" not in page


def test_signaler_cree_un_signalement_et_previent_l_equipe(client, settings, etudiant, question):
    settings.ADMINS = [("Équipe", "equipe@example.com")]
    client.force_login(etudiant)
    reponse = signaler(client, question, HX_Request="true")
    assert "Merci" in reponse.content.decode()
    signalement = Signalement.objects.get()
    assert signalement.question == question and signalement.sujet is None and signalement.corrige is None
    assert signalement.utilisateur == etudiant and signalement.statut == Signalement.Statut.OUVERT
    assert "Question signalée" in mail.outbox[0].subject


def test_motif_trop_court_question_invisible_et_limite(client, etudiant, question):
    client.force_login(etudiant)
    signaler(client, question, motif="faux")
    assert not Signalement.objects.exists()

    cachee = Question.objects.create(chapitre=question.chapitre, type="vrai_faux", enonce="?", langue="fr", publiee=False)
    assert signaler(client, cachee).status_code == 404

    for _ in range(securite.SIGNALEMENTS_QUESTION_PAR_COMPTE.maximum + 2):
        signaler(client, question)
    assert Signalement.objects.count() == securite.SIGNALEMENTS_QUESTION_PAR_COMPTE.maximum


def test_il_faut_etre_connecte(client, question):
    assert signaler(client, question).status_code == 302
    assert not Signalement.objects.exists()


def test_visible_du_moderateur_de_la_matiere_seulement(client, etudiant, question, compta_generale, bts):
    signalement = Signalement.objects.create(utilisateur=etudiant, question=question, motif="Énoncé ambigu.")
    liste = reverse("admin:communaute_signalement_changelist")
    fiche = reverse("admin:communaute_signalement_change", args=[signalement.pk])

    client.force_login(moderateur_de(compta_generale, "mod.compta@example.com"))
    page = client.get(liste).content.decode()
    assert "Énoncé ambigu." in page and "Question (Amortissements)" in page
    assert client.get(fiche).status_code == 200

    client.force_login(moderateur_de(Matiere.objects.create(examen=bts, nom="Droit"), "mod.droit@example.com"))
    assert "Énoncé ambigu." not in client.get(liste).content.decode()
    assert client.get(fiche).status_code in (302, 403, 404)


def test_une_seule_cible_par_signalement(etudiant, question, creer_sujet, session_terminee):
    sujet = creer_sujet(session_terminee)
    with pytest.raises(IntegrityError), transaction.atomic():
        Signalement.objects.create(utilisateur=etudiant, question=question, sujet=sujet, motif="Deux cibles")
    with pytest.raises(IntegrityError), transaction.atomic():
        Signalement.objects.create(utilisateur=etudiant, motif="Aucune cible")
