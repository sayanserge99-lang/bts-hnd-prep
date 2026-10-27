"""Fin des abonnements (CDC 3.8) : passage à « expiré » et rappel par e-mail avant la fin."""

from datetime import timedelta
from itertools import count

import pytest
from django.conf import settings as reglages
from django.core import mail
from django.utils import timezone

from accounts.models import Utilisateur
from config.celery import app
from paiements.models import Abonnement, Offre, Paiement
from paiements.tasks import suivre_les_abonnements

pytestmark = pytest.mark.django_db
NUMEROS = count(1)


@pytest.fixture(autouse=True)
def paiement_ouvert(settings):
    settings.PAIEMENT_ACTIF = True
    settings.SITE_URL = "https://bts-hnd-prep.example.com"


@pytest.fixture
def offre():
    return Offre.objects.create(nom="Premium 30 jours", prix=1500, type=Offre.Type.DUREE, duree_jours=30)


def abonnement(utilisateur, offre, debut, fin):
    paiement = Paiement.objects.create(
        utilisateur=utilisateur, offre=offre, montant=offre.prix, operateur="mtn", reference=f"R-{next(NUMEROS)}", statut="reussi",
    )
    return Abonnement.objects.create(utilisateur=utilisateur, offre=offre, debut=debut, fin=fin, paiement=paiement)


@pytest.fixture
def awa():
    return Utilisateur.objects.create_user(email="awa@example.com", password="Revision-2027", first_name="Awa")


def test_les_abonnements_finis_expirent(awa, offre):
    aujourd_hui = timezone.localdate()
    fini = abonnement(awa, offre, aujourd_hui - timedelta(days=31), aujourd_hui - timedelta(days=1))
    dernier_jour = abonnement(awa, offre, aujourd_hui - timedelta(days=29), aujourd_hui)

    suivre_les_abonnements()

    fini.refresh_from_db()
    dernier_jour.refresh_from_db()
    assert fini.statut == Abonnement.Statut.EXPIRE and dernier_jour.statut == Abonnement.Statut.ACTIF


def test_rappel_une_seule_fois_avant_la_fin(awa, offre):
    aujourd_hui = timezone.localdate()
    abonnement(awa, offre, aujourd_hui - timedelta(days=27), aujourd_hui + timedelta(days=2))
    abonnement(Utilisateur.objects.create_user(email="ben@example.com", password="x-Revision-2027"), offre,
               aujourd_hui, aujourd_hui + timedelta(days=20))  # encore loin de la fin

    suivre_les_abonnements()
    suivre_les_abonnements()  # le lendemain, ou une relance du worker : pas de second e-mail

    assert len(mail.outbox) == 1 and mail.outbox[0].to == ["awa@example.com"]
    assert (aujourd_hui + timedelta(days=2)).strftime("%d/%m/%Y") in mail.outbox[0].subject
    assert "https://bts-hnd-prep.example.com/offres/" in mail.outbox[0].body
    assert "conservés" in mail.outbox[0].body  # rassurant : rien n'est perdu à la fin


def test_pas_de_rappel_a_qui_a_deja_renouvele(awa, offre):
    aujourd_hui = timezone.localdate()
    actuel = abonnement(awa, offre, aujourd_hui - timedelta(days=28), aujourd_hui + timedelta(days=1))
    abonnement(awa, offre, actuel.fin + timedelta(days=1), actuel.fin + timedelta(days=31))
    suivre_les_abonnements()
    assert not mail.outbox


def test_pas_de_rappel_pour_des_jours_offerts(awa, compta_generale, comptabilite):
    from communaute.models import Contribution

    contribution = Contribution.objects.create(utilisateur=awa, matiere=compta_generale, specialite=comptabilite, annee=2024, certifie_droits=True)
    Abonnement.offrir_jours(awa, 2, contribution)
    suivre_les_abonnements()
    assert not mail.outbox


def test_pas_de_rappel_tant_que_le_paiement_est_ferme(settings, awa, offre):
    settings.PAIEMENT_ACTIF = False
    aujourd_hui = timezone.localdate()
    abonnement(awa, offre, aujourd_hui - timedelta(days=28), aujourd_hui + timedelta(days=1))
    suivre_les_abonnements()
    assert not mail.outbox


def test_le_rappel_parle_la_langue_de_l_etudiant(offre):
    john = Utilisateur.objects.create_user(email="john@example.com", password="Revision-2027", first_name="John", langue="en")
    aujourd_hui = timezone.localdate()
    abonnement(john, offre, aujourd_hui - timedelta(days=28), aujourd_hui + timedelta(days=1))
    suivre_les_abonnements()
    assert "Premium" in mail.outbox[0].subject and "se termine" not in mail.outbox[0].subject


def test_la_tache_est_programmee_chaque_matin():
    tache = reglages.CELERY_BEAT_SCHEDULE["suivre-les-abonnements"]
    assert tache["task"] in app.tasks  # le nom correspond bien à une tâche existante
    assert tache["schedule"].hour == {8}
