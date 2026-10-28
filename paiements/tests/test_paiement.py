"""Paiement Mobile Money (CDC 3.8, 10.4, 10.7) : commande, notification signée, abonnement, reçu."""

import json
from datetime import timedelta

import pytest
from django.core import mail
from django.core.checks import run_checks
from django.urls import reverse
from django.utils import timezone

from accounts.models import Consentement, ProfilEtude, Utilisateur
from paiements import service
from paiements.fournisseurs.base import signer
from paiements.models import Abonnement, Offre, Paiement

pytestmark = pytest.mark.django_db


@pytest.fixture
def paiement_ouvert(settings):
    settings.PAIEMENT_ACTIF = True
    settings.DEBUG = True  # agrégateur simulé
    settings.EXPLOITANT = {"structure": "BTS-HND Prep SARL", "niu": "M012345678901A", "adresse": "Yaoundé", "contact": ""}
    return settings


@pytest.fixture
def mensuel():
    return Offre.objects.create(nom="Premium 30 jours", prix=1500, type=Offre.Type.DUREE, duree_jours=30)


@pytest.fixture
def etudiant(comptabilite):
    utilisateur = Utilisateur.objects.create_user(email="awa@example.com", password="Revision-2027", first_name="Awa")
    ProfilEtude.objects.create(utilisateur=utilisateur, examen=comptabilite.examen, specialite=comptabilite)
    return utilisateur


def commander(client, offre, **autres):
    donnees = {"operateur": "mtn", "telephone": "6 77 12 34 56", "accepte": "on", **autres}
    return client.post(reverse("paiements:commander", args=[offre.pk]), donnees)


def notifier(client, paiement, statut="reussi", montant=None, signature=None):
    corps = json.dumps({"reference": paiement.reference, "statut": statut, "montant": montant or paiement.montant}).encode()
    return client.post(
        reverse("paiements:notification"), corps, content_type="application/json",
        HTTP_X_SIGNATURE=signature if signature is not None else signer(corps),
    )


# --- Commande ----------------------------------------------------------------------------------------------

def test_pas_de_paiement_sans_structure_ni_niu(client, etudiant, mensuel):
    """CDC 10.4 : paiement fermé tant que la structure et le NIU ne sont pas déclarés."""
    client.force_login(etudiant)
    assert client.get(reverse("paiements:commander", args=[mensuel.pk])).status_code == 404
    assert reverse("paiements:commander", args=[mensuel.pk]) not in client.get(reverse("offres")).content.decode()


def test_le_recapitulatif_montre_le_prix_ttc_et_les_dates(client, paiement_ouvert, etudiant, mensuel):
    client.force_login(etudiant)
    assert reverse("paiements:commander", args=[mensuel.pk]) in client.get(reverse("offres")).content.decode()
    page = client.get(reverse("paiements:commander", args=[mensuel.pk])).content.decode()
    aujourd_hui = timezone.localdate()
    assert "1 500 FCFA" in page and "TTC" in page
    assert f"du {aujourd_hui:%d/%m/%Y} au {aujourd_hui + timedelta(days=30):%d/%m/%Y}" in page


@pytest.mark.parametrize("saisie,attendu", [
    ("6 77 12 34 56", "237677123456"), ("+237 699-00-11-22", "237699001122"), ("237655443322", "237655443322"),
    ("0677123456", None), ("77 12 34 56", None), ("2 22 12 34 56", None),
])
def test_numero_mobile(saisie, attendu):
    assert service.normaliser_telephone(saisie) == attendu


def test_le_montant_vient_de_l_offre(client, paiement_ouvert, etudiant, mensuel):
    client.force_login(etudiant)
    reponse = commander(client, mensuel, montant="1")  # un navigateur trafiqué n'y change rien
    paiement = Paiement.objects.get()
    assert paiement.montant == 1500 and paiement.statut == Paiement.Statut.EN_ATTENTE and paiement.telephone == "237677123456"
    assert reponse.url == reverse("paiements:simulateur", args=[paiement.reference])
    # CDC 10.7 : conditions de vente acceptées et tracées.
    assert Consentement.objects.filter(utilisateur=etudiant, objet=Consentement.Objet.CONDITIONS_DE_VENTE).exists()


def test_les_conditions_de_vente_sont_obligatoires(client, paiement_ouvert, etudiant, mensuel):
    client.force_login(etudiant)
    commander(client, mensuel, accepte="")
    assert not Paiement.objects.exists()


# --- Parcours complet avec le simulateur ---------------------------------------------------------------------

