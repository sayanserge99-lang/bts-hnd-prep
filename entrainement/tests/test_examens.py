"""Examens blancs (CDC 3.5) : durée réelle, sauvegarde continue, reprise, soumission automatique, auto-évaluation."""

import re
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
    assert re.search(rf'value="{bonne(questions[0])}"[^>]*checked', page)


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


# --- Une question à la fois (maquette, écran 10) --------------------------------------------------------

def test_une_question_par_panneau_avec_grille_et_marque(client, etudiant, examen, questions):
    client.force_login(etudiant)
    tentative = demarrer(client, examen)
    page = client.get(reverse("entrainement:epreuve", args=[tentative.pk])).content.decode()
    assert page.count("data-panneau") == len(questions) + 1  # + la partie rédactionnelle
    assert page.count("data-case") == len(questions) + 1
    assert "Partie 1 · Question 1 sur 2" in page and "data-marquer" in page
    assert "Répondue" in page and "En cours" in page and "Marquée" in page
    assert "La correction s&#x27;affiche seulement" in page or "La correction s'affiche seulement" in page


def test_les_questions_marquees_sont_enregistrees_et_reviennent(client, etudiant, examen, questions):
    client.force_login(etudiant)
    tentative = demarrer(client, examen)
    marquee = questions[1].pk
    client.post(reverse("entrainement:enregistrer", args=[tentative.pk]), {"marquees": f"{marquee},999999,abc"})
    tentative.refresh_from_db()
    assert tentative.reponses["marquees"] == [marquee]  # une question d'une autre épreuve est ignorée
    page = client.get(reverse("entrainement:epreuve", args=[tentative.pk])).content.decode()
    assert f'id="marquees" value="{marquee}"' in page and 'aria-pressed="true"' in page


def test_une_reponse_envoyee_apres_l_heure_de_fin_est_refusee(client, etudiant, examen, questions, settings):
    """Au-delà de l'heure de fin (et de la marge de transmission), ni enregistrée, ni comptée à la remise."""
    client.force_login(etudiant)
    tentative = demarrer(client, examen)
    client.post(reverse("entrainement:enregistrer", args=[tentative.pk]), {f"q-{questions[0].pk}": mauvaise(questions[0])})
    Tentative.objects.filter(pk=tentative.pk).update(
        fin_prevue=timezone.now() - timedelta(seconds=settings.EXAMEN_DELAI_GRACE_SECONDES + 1)
    )

    tardive = {f"q-{questions[0].pk}": bonne(questions[0]), f"q-{questions[1].pk}": bonne(questions[1])}
    assert client.post(reverse("entrainement:enregistrer", args=[tentative.pk]), tardive).status_code == 409
    tentative.refresh_from_db()
    assert tentative.reponses["brouillon"] == {str(questions[0].pk): [mauvaise(questions[0])]}

    # La remise tardive non plus ne fait pas entrer ces réponses : seules comptent celles d'avant la fin.
    client.post(reverse("entrainement:rendre", args=[tentative.pk]), tardive)
    tentative.refresh_from_db()
    assert tentative.fin is not None and tentative.reponses["justes_qcm"] == 0
    assert tentative.fin <= tentative.fin_prevue


def test_la_marge_de_90_secondes_ne_sert_qu_au_transport(client, etudiant, examen, questions, settings):
    """Réponse partie avant 0:00 et arrivée 30 s après (réseau lent) : acceptée et comptée à la remise."""
    client.force_login(etudiant)
    tentative = demarrer(client, examen)
    Tentative.objects.filter(pk=tentative.pk).update(fin_prevue=timezone.now() - timedelta(seconds=30))
    assert settings.EXAMEN_DELAI_GRACE_SECONDES == 90

    client.post(reverse("entrainement:rendre", args=[tentative.pk]), {f"q-{questions[0].pk}": bonne(questions[0])})

    tentative.refresh_from_db()
    assert tentative.reponses["justes_qcm"] == 1
    assert tentative.fin <= tentative.fin_prevue  # l'heure de remise reste celle de la fin du temps


