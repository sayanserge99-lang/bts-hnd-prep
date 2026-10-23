"""Espace établissement (CDC 10.6) : validation des étudiants, épreuves internes, résultats partagés."""

from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from accounts.models import Consentement, ProfilEtude, Utilisateur
from partenaires.models import EpreuveInterne, Etablissement, Partenariat, ResponsableEtablissement

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4 epreuve interne"


@pytest.fixture
def iai():
    return Etablissement.objects.create(nom="IAI-Cameroun", ville="Yaoundé", region="centre")


@pytest.fixture
def hintel():
    return Etablissement.objects.create(nom="HINTEL")


@pytest.fixture
def convention(iai):
    aujourd_hui = timezone.localdate()
    return Partenariat.objects.create(
        etablissement=iai, convention="conventions/iai.pdf", date_debut=aujourd_hui - timedelta(days=10),
        date_fin=aujourd_hui + timedelta(days=300), taux_partage=10, statut=Partenariat.Statut.ACTIF,
    )


@pytest.fixture
def responsable(iai):
    utilisateur = Utilisateur.objects.create_user(email="secretariat@iai.example.com", password="Responsable-2027")
    ResponsableEtablissement.objects.create(utilisateur=utilisateur, etablissement=iai)
    return utilisateur


def etudiant(email, specialite, etablissement, valide=False):
    utilisateur = Utilisateur.objects.create_user(email=email, password="Revision-2027", first_name=email.split("@")[0])
    ProfilEtude.objects.create(
        utilisateur=utilisateur, examen=specialite.examen, specialite=specialite, etablissement=etablissement,
        etablissement_valide_le=timezone.now() if valide else None,
    )
    return utilisateur


def epreuve(etablissement, publiee=True, titre="Partiel d'algorithmique"):
    return EpreuveInterne.objects.create(
        etablissement=etablissement, titre=titre, type="partiel", annee_academique="2025-2026", publiee=publiee,
        fichier=SimpleUploadedFile("partiel.pdf", PDF, content_type="application/pdf"),
    )


# --- Accès à l'espace ----------------------------------------------------------------------------

def test_l_espace_est_reserve_au_responsable(client, comptabilite, iai, responsable):
    assert client.get(reverse("partenaires:espace")).status_code == 302  # visiteur → connexion
    client.force_login(etudiant("awa@example.com", comptabilite, iai))
    assert client.get(reverse("partenaires:espace")).status_code == 403
    client.force_login(responsable)
    assert client.get(reverse("partenaires:espace")).status_code == 200
    assert reverse("partenaires:espace") in client.get(reverse("accueil")).content.decode()


# --- Validation des étudiants ---------------------------------------------------------------------

def test_le_responsable_confirme_ses_etudiants(client, comptabilite, iai, responsable):
    awa = etudiant("awa@example.com", comptabilite, iai)
    client.force_login(responsable)
    assert "awa@example.com" in client.get(reverse("partenaires:espace")).content.decode()

    client.post(reverse("partenaires:valider", args=[awa.profil.pk]))

    awa.profil.refresh_from_db()
    assert awa.profil.etablissement_valide
    assert awa.profil.etablissement_valide_par == responsable


def test_le_responsable_retire_un_faux_etudiant(client, comptabilite, iai, responsable):
    faux = etudiant("faux@example.com", comptabilite, iai)
    client.force_login(responsable)
    client.post(reverse("partenaires:retirer", args=[faux.profil.pk]))

    faux.profil.refresh_from_db()
    assert faux.profil.etablissement is None


def test_un_responsable_n_agit_que_sur_son_etablissement(client, comptabilite, hintel, responsable):
    autre = etudiant("ben@example.com", comptabilite, hintel)
    client.force_login(responsable)

    assert client.post(reverse("partenaires:valider", args=[autre.profil.pk])).status_code == 404
    assert "ben@example.com" not in client.get(reverse("partenaires:espace")).content.decode()


def test_changer_d_etablissement_annule_la_validation(comptabilite, iai, hintel):
    awa = etudiant("awa@example.com", comptabilite, iai, valide=True)
    profil = awa.profil
    profil.etablissement = hintel
    profil.save()

    profil.refresh_from_db()
    assert not profil.etablissement_valide


# --- Épreuves internes ------------------------------------------------------------------------------

def test_deposer_une_epreuve(client, iai, responsable, convention, compta_generale):
    client.force_login(responsable)
    client.post(reverse("partenaires:deposer"), {
        "titre": "Partiel d'algorithmique", "matiere": compta_generale.pk, "type": "partiel",
        "annee_academique": "2025-2026", "publiee": "on",
        "fichier": SimpleUploadedFile("partiel.pdf", PDF, content_type="application/pdf"),
    })

    depose = EpreuveInterne.objects.get()
    assert depose.etablissement == iai and depose.publiee and depose.deposee_par == responsable


