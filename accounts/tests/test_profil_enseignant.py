"""CDC 11.1 : l'enseignant derrière chaque corrigé vérifié, affiché seulement avec son consentement."""

import io
import json

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from accounts.models import AffectationModerateur, Consentement, ProfilEnseignant, Utilisateur
from partenaires.models import Etablissement
from sujets.models import Corrige, Sujet

pytestmark = pytest.mark.django_db

MOT_DE_PASSE = "Enseignant-2027"


@pytest.fixture
def sujet(creer_sujet, session_terminee):
    return creer_sujet(session_terminee, statut=Sujet.Statut.PUBLIE)


@pytest.fixture
def enseignant(compta_generale):
    utilisateur = Utilisateur.objects.create_user(
        email="mbarga@example.com", password=MOT_DE_PASSE, first_name="Paul", last_name="Mbarga"
    )
    utilisateur.groups.add(Group.objects.get(name="Modérateur"))
    AffectationModerateur.objects.create(moderateur=utilisateur, matiere=compta_generale)
    profil = ProfilEnseignant.objects.create(
        utilisateur=utilisateur, etablissement=Etablissement.objects.create(nom="IAI-Cameroun", ville="Yaoundé"),
        affichage=ProfilEnseignant.Affichage.NOM,
    )
    profil.matieres.add(compta_generale)
    return utilisateur


@pytest.fixture
def corrige(sujet, enseignant):
    return Corrige.objects.create(
        sujet=sujet, statut=Corrige.Statut.VERIFIE, publication=Corrige.Publication.PUBLIE, auteur="Équipe",
        titulaire_droits="BTS-HND Prep", partie_gratuite="Exercice 1", verifie_par=enseignant,
    )


def consentir(utilisateur):
    Consentement.objects.create(utilisateur=utilisateur, objet=Consentement.Objet.PROFIL_ENSEIGNANT, version="1.0")


def onglet_corrige(client, sujet):
    return client.get(reverse("sujets:detail", args=[sujet.pk]), {"onglet": "corrige"}).content.decode()


def image(**exif):
    tampon = io.BytesIO()
    donnees = Image.new("RGB", (800, 600), "green").getexif()
    for cle, valeur in exif.items():
        donnees[int(cle)] = valeur
    Image.new("RGB", (800, 600), "green").save(tampon, "JPEG", exif=donnees)
    return SimpleUploadedFile("moi.jpg", tampon.getvalue(), content_type="image/jpeg")


# --- La carte sous le corrigé --------------------------------------------------------------------------------------

def test_pas_de_carte_sans_consentement(client, sujet, corrige):
    page = onglet_corrige(client, sujet)
    assert "Vérifié par un enseignant" in page
    assert "Mbarga" not in page and "IAI-Cameroun" not in page


def test_carte_complete_avec_consentement(client, sujet, corrige, enseignant):
    consentir(enseignant)
    page = onglet_corrige(client, sujet)
    assert "Vérifié par Paul Mbarga" in page
    assert "IAI-Cameroun" in page and "Comptabilité générale" in page and "1 corrigé vérifié" in page


def test_initiales_seules_quand_c_est_son_choix(client, sujet, corrige, enseignant):
    consentir(enseignant)
    ProfilEnseignant.objects.filter(utilisateur=enseignant).update(affichage=ProfilEnseignant.Affichage.INITIALES)
    page = onglet_corrige(client, sujet)
    assert "Vérifié par P. M." in page
    assert "Paul" not in page and "Mbarga" not in page


def test_le_retrait_s_applique_tout_de_suite(client, sujet, corrige, enseignant):
    client.force_login(enseignant)
    client.post(reverse("accounts:profil_enseignant"),
                {"affichage": "nom", "consentement": "on", "nouvelle_photo": image()})
    profil = ProfilEnseignant.objects.get(utilisateur=enseignant)
    photo = reverse("accounts:photo_enseignant", args=[profil.pk])
    client.logout()
    assert "Vérifié par Paul Mbarga" in onglet_corrige(client, sujet)
    assert client.get(photo).status_code == 200

    client.force_login(enseignant)
    client.post(reverse("accounts:retirer_profil_enseignant"))
    client.logout()

    page = onglet_corrige(client, sujet)
    assert "Mbarga" not in page and "Vérifié par un enseignant" in page
    assert client.get(photo).status_code == 404
    profil.refresh_from_db()
    assert not profil.photo and not profil.visible