def test_les_consignes_annoncent_la_fermeture_de_la_copie(client, etudiant, examen):
    client.force_login(etudiant)
    page = client.get(reverse("entrainement:consignes", args=[examen.pk])).content.decode()
    assert "La copie se ferme automatiquement à la fin du temps." in page


def test_le_bandeau_de_connexion_perdue_dit_la_regle_des_90_secondes(client, etudiant, examen, questions):
    client.force_login(etudiant)
    tentative = demarrer(client, examen)
    page = client.get(reverse("entrainement:epreuve", args=[tentative.pk])).content.decode().replace("&#x27;", "'")
    assert ('id="bandeau-hors-ligne"' in page and "Connexion perdue. Vos réponses sont gardées sur le téléphone et envoyées "
            "dès le retour du réseau. Attention : après la fin du temps, les réponses qui ne sont pas arrivées dans "
            "les 90 secondes ne sont pas comptées." in page)
    # Sauvegarde au fil de l'eau : HTMX écoute aussi « sauvegarder », lancé par examen.js au retour du réseau.
    assert "every 30s, sauvegarder" in page


# --- Copie locale des réponses (static/js/copie-locale.js) -------------------------------------------------

def test_le_serveur_confirme_la_version_recue_de_la_copie_locale(client, etudiant, examen, questions):
    client.force_login(etudiant)
    tentative = demarrer(client, examen)
    adresse = reverse("entrainement:enregistrer", args=[tentative.pk])
    assert client.post(adresse, {f"q-{questions[0].pk}": bonne(questions[0]), "version": "3"})["X-Version-Recue"] == "3"
    # Un envoi plus ancien arrivé en retard ne fait pas reculer la version : la copie plus récente reste à envoyer.
    assert client.post(adresse, {f"q-{questions[0].pk}": bonne(questions[0]), "version": "2"})["X-Version-Recue"] == "3"
    page = client.get(reverse("entrainement:epreuve", args=[tentative.pk])).content.decode()
    assert 'data-version-recue="3"' in page and 'name="version" id="version-copie" value="3"' in page

    client.post(reverse("entrainement:rendre", args=[tentative.pk]), {f"q-{questions[0].pk}": bonne(questions[0]), "version": "4"})
    tentative.refresh_from_db()
    assert examen_blanc.version_recue(tentative) == 4  # la remise compte : la page suivante efface la copie


def test_un_renvoi_de_la_copie_locale_apres_fin_plus_90_s_est_refuse(client, etudiant, examen, questions, settings):
    """Le serveur juge à l'heure de réception, même pour des réponses gardées sur le téléphone."""
    client.force_login(etudiant)
    tentative = demarrer(client, examen)
    adresse = reverse("entrainement:enregistrer", args=[tentative.pk])
    client.post(adresse, {f"q-{questions[0].pk}": mauvaise(questions[0]), "version": "1"})
    Tentative.objects.filter(pk=tentative.pk).update(
        fin_prevue=timezone.now() - timedelta(seconds=settings.EXAMEN_DELAI_GRACE_SECONDES + 1)
    )

    reponse = client.post(adresse, {f"q-{questions[0].pk}": bonne(questions[0]), "version": "5"})

    assert reponse.status_code == 409
    tentative.refresh_from_db()
    assert tentative.reponses["brouillon"] == {str(questions[0].pk): [mauvaise(questions[0])]}
    assert examen_blanc.version_recue(tentative) == 1
    # La page de l'épreuve terminée porte la version reçue et le message montré si la copie locale est refusée.
    page = client.get(reverse("entrainement:epreuve", args=[tentative.pk]), follow=True).content.decode().replace("&#x27;", "'")
    assert "data-copie-tardive" in page and 'data-version-recue="1"' in page
    assert "Ces réponses sont arrivées après la fin de l'épreuve et n'ont pas été comptées." in page


def test_la_deconnexion_efface_la_copie_locale(client, etudiant):
    client.force_login(etudiant)
    page = client.get(reverse("accounts:profil")).content.decode()
    assert "js/copie-locale.js" in page
    assert re.search(r'action="/[^"]*deconnexion/"[^>]*data-efface-copie-locale', page)
    assert "data-efface-copie-locale" in client.get(reverse("accounts:supprimer")).content.decode()