def test_un_faux_pdf_est_refuse(client, responsable, convention):
    client.force_login(responsable)
    client.post(reverse("partenaires:deposer"), {
        "titre": "X", "type": "devoir", "annee_academique": "2025-2026",
        "fichier": SimpleUploadedFile("faux.pdf", b"<html>", content_type="application/pdf"),
    })
    assert not EpreuveInterne.objects.exists()


def test_pas_de_publication_sans_convention_active(client, responsable):
    client.force_login(responsable)
    client.post(reverse("partenaires:deposer"), {
        "titre": "X", "type": "devoir", "annee_academique": "2025-2026", "publiee": "on",
        "fichier": SimpleUploadedFile("partiel.pdf", PDF, content_type="application/pdf"),
    })
    assert not EpreuveInterne.objects.exists()

    brouillon = epreuve(responsable.responsable_de.etablissement, publiee=False)
    client.post(reverse("partenaires:publication", args=[brouillon.pk]))
    brouillon.refresh_from_db()
    assert not brouillon.publiee


def test_seuls_les_etudiants_valides_voient_les_epreuves(client, comptabilite, iai, convention):
    interne = epreuve(iai)
    url = reverse("partenaires:pdf_epreuve", args=[interne.pk])

    declare = etudiant("declare@example.com", comptabilite, iai)
    client.force_login(declare)
    assert interne.titre not in client.get(reverse("partenaires:mes_epreuves")).content.decode()
    assert client.get(url).status_code == 404

    valide = etudiant("valide@example.com", comptabilite, iai, valide=True)
    client.force_login(valide)
    assert "Partiel d" in client.get(reverse("partenaires:mes_epreuves")).content.decode()
    assert client.get(url).status_code == 200


def test_les_epreuves_d_un_autre_etablissement_restent_invisibles(client, comptabilite, iai, hintel, convention):
    interne = epreuve(iai)
    client.force_login(etudiant("ben@example.com", comptabilite, hintel, valide=True))
    assert client.get(reverse("partenaires:pdf_epreuve", args=[interne.pk])).status_code == 404


def test_une_epreuve_non_publiee_ou_sans_convention_est_invisible(client, comptabilite, iai, convention):
    brouillon = epreuve(iai, publiee=False)
    client.force_login(etudiant("valide@example.com", comptabilite, iai, valide=True))
    assert client.get(reverse("partenaires:pdf_epreuve", args=[brouillon.pk])).status_code == 404

    publiee = epreuve(iai, titre="Devoir 2")
    Partenariat.objects.update(statut=Partenariat.Statut.RESILIE)  # convention résiliée
    assert client.get(reverse("partenaires:pdf_epreuve", args=[publiee.pk])).status_code == 404


# --- Résultats partagés -------------------------------------------------------------------------------

def test_le_partage_des_resultats_est_desactive_par_defaut_et_revocable(client, comptabilite, iai, responsable):
    awa = etudiant("awa@example.com", comptabilite, iai, valide=True)
    client.force_login(responsable)
    assert "awa@example.com" not in client.get(reverse("partenaires:espace")).content.decode().split("Résultats partagés")[1]

    client.force_login(awa)
    client.post(reverse("accounts:partage"))
    assert Consentement.partage_actif(awa)
    client.force_login(responsable)
    assert "awa" in client.get(reverse("partenaires:espace")).content.decode().split("Résultats partagés")[1]

    client.force_login(awa)
    client.post(reverse("accounts:partage"))
    assert not Consentement.partage_actif(awa)
    # Le consentement reste tracé, avec sa date de révocation (CDC 10.2).
    assert Consentement.objects.filter(utilisateur=awa, date_revocation__isnull=False).count() == 1


def test_un_etudiant_non_valide_ne_partage_rien(client, comptabilite, iai, responsable):
    declare = etudiant("declare@example.com", comptabilite, iai)
    Consentement.objects.create(utilisateur=declare, objet=Consentement.Objet.PARTAGE_ETABLISSEMENT, version="1.0")
    client.force_login(responsable)
    resultats = client.get(reverse("partenaires:espace")).content.decode().split("Résultats partagés")[1]
    assert "declare" not in resultats


def test_mon_espace_montre_l_etat_de_validation(client, comptabilite, iai):
    awa = etudiant("awa@example.com", comptabilite, iai)
    client.force_login(awa)
    assert "en attente de validation" in client.get(reverse("accounts:profil")).content.decode()
    ProfilEtude.objects.filter(pk=awa.profil.pk).update(etablissement_valide_le=timezone.now())
    contenu = client.get(reverse("accounts:profil")).content.decode()
    assert "Épreuves de mon établissement" in contenu and "Partager mes résultats" in contenu