def test_payer_ouvre_le_premium_et_envoie_le_recu(client, paiement_ouvert, etudiant, mensuel, django_capture_on_commit_callbacks):
    client.force_login(etudiant)
    commander(client, mensuel)
    paiement = Paiement.objects.get()
    assert "En attente de votre confirmation" in client.get(reverse("paiements:suivi", args=[paiement.reference])).content.decode()

    with django_capture_on_commit_callbacks(execute=True):
        client.post(reverse("paiements:simulateur", args=[paiement.reference]), {"choix": "valider"})

    paiement.refresh_from_db()
    abonnement = Abonnement.objects.get(paiement=paiement)
    assert paiement.statut == Paiement.Statut.REUSSI and paiement.confirme_le
    assert abonnement.debut == timezone.localdate() and abonnement.fin == timezone.localdate() + timedelta(days=30)
    assert "Paiement réussi" in client.get(reverse("paiements:suivi", args=[paiement.reference])).content.decode()

    # CDC 10.7 : reçu envoyé, et consultable dans le profil.
    assert len(mail.outbox) == 1 and paiement.numero_recu in mail.outbox[0].subject
    assert "NIU M012345678901A" in mail.outbox[0].body
    recu = client.get(reverse("paiements:recu", args=[paiement.reference])).content.decode()
    assert paiement.numero_recu in recu and "1 500 FCFA" in recu and "MTN MoMo" in recu
    assert reverse("paiements:recu", args=[paiement.reference]) in client.get(reverse("accounts:profil")).content.decode()


def test_un_refus_n_ouvre_rien(client, paiement_ouvert, etudiant, mensuel):
    client.force_login(etudiant)
    commander(client, mensuel)
    paiement = Paiement.objects.get()
    client.post(reverse("paiements:simulateur", args=[paiement.reference]), {"choix": "refuser"})
    paiement.refresh_from_db()
    assert paiement.statut == Paiement.Statut.ECHOUE and not Abonnement.objects.exists()
    assert client.get(reverse("paiements:recu", args=[paiement.reference])).status_code == 404
    assert "Paiement non abouti" in client.get(reverse("paiements:suivi", args=[paiement.reference])).content.decode()


# --- Notification de l'agrégateur -----------------------------------------------------------------------------

@pytest.fixture
def en_attente(paiement_ouvert, etudiant, mensuel):
    return Paiement.objects.create(utilisateur=etudiant, offre=mensuel, montant=1500, operateur="orange", reference="BHP-ESSAI1", fournisseur="simule")


def test_seule_une_notification_signee_compte(client, en_attente):
    assert notifier(client, en_attente, signature="fausse").status_code == 400
    en_attente.refresh_from_db()
    assert en_attente.statut == Paiement.Statut.EN_ATTENTE

    assert notifier(client, en_attente).status_code == 200
    en_attente.refresh_from_db()
    assert en_attente.statut == Paiement.Statut.REUSSI


def test_une_notification_repetee_ne_compte_qu_une_fois(client, en_attente):
    notifier(client, en_attente)
    notifier(client, en_attente)
    notifier(client, en_attente, statut="echoue")  # une notification tardive ne défait pas un paiement réussi
    en_attente.refresh_from_db()
    assert en_attente.statut == Paiement.Statut.REUSSI and Abonnement.objects.count() == 1


def test_un_montant_inattendu_n_ouvre_rien(client, en_attente):
    notifier(client, en_attente, montant=15)
    en_attente.refresh_from_db()
    assert en_attente.statut == Paiement.Statut.ECHOUE and "Montant reçu" in en_attente.motif_echec
    assert not Abonnement.objects.exists()


def test_reference_inconnue(client, en_attente):
    en_attente.reference = "BHP-INCONNUE"
    assert notifier(client, en_attente).status_code == 404


def test_un_paiement_oublie_est_abandonne(client, en_attente, etudiant):
    Paiement.objects.filter(pk=en_attente.pk).update(cree_le=timezone.now() - timedelta(minutes=31))
    client.force_login(etudiant)
    assert "Délai dépassé" in client.get(reverse("paiements:suivi", args=[en_attente.reference])).content.decode()


def test_un_paiement_n_est_visible_que_de_son_auteur(client, en_attente, comptabilite):
    autre = Utilisateur.objects.create_user(email="ben@example.com", password="Revision-2027")
    client.force_login(autre)
    assert client.get(reverse("paiements:suivi", args=[en_attente.reference])).status_code == 404
    assert client.get(reverse("paiements:simulateur", args=[en_attente.reference])).status_code == 404


def test_le_simulateur_n_existe_pas_en_production(client, en_attente, etudiant, settings):
    settings.DEBUG = False
    client.force_login(etudiant)
    assert client.get(reverse("paiements:simulateur", args=[en_attente.reference])).status_code == 404
    # Et le site refuse de démarrer avec le paiement ouvert sur l'agrégateur simulé.
    assert "paiements.E001" in [erreur.id for erreur in run_checks()]


def test_le_champ_telephone_affiche_l_indicatif_237(client, paiement_ouvert, etudiant, mensuel):
    """Maquette : « +237 » devant le champ ; le numéro saisi sans indicatif (ou avec) est accepté."""
    client.force_login(etudiant)
    page = client.get(reverse("paiements:commander", args=[mensuel.pk])).content.decode()
    assert 'class="avec-prefixe flex"' in page and ">+237</span>" in page
    commander(client, mensuel, telephone="677 12 34 56")
    assert Paiement.objects.get().telephone == "237677123456"
