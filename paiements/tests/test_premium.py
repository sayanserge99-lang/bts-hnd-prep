"""Premium (CDC 3.8, 7, 10.7) : une seule règle d'accès, page Offres aux prix TTC."""

from datetime import date, timedelta

import pytest
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse
from django.utils import timezone

from accounts.models import ProfilEtude, Utilisateur
from catalogue.models import Session
from communaute.models import Contribution
from entrainement import quiz
from entrainement.examen_blanc import peut_passer_un_examen
from entrainement.progression import voit_les_statistiques_completes
from paiements.acces import est_premium, lit_le_corrige_complet
from paiements.models import Abonnement, Offre

pytestmark = pytest.mark.django_db


@pytest.fixture
def etudiant(comptabilite):
    utilisateur = Utilisateur.objects.create_user(email="awa@example.com", password="Revision-2027")
    ProfilEtude.objects.create(utilisateur=utilisateur, examen=comptabilite.examen, specialite=comptabilite)
    return utilisateur


def abonner(utilisateur, compta_generale, comptabilite):
    """Abonnement le plus simple à créer : des jours offerts pour une contribution."""
    contribution = Contribution.objects.create(
        utilisateur=utilisateur, matiere=compta_generale, specialite=comptabilite, annee=2024, certifie_droits=True
    )
    return Abonnement.offrir_jours(utilisateur, 7, contribution)


# --- Une seule règle ------------------------------------------------------------------------------------

def test_paiement_ferme_tout_est_ouvert_aux_inscrits(settings, etudiant):
    settings.PAIEMENT_ACTIF = False
    assert est_premium(etudiant) and peut_passer_un_examen(etudiant) and voit_les_statistiques_completes(etudiant)
    assert quiz.quiz_restants_aujourd_hui(etudiant) is None
    assert not est_premium(AnonymousUser())
    assert lit_le_corrige_complet(AnonymousUser())  # le corrigé se lit sans compte d'ici là


def test_paiement_ouvert_le_premium_suit_l_abonnement(settings, etudiant, compta_generale, comptabilite):
    settings.PAIEMENT_ACTIF = True
    regles = (est_premium, peut_passer_un_examen, voit_les_statistiques_completes, lit_le_corrige_complet)
    assert not any(regle(etudiant) for regle in regles)
    assert quiz.quiz_restants_aujourd_hui(etudiant) == settings.QUIZ_GRATUITS_PAR_JOUR

    abonner(etudiant, compta_generale, comptabilite)
    assert all(regle(etudiant) for regle in regles)
    assert quiz.quiz_restants_aujourd_hui(etudiant) is None

    Abonnement.objects.update(fin=timezone.localdate() - timedelta(days=1))  # expiré
    assert not est_premium(etudiant)


def test_l_equipe_a_toujours_acces(settings):
    settings.PAIEMENT_ACTIF = True
    moderateur = Utilisateur.objects.create_user(email="mod@example.com", password="Moderation-2027", is_staff=True)
    assert est_premium(moderateur) and lit_le_corrige_complet(moderateur)


# --- Page Offres ---------------------------------------------------------------------------------------------

def test_la_page_offres_affiche_les_prix_ttc(client, bts):
    aujourd_hui = timezone.localdate()
    Session.objects.create(examen=bts, annee=aujourd_hui.year + 1, date_debut=aujourd_hui + timedelta(days=100), date_fin_officielle=date(aujourd_hui.year + 1, 6, 30))
    Offre.objects.create(nom="Pass session", prix=5000, type=Offre.Type.SESSION)
    Offre.objects.create(nom="Premium 30 jours", prix=1500, type=Offre.Type.DUREE, duree_jours=30)
    Offre.objects.create(nom="Ancienne offre", prix=900, type=Offre.Type.DUREE, duree_jours=7, active=False)

    contenu = client.get(reverse("offres")).content.decode()

    assert "5 000 FCFA" in contenu and "1 500 FCFA" in contenu and "TTC" in contenu
    assert f"jusqu'à la fin de la session {aujourd_hui.year + 1} (30/06/{aujourd_hui.year + 1})" in contenu
    assert "pendant 30 jours" in contenu
    assert "Ancienne offre" not in contenu
    assert "Phase de lancement" in contenu  # paiement fermé
    assert reverse("accounts:activer_code") in contenu
    # Les mêmes offres sur l'accueil, et le menu mène à la page.
    accueil = client.get(reverse("accueil")).content.decode()
    assert "5 000 FCFA" in accueil and f'href="{reverse("offres")}"' in accueil


def test_l_abonne_voit_jusqu_a_quand(client, etudiant, compta_generale, comptabilite):
    abonnement = abonner(etudiant, compta_generale, comptabilite)
    client.force_login(etudiant)
    assert f"actif jusqu'au {abonnement.fin:%d/%m/%Y}" in client.get(reverse("offres")).content.decode()


def test_le_prix_ne_se_coupe_pas():
    from paiements.templatetags.prix import fcfa

    assert fcfa(5000) == "5 000 FCFA" and fcfa(150) == "150 FCFA" and fcfa(1250000) == "1 250 000 FCFA"
