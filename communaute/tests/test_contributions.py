"""Contributions (CDC 3.7, 4.1, 4.2, 10.1) : envoi, contrôles, modération, récompense."""

import io
from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from accounts.models import AffectationModerateur, ProfilEtude, Utilisateur
from catalogue.models import Matiere, SpecialiteMatiere
from communaute.models import Contribution
from paiements.models import Abonnement, Offre, Paiement
from sujets.models import Corrige, Sujet

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4 sujet contribue"


def pdf(nom="sujet.pdf", contenu=PDF):
    return SimpleUploadedFile(nom, contenu, content_type="application/pdf")


def photo(nom):
    sortie = io.BytesIO()
    Image.new("RGB", (60, 80), "white").save(sortie, "PNG")
    return SimpleUploadedFile(nom, sortie.getvalue(), content_type="image/png")


@pytest.fixture
def etudiant(comptabilite):
    utilisateur = Utilisateur.objects.create_user(email="awa@example.com", password="Revision-2027", first_name="Awa")
    ProfilEtude.objects.create(utilisateur=utilisateur, examen=comptabilite.examen, specialite=comptabilite)
    return utilisateur


@pytest.fixture
def admin_client(client):
    client.force_login(Utilisateur.objects.create_superuser(email="admin@example.com", password="Administration-2027"))
    return client


def envoyer(client, comptabilite, matiere, annee, fichiers=None, **autres):
    donnees = {"specialite": comptabilite.pk, "matiere": matiere.pk, "annee": annee, "certifie_droits": "on", **autres}
    donnees["fichiers"] = fichiers if fichiers is not None else [pdf()]
    return client.post(reverse("communaute:envoyer_sujet"), donnees)


def contribution_sujet(etudiant, compta_generale, comptabilite, annee=2025):
    contribution = Contribution(
        utilisateur=etudiant, matiere=compta_generale, specialite=comptabilite, annee=annee, certifie_droits=True
    )
    contribution.fichier.save("sujet.pdf", SimpleUploadedFile("sujet.pdf", PDF), save=False)
    contribution.save()
    return contribution


# --- Envoi ------------------------------------------------------------------------------------------

def test_envoyer_un_sujet_en_pdf(client, etudiant, comptabilite, compta_generale, session_terminee):
    client.force_login(etudiant)
    reponse = envoyer(client, comptabilite, compta_generale, 2025, commentaire="Épreuve écrite")

    assert reponse.url == reverse("communaute:mes_contributions")
    contribution = Contribution.objects.get()
    assert contribution.statut == Contribution.Statut.EN_ATTENTE and contribution.utilisateur == etudiant
    assert contribution.fichier.read() == PDF
    # CDC 10.1 : certification enregistrée avec sa date.
    assert contribution.certifie_droits and contribution.date_certification
    assert "En attente de vérification" in client.get(reverse("communaute:mes_contributions")).content.decode()


def test_les_photos_sont_assemblees_en_un_pdf(client, etudiant, comptabilite, compta_generale, session_terminee):
    client.force_login(etudiant)
    envoyer(client, comptabilite, compta_generale, 2025, fichiers=[photo("page1.png"), photo("page2.png")])
    contenu = Contribution.objects.get().fichier.read()
    assert contenu.startswith(b"%PDF") and contenu.count(b"/Type /Page") - contenu.count(b"/Type /Pages") == 2


@pytest.mark.parametrize("fichiers", [
    [pdf(contenu=b"<html>")],  # faux PDF
    [pdf(), photo("page.png")],  # mélange
    [SimpleUploadedFile("sujet.docx", b"PK", content_type="application/msword")],
])
def test_documents_refuses(client, etudiant, comptabilite, compta_generale, session_terminee, fichiers):
    client.force_login(etudiant)
    envoyer(client, comptabilite, compta_generale, 2025, fichiers=fichiers)
    assert not Contribution.objects.exists()


def test_la_certification_des_droits_est_obligatoire(client, etudiant, comptabilite, compta_generale, session_terminee):
    client.force_login(etudiant)
    envoyer(client, comptabilite, compta_generale, 2025, certifie_droits="")
    assert not Contribution.objects.exists()


def test_un_sujet_d_une_session_en_cours_est_refuse_des_l_envoi(client, etudiant, comptabilite, compta_generale, session_en_cours):
    """Règle absolue (CDC 4.2) : même pas en file de modération."""
    client.force_login(etudiant)
    contenu = envoyer(client, comptabilite, compta_generale, session_en_cours.annee).content.decode()
    assert "n&#x27;est pas terminée" in contenu
    # Année courante sans session enregistrée : refusée elle aussi.
    envoyer(client, comptabilite, compta_generale, timezone.localdate().year)
    assert not Contribution.objects.exists()


def test_alerte_doublon(client, etudiant, comptabilite, compta_generale, session_terminee, creer_sujet):
    creer_sujet(session_terminee)
    client.force_login(etudiant)
    assert "Nous avons déjà ce sujet" in envoyer(client, comptabilite, compta_generale, 2025).content.decode()
    assert not Contribution.objects.exists()

    envoyer(client, comptabilite, compta_generale, 2025, envoyer_quand_meme="on")
    assert Contribution.objects.count() == 1


