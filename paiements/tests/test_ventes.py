"""Page « Ventes » : revenus par mois et par offre, payeurs fidèles, à relancer, non renouvelés ; administrateur seul."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone

from accounts.models import Utilisateur
from paiements.models import Abonnement, Offre, Paiement
from paiements.templatetags.prix import fcfa
from paiements.ventes import debut_du_mois, tableau_des_ventes

pytestmark = pytest.mark.django_db


@pytest.fixture
def mensuel():
    return Offre.objects.create(nom="Premium 30 jours", prix=1500, type=Offre.Type.DUREE, duree_jours=30)


def payer(utilisateur, offre, montant, il_y_a=0, statut=Paiement.Statut.REUSSI, fin=None):
    numero = Paiement.objects.count() + 1
    quand = timezone.now() - timedelta(days=il_y_a)
    paiement = Paiement.objects.create(utilisateur=utilisateur, offre=offre, montant=montant, operateur="mtn",
                                       reference=f"R{numero}", statut=statut, confirme_le=quand)
    if statut == Paiement.Statut.REUSSI:
        debut = (quand - timedelta(days=1)).date()
        Abonnement.objects.create(utilisateur=utilisateur, offre=offre, paiement=paiement, debut=debut,
                                  fin=fin or debut + timedelta(days=30))
    return paiement


def etudiant(email, prenom):
    return Utilisateur.objects.create_user(email=email, password="Revision-2027", first_name=prenom)


def test_revenus_fideles_et_echecs(mensuel):
    awa, ben = etudiant("awa@example.com", "Awa"), etudiant("ben@example.com", "Ben")
    aujourd_hui = timezone.localdate()
    payer(awa, mensuel, 1500, il_y_a=40)
    payer(awa, mensuel, 1200)  # avec un code de réduction : seul le montant payé compte
    payer(ben, mensuel, 1500)
    payer(ben, mensuel, 1500, statut=Paiement.Statut.ECHOUE)

    ventes = tableau_des_ventes()
    assert ventes["mois"][-1]["mois"] == debut_du_mois(aujourd_hui)
    assert ventes["ca_mois"].valeur == sum(p.montant for p in Paiement.objects.filter(
        statut="reussi", confirme_le__date__gte=debut_du_mois(aujourd_hui)))
    assert ventes["ca_periode"] == 4200 and ventes["payeurs"] == 2 and ventes["fideles"] == 1
    assert ventes["renouvellement"] == 50 and ventes["echoues_30_jours"] == 1
    assert [(ligne["utilisateur__first_name"], ligne["total"]) for ligne in ventes["meilleurs"]] == [("Awa", 2700), ("Ben", 1500)]


def test_a_relancer_et_non_renouveles(mensuel):
    aujourd_hui = timezone.localdate()
    bientot, perdu, reparti = etudiant("a@example.com", "Bientôt"), etudiant("b@example.com", "Perdu"), etudiant("c@example.com", "Reparti")
    payer(bientot, mensuel, 1500, il_y_a=26, fin=aujourd_hui + timedelta(days=3))
    payer(perdu, mensuel, 1500, il_y_a=50, fin=aujourd_hui - timedelta(days=10))
    payer(reparti, mensuel, 1500, il_y_a=50, fin=aujourd_hui - timedelta(days=10))
    payer(reparti, mensuel, 1500)  # a repris un mois : ni perdu ni à relancer

    ventes = tableau_des_ventes()
    assert [a.utilisateur.first_name for a in ventes["a_relancer"]] == ["Bientôt"]
    assert [ligne["utilisateur__first_name"] for ligne in ventes["perdus"]] == ["Perdu"]


def test_page_reservee_a_l_administrateur(client, mensuel):
    payer(etudiant("awa@example.com", "Awa"), mensuel, 1500)
    moderateur = Utilisateur.objects.create_user(email="moderateur@example.com", password="Moderation-2027")
    moderateur.groups.add(Group.objects.get(name="Modérateur"))
    client.force_login(moderateur)
    assert client.get(reverse("ventes")).status_code == 403

    administrateur = Utilisateur.objects.create_user(email="admin@example.com", password="Admin-2027-xyz")
    administrateur.groups.add(Group.objects.get(name="Administrateur"))
    client.force_login(administrateur)
    page = client.get(reverse("ventes")).content.decode()
    assert "Awa" in page and fcfa(1500) in page and "jamais à exporter" in page
    assert reverse("ventes") in client.get(reverse("accounts:profil")).content.decode()
