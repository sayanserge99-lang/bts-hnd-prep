"""CDC 11.1 : codes de réduction (remise calculée par le serveur, plancher, réservation, une utilisation par étudiant)."""

import threading
import time
from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.db import connection
from django.urls import reverse
from django.utils import timezone

from accounts.models import ProfilEtude, Utilisateur
from paiements import reductions, service
from paiements.models import CodeReduction, Offre, Paiement, UtilisationCode
from paiements.templatetags.prix import fcfa
from paiements.tests.test_paiement import commander, etudiant, mensuel, notifier, paiement_ouvert  # noqa: F401
from partenaires.models import Etablissement

pytestmark = pytest.mark.django_db


@pytest.fixture
def code(mensuel):
    aujourd_hui = timezone.localdate()
    code = CodeReduction.objects.create(
        code="RENTREE27", type=CodeReduction.Type.POURCENTAGE, valeur=20,
        debut=aujourd_hui - timedelta(days=1), fin=aujourd_hui + timedelta(days=30),
    )
    code.offres.add(mensuel)
    return code


@pytest.fixture
def ben(comptabilite):
    utilisateur = Utilisateur.objects.create_user(email="ben@example.com", password="Revision-2027")
    ProfilEtude.objects.create(utilisateur=utilisateur, examen=comptabilite.examen, specialite=comptabilite)
    return utilisateur


def page(client, offre, saisie):
    return client.get(reverse("paiements:commander", args=[offre.pk]), {"code": saisie}).content.decode()


# --- Calcul -----------------------------------------------------------------------------------------------------------

def test_la_remise_respecte_le_plancher(settings):
    settings.PAIEMENT_PRIX_MINIMUM = 500
    pourcent = CodeReduction(type=CodeReduction.Type.POURCENTAGE, valeur=20)
    assert reductions.remise_pour(pourcent, 1500) == 300
    assert reductions.remise_pour(CodeReduction(type=CodeReduction.Type.POURCENTAGE, valeur=100), 1500) == 1000
    assert reductions.remise_pour(CodeReduction(type=CodeReduction.Type.MONTANT, valeur=2000), 5000) == 2000
    assert reductions.remise_pour(CodeReduction(type=CodeReduction.Type.MONTANT, valeur=2000), 1500) == 1000
    # Une offre déjà sous le plancher ne baisse pas.
    assert reductions.remise_pour(pourcent, 400) == 0


# --- Parcours ---------------------------------------------------------------------------------------------------------

def test_le_nouveau_prix_s_affiche_avant_de_payer_et_la_casse_ne_compte_pas(client, paiement_ouvert, etudiant, mensuel, code):
    client.force_login(etudiant)
    contenu = page(client, mensuel, " rentree27 ")
    assert f"Code RENTREE27 appliqué : {fcfa(300)} de remise." in contenu
    assert f'<s class="block text-sm text-gris">{fcfa(1500)}</s>' in contenu and f"Payer {fcfa(1200)}" in contenu


def test_le_code_n_est_compte_qu_au_succes(client, paiement_ouvert, etudiant, mensuel, code):
    client.force_login(etudiant)
    commander(client, mensuel, code="rentree27", montant="1")  # le navigateur n'impose ni montant ni remise
    paiement = Paiement.objects.get()
    assert (paiement.prix_initial, paiement.remise, paiement.montant) == (1500, 300, 1200)
    utilisation = UtilisationCode.objects.get()
    assert utilisation.paiement == paiement and utilisation.confirmee_le is None  # réservée seulement

    notifier(client, paiement)
    utilisation.refresh_from_db()
    assert utilisation.confirmee_le is not None
    recu = client.get(reverse("paiements:recu", args=[paiement.reference])).content.decode()
    assert fcfa(1500) in recu and fcfa(300) in recu and "RENTREE27" in recu and fcfa(1200) in recu


def test_un_paiement_echoue_ne_consomme_rien(client, paiement_ouvert, etudiant, mensuel, code):
    code.utilisations_max = 1
    code.save()
    client.force_login(etudiant)
    commander(client, mensuel, code="RENTREE27")
    notifier(client, Paiement.objects.get(), statut="echoue")
    assert not UtilisationCode.objects.exists()
    # Le même étudiant peut réessayer, et la seule utilisation est toujours disponible.
    assert "Code RENTREE27 appliqué" in page(client, mensuel, "RENTREE27")


def test_une_reservation_abandonnee_est_rendue_apres_le_delai(client, paiement_ouvert, etudiant, ben, mensuel, code, settings):
    code.utilisations_max = 1
    code.save()
    client.force_login(etudiant)
    commander(client, mensuel, code="RENTREE27")
    client.force_login(ben)
    assert "Ce code est épuisé" in page(client, mensuel, "RENTREE27")

    Paiement.objects.update(cree_le=timezone.now() - timedelta(minutes=settings.PAIEMENT_DELAI_MINUTES + 1))
    assert "Code RENTREE27 appliqué" in page(client, mensuel, "RENTREE27")
    assert Paiement.objects.get(utilisateur=etudiant).statut == Paiement.Statut.ECHOUE


# --- Refus ------------------------------------------------------------------------------------------------------------