def test_la_matiere_doit_etre_de_la_specialite(client, etudiant, comptabilite, marketing, bts, session_terminee):
    hors_programme = Matiere.objects.create(examen=bts, nom="Techniques de vente")
    SpecialiteMatiere.objects.create(specialite=marketing, matiere=hors_programme, coefficient=2)
    client.force_login(etudiant)
    envoyer(client, comptabilite, hors_programme, 2025)
    assert not Contribution.objects.exists()


def test_limite_d_envois_par_jour(client, settings, etudiant, comptabilite, compta_generale, session_terminee):
    settings.CONTRIBUTIONS_PAR_JOUR = 1
    client.force_login(etudiant)
    envoyer(client, comptabilite, compta_generale, 2025)
    envoyer(client, comptabilite, compta_generale, 2025, envoyer_quand_meme="on")
    assert Contribution.objects.count() == 1


def test_acces(client, settings, etudiant):
    assert client.get(reverse("communaute:envoyer_sujet")).status_code == 302  # visiteur → connexion
    client.force_login(etudiant)
    assert client.get(reverse("communaute:envoyer_sujet")).status_code == 200
    settings.FONCTIONNALITES = {**settings.FONCTIONNALITES, "contributions": False}
    assert client.get(reverse("communaute:envoyer_sujet")).status_code == 404


# --- Modération : sujet -----------------------------------------------------------------------------------

def test_valider_un_sujet_le_cree_en_brouillon_et_offre_des_jours(
    admin_client, etudiant, comptabilite, compta_generale, session_terminee, django_capture_on_commit_callbacks
):
    contribution = contribution_sujet(etudiant, compta_generale, comptabilite)
    url = reverse("admin:communaute_contribution_valider", args=[contribution.pk])
    page = admin_client.get(url).content.decode()
    assert "MINESUP, BTS session 2025" in page  # fiche préremplie

    with django_capture_on_commit_callbacks(execute=True):
        admin_client.post(url, {
            "session": session_terminee.pk, "titre": "Comptabilité générale", "type_epreuve": "ecrite", "duree": 240,
            "source": "MINESUP, BTS session 2025", "specialites": [comptabilite.pk],
        })

    contribution.refresh_from_db()
    sujet = contribution.sujet
    assert contribution.statut == Contribution.Statut.VALIDEE and contribution.traitee_par.is_superuser
    # Toujours en brouillon : la publication reste une décision à part, soumise à la règle.
    assert sujet.statut == Sujet.Statut.BROUILLON and sujet.fichier.read() == PDF
    assert list(sujet.specialites.all()) == [comptabilite]
    recompense = Abonnement.objects.get(utilisateur=etudiant)
    assert recompense.contribution == contribution and (recompense.fin - recompense.debut).days + 1 == 7
    assert contribution.jours_offerts == 7
    assert len(mail.outbox) == 1 and "validée" in mail.outbox[0].subject


def test_les_jours_offerts_s_ajoutent_a_l_abonnement_en_cours(etudiant, compta_generale, comptabilite, session_terminee):
    from communaute import contributions

    aujourd_hui = timezone.localdate()
    offre = Offre.objects.create(nom="Mensuel", prix=1500, type="duree", duree_jours=30)
    paiement = Paiement.objects.create(utilisateur=etudiant, offre=offre, montant=1500, operateur="mtn", reference="R1", statut="reussi")
    Abonnement.objects.create(utilisateur=etudiant, offre=offre, debut=aujourd_hui, fin=aujourd_hui + timedelta(days=29), paiement=paiement)

    contributions.valider_sujet(
        contribution_sujet(etudiant, compta_generale, comptabilite), None, session=session_terminee, titre="T",
        type_epreuve="ecrite", duree=240, source="MINESUP", specialites=[comptabilite],
    )
    recompense = Abonnement.objects.get(contribution__isnull=False)
    assert recompense.debut == aujourd_hui + timedelta(days=30)


def test_valider_un_sujet_d_une_session_en_cours_est_impossible(
    admin_client, etudiant, comptabilite, compta_generale, session_en_cours
):
    contribution = contribution_sujet(etudiant, compta_generale, comptabilite, annee=2025)
    admin_client.post(reverse("admin:communaute_contribution_valider", args=[contribution.pk]), {
        "session": session_en_cours.pk, "titre": "X", "type_epreuve": "ecrite", "duree": 240, "source": "X",
        "specialites": [comptabilite.pk],
    })
    contribution.refresh_from_db()
    assert contribution.statut == Contribution.Statut.EN_ATTENTE and not Sujet.objects.exists()