def test_decocher_l_accord_retire_aussi_la_carte(client, sujet, corrige, enseignant):
    consentir(enseignant)
    client.force_login(enseignant)
    client.post(reverse("accounts:profil_enseignant"), {"affichage": "nom"})
    client.logout()
    assert "Mbarga" not in onglet_corrige(client, sujet)
    assert Consentement.objects.get(utilisateur=enseignant).date_revocation is not None


# --- La photo ------------------------------------------------------------------------------------------------------

def test_la_photo_est_recadree_sans_localisation_et_cachee_sans_accord(client, enseignant):
    client.force_login(enseignant)
    client.post(reverse("accounts:profil_enseignant"),
                {"affichage": "nom", "nouvelle_photo": image(**{"271": "Samsung", "306": "2026:10:29 10:00:00"})})
    profil = ProfilEnseignant.objects.get(utilisateur=enseignant)
    with profil.photo.open("rb") as fichier:
        photo = Image.open(fichier)
        photo.load()
    assert photo.size == (256, 256) and not photo.getexif()
    # L'enseignant voit sa photo ; les autres non, tant qu'il n'a pas donné son accord.
    adresse = reverse("accounts:photo_enseignant", args=[profil.pk])
    assert client.get(adresse).status_code == 200
    client.logout()
    assert client.get(adresse).status_code == 404


def test_un_fichier_qui_n_est_pas_une_image_est_refuse(client, enseignant):
    client.force_login(enseignant)
    faux = SimpleUploadedFile("moi.jpg", b"pas une image", content_type="image/jpeg")
    page = client.post(reverse("accounts:profil_enseignant"), {"affichage": "nom", "nouvelle_photo": faux})
    assert page.status_code == 200 and not ProfilEnseignant.objects.get(utilisateur=enseignant).photo


def test_la_page_est_reservee_aux_enseignants(client):
    client.force_login(Utilisateur.objects.create_user(email="awa@example.com", password=MOT_DE_PASSE))
    assert client.get(reverse("accounts:profil_enseignant")).status_code == 404


def test_l_export_contient_le_profil_enseignant(client, enseignant):
    client.force_login(enseignant)
    donnees = json.loads(client.get(reverse("accounts:exporter")).content)
    assert donnees["profil_enseignant"]["etablissement"].startswith("IAI-Cameroun")


# --- « Vérifié par » posé par l'administration ---------------------------------------------------------------------

def formulaire(corrige, **champs):
    return {
        "sujet": corrige.sujet_id, "partie_gratuite": corrige.partie_gratuite, "contenu": "", "statut": corrige.statut,
        "publication": corrige.publication, "auteur": corrige.auteur, "titulaire_droits": corrige.titulaire_droits,
        "regime_propriete": "", **champs,
    }


@pytest.fixture
def en_preparation(sujet):
    return Corrige.objects.create(
        sujet=sujet, auteur="Équipe", titulaire_droits="BTS-HND Prep", partie_gratuite="Exercice 1",
    )


def test_l_enseignant_qui_verifie_est_enregistre_automatiquement(client, en_preparation, enseignant):
    client.force_login(enseignant)
    adresse = reverse("admin:sujets_corrige_change", args=[en_preparation.pk])
    reponse = client.post(adresse, formulaire(en_preparation, statut="verifie"))
    assert reponse.status_code == 302
    en_preparation.refresh_from_db()
    assert en_preparation.verifie_par == enseignant and en_preparation.verifie_le is not None

    # Repassé en préparation : il n'est plus vérifié par personne.
    client.post(adresse, formulaire(en_preparation, statut="en_preparation"))
    en_preparation.refresh_from_db()
    assert en_preparation.verifie_par is None and en_preparation.verifie_le is None


def test_un_moderateur_sans_profil_enseignant_ne_peut_pas_marquer_verifie(client, en_preparation, compta_generale):
    moderateur = Utilisateur.objects.create_user(email="moderateur@example.com", password=MOT_DE_PASSE)
    moderateur.groups.add(Group.objects.get(name="Modérateur"))
    AffectationModerateur.objects.create(moderateur=moderateur, matiere=compta_generale)
    client.force_login(moderateur)
    reponse = client.post(reverse("admin:sujets_corrige_change", args=[en_preparation.pk]),
                          formulaire(en_preparation, statut="verifie"))
    assert reponse.status_code == 200 and "Seul un enseignant" in reponse.content.decode()
    en_preparation.refresh_from_db()
    assert en_preparation.statut == Corrige.Statut.EN_PREPARATION and en_preparation.verifie_par is None
