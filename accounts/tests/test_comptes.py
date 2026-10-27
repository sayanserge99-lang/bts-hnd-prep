"""Comptes (CDC 3.1) et droits sur les données personnelles (CDC 10.2)."""

import json

import pytest
from django.conf import settings
from django.core import mail
from django.urls import reverse

from accounts.models import Consentement, Utilisateur
from sujets.models import Favori, Sujet

pytestmark = pytest.mark.django_db

MOT_DE_PASSE = "Revision-BTS-2027"


@pytest.fixture
def etudiant(comptabilite):
    from accounts.models import ProfilEtude

    utilisateur = Utilisateur.objects.create_user(email="awa@example.com", password=MOT_DE_PASSE, first_name="Awa")
    ProfilEtude.objects.create(utilisateur=utilisateur, examen=comptabilite.examen, specialite=comptabilite)
    return utilisateur


def inscrire(client, comptabilite, **champs):
    donnees = {
        "first_name": "Awa",
        "last_name": "Ngono",
        "email": "Awa.Ngono@Example.com",
        "langue": "fr",
        "specialite": comptabilite.pk,
        "password1": MOT_DE_PASSE,
        "password2": MOT_DE_PASSE,
        "accepte_conditions": "on", "examen": "BTS",
        **champs,
    }
    return client.post(reverse("accounts:inscription"), donnees)


def test_inscription_cree_compte_profil_consentements_et_role(client, comptabilite):
    reponse = inscrire(client, comptabilite)

    assert reponse.status_code == 302
    utilisateur = Utilisateur.objects.get()
    assert utilisateur.email == "awa.ngono@example.com"
    assert utilisateur.groups.filter(name="Étudiant").exists()
    assert utilisateur.profil.specialite == comptabilite
    assert utilisateur.profil.examen == comptabilite.examen
    objets = set(utilisateur.consentements.values_list("objet", flat=True))
    assert objets == {Consentement.Objet.CGU, Consentement.Objet.CONFIDENTIALITE}
    assert utilisateur.consentements.first().version == settings.VERSION_POLITIQUES
    # Connecté directement après l'inscription.
    assert client.get(reverse("accounts:profil")).status_code == 200


def test_inscription_refusee_sans_consentement(client, comptabilite):
    inscrire(client, comptabilite, accepte_conditions="")
    assert not Utilisateur.objects.exists()


def test_la_case_de_consentement_n_est_pas_precochee(client, comptabilite):
    contenu = client.get(reverse("accounts:inscription")).content.decode()
    case = contenu[contenu.index('name="accepte_conditions"') - 200 : contenu.index('name="accepte_conditions"') + 100]
    assert "checked" not in case


def test_une_adresse_ne_sert_qu_une_fois_quelle_que_soit_la_casse(client, comptabilite, etudiant):
    inscrire(client, comptabilite, email="AWA@example.com")
    assert Utilisateur.objects.count() == 1


def test_connexion_par_email_sans_tenir_compte_de_la_casse(client, etudiant):
    reponse = client.post(reverse("accounts:connexion"), {"username": "AWA@Example.com", "password": MOT_DE_PASSE})
    assert reponse.status_code == 302
    assert reponse.url == reverse("accounts:profil")


def test_connexion_bloquee_apres_trop_d_echecs(client, etudiant):
    for _ in range(settings.CONNEXION_ESSAIS_MAX):
        client.post(reverse("accounts:connexion"), {"username": etudiant.email, "password": "faux"})

    # Même avec le bon mot de passe, le compte reste bloqué pendant la durée prévue.
    reponse = client.post(reverse("accounts:connexion"), {"username": etudiant.email, "password": MOT_DE_PASSE})
    assert reponse.status_code == 200
    assert "Trop de tentatives" in reponse.content.decode()


def test_le_profil_exige_une_connexion(client):
    reponse = client.get(reverse("accounts:profil"))
    assert reponse.status_code == 302
    assert reponse.url.startswith(reverse("accounts:connexion"))


def test_modifier_le_profil(client, etudiant, marketing):
    client.force_login(etudiant)
    client.post(
        reverse("accounts:modifier_profil"),
        {"first_name": "Awa", "last_name": "Ngono", "langue": "en", "specialite": marketing.pk},
    )
    etudiant.refresh_from_db()
    assert etudiant.langue == "en"
    assert etudiant.profil.specialite == marketing


def test_favoris(client, etudiant, creer_sujet, session_terminee):
    sujet = creer_sujet(session_terminee, statut=Sujet.Statut.PUBLIE)
    client.force_login(etudiant)

    client.post(reverse("sujets:favori", args=[sujet.pk]))
    assert Favori.objects.filter(utilisateur=etudiant, sujet=sujet).exists()
    assert sujet.titre in client.get(reverse("accounts:profil")).content.decode()

    client.post(reverse("sujets:favori", args=[sujet.pk]))
    assert not Favori.objects.exists()


def test_pas_de_favori_sur_un_sujet_non_publie(client, etudiant, creer_sujet, session_en_cours):
    sujet = creer_sujet(session_en_cours)
    client.force_login(etudiant)
    assert client.post(reverse("sujets:favori", args=[sujet.pk])).status_code == 404


def test_un_visiteur_est_invite_a_se_connecter_pour_un_favori(client, creer_sujet, session_terminee):
    sujet = creer_sujet(session_terminee, statut=Sujet.Statut.PUBLIE)
    contenu = client.get(reverse("sujets:detail", args=[sujet.pk])).content.decode()
    assert "Se connecter pour garder ce sujet" in contenu


def test_export_des_donnees(client, etudiant):
    client.force_login(etudiant)
    reponse = client.get(reverse("accounts:exporter"))

    assert reponse["Content-Disposition"].startswith("attachment")
    donnees = json.loads(reponse.content)
    assert donnees["compte"]["email"] == etudiant.email
    assert donnees["profil_etude"]["examen"] == "BTS"


def test_suppression_du_compte_exige_le_mot_de_passe(client, etudiant):
    client.force_login(etudiant)

    client.post(reverse("accounts:supprimer"), {"mot_de_passe": "faux"})
    assert Utilisateur.objects.filter(pk=etudiant.pk).exists()

    client.post(reverse("accounts:supprimer"), {"mot_de_passe": MOT_DE_PASSE})
    assert not Utilisateur.objects.filter(pk=etudiant.pk).exists()


def test_reinitialisation_du_mot_de_passe(client, etudiant):
    client.post(reverse("accounts:mot_de_passe_oublie"), {"email": "AWA@example.com"})

    assert len(mail.outbox) == 1
    assert "/compte/mot-de-passe/" in mail.outbox[0].body


def test_la_deconnexion_se_fait_en_post(client, etudiant):
    client.force_login(etudiant)
    assert client.get(reverse("accounts:deconnexion")).status_code == 405
    client.post(reverse("accounts:deconnexion"))
    assert client.get(reverse("accounts:profil")).status_code == 302


def test_bandeau_selon_la_connexion(client, etudiant):
    assert "Créer un compte" in client.get(reverse("accueil")).content.decode()
    client.force_login(etudiant)
    assert "Mon espace" in client.get(reverse("accueil")).content.decode()