def test_rejeter_supprime_le_fichier_et_previent(admin_client, etudiant, comptabilite, compta_generale, django_capture_on_commit_callbacks):
    contribution = contribution_sujet(etudiant, compta_generale, comptabilite)
    chemin = contribution.fichier.name
    url = reverse("admin:communaute_contribution_rejeter", args=[contribution.pk])
    admin_client.post(url, {"motif": ""})  # motif obligatoire
    assert Contribution.objects.get().statut == Contribution.Statut.EN_ATTENTE

    with django_capture_on_commit_callbacks(execute=True):
        admin_client.post(url, {"motif": "Photo illisible."})

    contribution.refresh_from_db()
    assert contribution.statut == Contribution.Statut.REJETEE and not contribution.fichier
    assert not contribution.fichier.storage.exists(chemin)
    assert "Photo illisible." in mail.outbox[0].body
    assert not Abonnement.objects.exists()
    admin_client.force_login(etudiant)
    assert "Photo illisible." in admin_client.get(reverse("communaute:mes_contributions")).content.decode()


def test_une_contribution_traitee_ne_se_retraite_pas(admin_client, etudiant, comptabilite, compta_generale):
    contribution = contribution_sujet(etudiant, compta_generale, comptabilite)
    admin_client.post(reverse("admin:communaute_contribution_rejeter", args=[contribution.pk]), {"motif": "Doublon."})
    assert admin_client.get(reverse("admin:communaute_contribution_valider", args=[contribution.pk])).status_code == 404


def test_un_moderateur_ne_traite_que_ses_matieres(client, etudiant, comptabilite, compta_generale, bts):
    autre = Matiere.objects.create(examen=bts, nom="Droit")
    moderateur = Utilisateur.objects.create_user(email="mod@example.com", password="Moderation-2027", is_staff=True)
    moderateur.groups.add(Group.objects.get(name="Modérateur"))
    AffectationModerateur.objects.create(moderateur=moderateur, matiere=autre)
    contribution = contribution_sujet(etudiant, compta_generale, comptabilite)
    client.force_login(moderateur)

    assert client.get(reverse("admin:communaute_contribution_valider", args=[contribution.pk])).status_code == 404
    assert client.get(reverse("admin:communaute_contribution_fichier", args=[contribution.pk])).status_code == 404


def test_le_fichier_est_reserve_a_l_equipe(client, admin_client, etudiant, comptabilite, compta_generale):
    contribution = contribution_sujet(etudiant, compta_generale, comptabilite)
    url = reverse("admin:communaute_contribution_fichier", args=[contribution.pk])
    assert admin_client.get(url).status_code == 200
    fiche = admin_client.get(reverse("admin:communaute_contribution_change", args=[contribution.pk])).content.decode()
    assert reverse("admin:communaute_contribution_valider", args=[contribution.pk]) in fiche and url in fiche
    assert admin_client.get(reverse("admin:communaute_contribution_changelist")).status_code == 200
    client.force_login(etudiant)
    assert client.get(url).status_code == 302  # pas d'accès à l'admin


# --- Corrigés proposés ---------------------------------------------------------------------------------------

def test_proposer_puis_valider_un_corrige(client, etudiant, creer_sujet, session_terminee):
    sujet = creer_sujet(session_terminee, statut=Sujet.Statut.PUBLIE)
    client.force_login(etudiant)
    assert "Proposez votre corrigé" in client.get(reverse("sujets:detail", args=[sujet.pk]) + "?onglet=corrige").content.decode()
    client.post(reverse("communaute:proposer_corrige", args=[sujet.pk]), {"texte": "**Exercice 1** : 240 000 FCFA.", "certifie_droits": "on"})
    contribution = Contribution.objects.get()
    assert contribution.type == Contribution.Type.CORRIGE and contribution.sujet_vise == sujet

    client.force_login(Utilisateur.objects.create_superuser(email="admin@example.com", password="Administration-2027"))
    url = reverse("admin:communaute_contribution_valider", args=[contribution.pk])
    assert "Awa" in client.get(url).content.decode()  # auteur prérempli
    client.post(url, {"auteur": "Awa", "titulaire_droits": "Awa", "partie_gratuite": contribution.texte, "contenu": ""})

    corrige = Corrige.objects.get()
    assert corrige.statut == Corrige.Statut.COMMUNAUTE and corrige.publication == Corrige.Publication.BROUILLON
    assert corrige.sujet == sujet and "240 000" in corrige.partie_gratuite
    assert not Abonnement.objects.exists()  # CDC 3.7 : jours offerts pour les sujets


def test_un_corrige_vide_ou_pour_un_sujet_non_publie_est_refuse(client, etudiant, creer_sujet, session_terminee, session_en_cours):
    client.force_login(etudiant)
    brouillon = creer_sujet(session_en_cours)
    assert client.get(reverse("communaute:proposer_corrige", args=[brouillon.pk])).status_code == 404

    publie = creer_sujet(session_terminee, statut=Sujet.Statut.PUBLIE)
    client.post(reverse("communaute:proposer_corrige", args=[publie.pk]), {"texte": "  ", "certifie_droits": "on"})
    assert not Contribution.objects.exists()