def test_code_expire_ou_pas_encore_valable(client, paiement_ouvert, etudiant, mensuel, code):
    client.force_login(etudiant)
    hier = timezone.localdate() - timedelta(days=1)
    CodeReduction.objects.filter(pk=code.pk).update(debut=hier - timedelta(days=5), fin=hier)
    assert f"Ce code a expiré le {hier:%d/%m/%Y}." in page(client, mensuel, "RENTREE27")
    demain = timezone.localdate() + timedelta(days=1)
    CodeReduction.objects.filter(pk=code.pk).update(debut=demain, fin=demain)
    assert f"Ce code n&#x27;est valable qu&#x27;à partir du {demain:%d/%m/%Y}." in page(client, mensuel, "RENTREE27")


def test_code_epuise(client, paiement_ouvert, etudiant, ben, mensuel, code):
    code.utilisations_max = 1
    code.save()
    client.force_login(etudiant)
    commander(client, mensuel, code="RENTREE27")
    notifier(client, Paiement.objects.get(), statut="reussi")
    client.force_login(ben)
    assert "Ce code est épuisé" in page(client, mensuel, "RENTREE27")
    # Paiement forcé quand même : refusé, rien n'est créé.
    commander(client, mensuel, code="RENTREE27")
    assert Paiement.objects.filter(utilisateur=ben).count() == 0


def test_une_seule_utilisation_par_etudiant(client, paiement_ouvert, etudiant, mensuel, code):
    client.force_login(etudiant)
    commander(client, mensuel, code="RENTREE27")
    notifier(client, Paiement.objects.get())
    assert "Vous avez déjà utilisé ce code" in page(client, mensuel, "RENTREE27")


def test_mauvaise_offre_code_inconnu_ou_inactif(client, paiement_ouvert, etudiant, mensuel, code):
    autre = Offre.objects.create(nom="Premium 7 jours", prix=600, type=Offre.Type.DUREE, duree_jours=7)
    client.force_login(etudiant)
    assert "Ce code ne vaut pas pour l&#x27;offre « Premium 7 jours »." in page(client, autre, "RENTREE27")
    assert "Ce code de réduction n&#x27;existe pas" in page(client, mensuel, "INVENTE")
    CodeReduction.objects.filter(pk=code.pk).update(actif=False)
    assert "Ce code de réduction n&#x27;existe pas" in page(client, mensuel, "RENTREE27")


def test_code_reserve_aux_etudiants_confirmes_d_un_etablissement(client, paiement_ouvert, etudiant, mensuel, code):
    iai = Etablissement.objects.create(nom="IAI-Cameroun", ville="Yaoundé")
    CodeReduction.objects.filter(pk=code.pk).update(etablissement=iai)
    client.force_login(etudiant)
    assert "réservé aux étudiants confirmés par IAI-Cameroun" in page(client, mensuel, "RENTREE27")
    ProfilEtude.objects.filter(utilisateur=etudiant).update(etablissement=iai)  # déclaré, pas encore confirmé
    assert "réservé aux étudiants confirmés" in page(client, mensuel, "RENTREE27")
    ProfilEtude.objects.filter(utilisateur=etudiant).update(etablissement_valide_le=timezone.now())
    assert "Code RENTREE27 appliqué" in page(client, mensuel, "RENTREE27")


# --- Deux paiements simultanés sur la dernière utilisation -----------------------------------------------------------

@pytest.mark.django_db(transaction=True)
def test_deux_paiements_simultanes_ne_depassent_pas_la_limite(paiement_ouvert, etudiant, ben, mensuel, code, monkeypatch):
    code.utilisations_max = 1
    code.save()
    # Le comptage est ralenti : sans verrou, les deux commandes compteraient 0 utilisation en même temps.
    compter = reductions.places_prises
    monkeypatch.setattr(reductions, "places_prises", lambda c: (compter(c), time.sleep(0.5))[0])
    depart, resultats = threading.Barrier(2), []

    def payer(utilisateur):
        try:
            depart.wait()
            service.commander(utilisateur, mensuel, "mtn", "237677123456", None, code=code)
            resultats.append("payé")
        except reductions.CodeRefuse:
            resultats.append("refusé")
        finally:
            connection.close()

    fils = [threading.Thread(target=payer, args=(u,)) for u in (etudiant, ben)]
    for fil in fils:
        fil.start()
    for fil in fils:
        fil.join()

    assert sorted(resultats) == ["payé", "refusé"]
    assert UtilisationCode.objects.count() == 1 and Paiement.objects.count() == 1


# --- Administration ---------------------------------------------------------------------------------------------------

def test_seul_l_administrateur_gere_les_codes(client, code, compta_generale):
    moderateur = Utilisateur.objects.create_user(email="moderateur@example.com", password="Moderation-2027")
    moderateur.groups.add(Group.objects.get(name="Modérateur"))
    client.force_login(moderateur)
    assert client.get(reverse("admin:paiements_codereduction_changelist")).status_code == 403

    administrateur = Utilisateur.objects.create_user(email="admin@example.com", password="Admin-2027-xyz")
    administrateur.groups.add(Group.objects.get(name="Administrateur"))
    client.force_login(administrateur)
    liste = client.get(reverse("admin:paiements_codereduction_changelist")).content.decode()
    assert "RENTREE27" in liste and "0 / ∞" in liste
