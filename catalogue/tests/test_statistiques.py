"""Statistiques du back-office (CDC 3.9) et compteur anonyme des consultations."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone

from accounts.models import Utilisateur
from catalogue.statistiques import tableau_de_bord
from communaute.models import DemandeRetrait
from paiements.models import Abonnement, CodeAcces, Offre, Paiement
from partenaires.models import Etablissement, Partenariat
from sujets.models import ConsultationJour, Sujet

pytestmark = pytest.mark.django_db


@pytest.fixture
def sujets(creer_sujet, session_terminee):
    return [
        creer_sujet(session_terminee, titre=f"Sujet {lettre}", statut=Sujet.Statut.PUBLIE, type_epreuve=type_epreuve)
        for lettre, type_epreuve in (("A", "ecrite"), ("B", "pratique"))
    ]


def etudiant(email, il_y_a_jours=0):
    utilisateur = Utilisateur.objects.create_user(email=email, password="Revision-2027")
    Utilisateur.objects.filter(pk=utilisateur.pk).update(date_joined=timezone.now() - timedelta(days=il_y_a_jours))
    return utilisateur


# --- Compteur de consultations ---------------------------------------------------------------

def test_les_consultations_sont_comptees_par_jour(client, sujets):
    sujet = sujets[0]
    client.get(reverse("sujets:detail", args=[sujet.pk]))
    client.get(reverse("sujets:detail", args=[sujet.pk]), {"onglet": "corrige"})
    client.get(reverse("sujets:pdf", args=[sujet.pk]))

    ligne = ConsultationJour.objects.get(sujet=sujet, jour=timezone.localdate())
    assert (ligne.fiches, ligne.pdf) == (2, 1)


def test_l_equipe_n_est_pas_comptee(admin_client, sujets):
    admin_client.get(reverse("sujets:detail", args=[sujets[0].pk]))
    assert not ConsultationJour.objects.exists()


def test_un_sujet_non_publie_n_est_pas_compte(client, creer_sujet, session_en_cours):
    brouillon = creer_sujet(session_en_cours)
    client.get(reverse("sujets:detail", args=[brouillon.pk]))
    assert not ConsultationJour.objects.exists()


# --- Indicateurs --------------------------------------------------------------------------------

def test_inscrits_et_nouveaux_compares_a_la_periode_precedente(sujets):
    etudiant("a@example.com", 2)
    etudiant("b@example.com", 10)
    etudiant("c@example.com", 45)  # période précédente
    etudiant("d@example.com", 200)

    stats = tableau_de_bord()

    assert stats["inscrits"] == 4
    assert stats["nouveaux"].valeur == 2
    assert stats["nouveaux"].precedente == 1
    assert stats["nouveaux"].evolution == 1


def test_classement_des_sujets_les_plus_consultes(sujets):
    aujourd_hui = timezone.localdate()
    a, b = sujets
    ConsultationJour.objects.create(sujet=a, jour=aujourd_hui, fiches=3, pdf=1)
    ConsultationJour.objects.create(sujet=b, jour=aujourd_hui, fiches=5, pdf=4)
    ConsultationJour.objects.create(sujet=a, jour=aujourd_hui - timedelta(days=60), fiches=100)  # hors période

    top = tableau_de_bord()["top"]

    assert [(ligne["sujet"], ligne["total"]) for ligne in top] == [(b, 9), (a, 4)]
    assert top[0]["part"] == 100


def test_elements_a_traiter(sujets):
    DemandeRetrait.objects.create(demandeur_nom="X", demandeur_email="x@example.com", sujet=sujets[0], motif="M")
    assert tableau_de_bord()["a_traiter"]["retraits"] == 1


def test_revenus_et_conversion_seulement_une_fois_le_paiement_ouvert(settings, sujets):
    assert tableau_de_bord()["revenus"] is None

    settings.PAIEMENT_ACTIF = True
    abonne = etudiant("abonne@example.com")
    etudiant("gratuit@example.com")
    offre = Offre.objects.create(nom="Pass", prix=5000, type=Offre.Type.SESSION)
    paiement = Paiement.objects.create(
        utilisateur=abonne, offre=offre, montant=5000, operateur="mtn", reference="REF-1",
        statut=Paiement.Statut.REUSSI, confirme_le=timezone.now(),
    )
    Abonnement.objects.create(
        utilisateur=abonne, offre=offre, paiement=paiement,
        debut=timezone.localdate(), fin=timezone.localdate() + timedelta(days=30),
    )

    revenus = tableau_de_bord()["revenus"]
    assert revenus == {"montant": 5000, "abonnes": 1, "conversion": 50.0}


# --- Accès ----------------------------------------------------------------------------------------

def test_page_des_statistiques_pour_l_administrateur(admin_client, sujets):
    reponse = admin_client.get(reverse("statistiques"))

    assert reponse.status_code == 200
    contenu = reponse.content.decode()
    assert "Sujets les plus consultés" in contenu
    assert "Le paiement n&#x27;est pas encore ouvert" in contenu or "Le paiement n'est pas encore ouvert" in contenu
    # Le lien apparaît dans l'en-tête de l'admin.
    assert reverse("statistiques") in admin_client.get(reverse("admin:index")).content.decode()


def test_un_moderateur_n_y_a_pas_acces(client):
    moderateur = etudiant("moderateur@example.com")
    moderateur.groups.add(Group.objects.get(name="Modérateur"))
    client.force_login(moderateur)

    assert client.get(reverse("statistiques")).status_code == 403
    assert reverse("statistiques") not in client.get(reverse("admin:index")).content.decode()


def test_un_visiteur_est_renvoye_vers_la_connexion(client):
    reponse = client.get(reverse("statistiques"))
    assert reponse.status_code == 302
    assert "/admin/login/" in reponse.url
