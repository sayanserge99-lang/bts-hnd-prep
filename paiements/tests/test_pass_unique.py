"""Un seul Pass par session, et l'accès Premium affiché en périodes continues."""

from datetime import timedelta

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from accounts.models import ProfilEtude, Utilisateur
from catalogue.models import Session
from paiements import codes
from paiements.models import Abonnement, Offre, Paiement
from paiements.tests.test_codes import partenariat, iai  # noqa: F401 (fixtures)
from paiements.tests.test_paiement import commander, notifier, paiement_ouvert  # noqa: F401 (fixtures)

pytestmark = pytest.mark.django_db


@pytest.fixture
def pass_session():
    return Offre.objects.create(nom="Pass session", prix=5000, type=Offre.Type.SESSION)


@pytest.fixture
def mensuel():
    return Offre.objects.create(nom="Premium 30 jours", prix=1500, type=Offre.Type.DUREE, duree_jours=30)


@pytest.fixture
def etudiant(comptabilite, session_en_cours):
    utilisateur = Utilisateur.objects.create_user(email="awa@example.com", password="Revision-2027", first_name="Awa")
    ProfilEtude.objects.create(utilisateur=utilisateur, examen=comptabilite.examen, specialite=comptabilite)
    return utilisateur


def acheter(client, etudiant, offre, **autres):
    client.force_login(etudiant)
    commander(client, offre, **autres)
    paiement = Paiement.objects.filter(utilisateur=etudiant).latest("cree_le")
    notifier(client, paiement)
    paiement.refresh_from_db()
    return paiement


def test_le_pass_finit_a_la_date_officielle_de_fin(client, paiement_ouvert, etudiant, pass_session, session_en_cours):
    acheter(client, etudiant, pass_session)
    assert Abonnement.objects.get(utilisateur=etudiant).fin == session_en_cours.date_fin_officielle


def test_un_pass_actif_ne_se_rachete_pas(client, paiement_ouvert, etudiant, pass_session, session_en_cours):
    # Sans le refus, le second achat vendrait en silence le Pass de cette session suivante.
    Session.objects.create(
        examen=session_en_cours.examen, annee=session_en_cours.annee + 1,
        date_debut=session_en_cours.date_fin_officielle + timedelta(days=300),
        date_fin_officielle=session_en_cours.date_fin_officielle + timedelta(days=330),
    )
    acheter(client, etudiant, pass_session)

    reponse = client.get(reverse("paiements:commander", args=[pass_session.pk]), follow=True)
    assert "Vous avez déjà le Pass session" in reponse.content.decode()
    commander(client, pass_session)
    assert Paiement.objects.filter(utilisateur=etudiant).count() == 1


def test_deux_paiements_du_meme_pass_lances_ensemble(client, paiement_ouvert, etudiant, pass_session, settings,
                                                    django_capture_on_commit_callbacks):
    """Deux appuis sur « Payer » : le second argent reçu n'ouvre rien de faux, il est signalé pour remboursement."""
    settings.ADMINS = [("Équipe", "equipe@example.com")]
    client.force_login(etudiant)
    commander(client, pass_session)
    commander(client, pass_session)
    premier, second = Paiement.objects.filter(utilisateur=etudiant).order_by("cree_le")

    notifier(client, premier)
    with django_capture_on_commit_callbacks(execute=True):
        reponse = notifier(client, second)

    assert reponse.status_code == 200
    second.refresh_from_db()
    assert second.statut == Paiement.Statut.REUSSI and second.motif_echec.startswith("À régulariser")
    assert Abonnement.objects.filter(utilisateur=etudiant).count() == 1
    assert any("à régulariser" in envoi.subject for envoi in mail.outbox)


def test_un_code_de_pass_n_est_pas_consomme_si_le_pass_est_deja_actif(client, paiement_ouvert, etudiant, pass_session, partenariat):
    acheter(client, etudiant, pass_session)
    code = codes.generer(partenariat, pass_session, 1)[0]

    with pytest.raises(codes.CodeRefuse, match="déjà le Pass"):
        codes.activer(etudiant, code.code)
    code.refresh_from_db()
    assert code.utilise_par is None


def test_le_mensuel_reste_cumulable(client, paiement_ouvert, etudiant, mensuel):
    acheter(client, etudiant, mensuel)
    acheter(client, etudiant, mensuel)
    assert Abonnement.objects.filter(utilisateur=etudiant).count() == 2


def test_achat_puis_code_forment_une_seule_periode(client, paiement_ouvert, etudiant, mensuel, partenariat):
    acheter(client, etudiant, mensuel)
    codes.activer(etudiant, codes.generer(partenariat, mensuel, 1)[0].code)

    periodes = Abonnement.periodes(etudiant)

    aujourd_hui = timezone.localdate()
    assert len(periodes) == 1
    assert periodes[0]["debut"] == aujourd_hui and periodes[0]["fin"] == aujourd_hui + timedelta(days=61)
    assert periodes[0]["origines"] == ["Premium 30 jours"]
    page = client.get(reverse("accounts:profil")).content.decode()
    assert page.count("Premium du ") == 1


def test_periodes_separees_par_un_trou(etudiant, mensuel):
    aujourd_hui = timezone.localdate()
    Abonnement.objects.create(utilisateur=etudiant, offre=mensuel, debut=aujourd_hui, fin=aujourd_hui + timedelta(days=5),
                              paiement=Paiement.objects.create(utilisateur=etudiant, offre=mensuel, montant=1500, operateur="mtn", reference="R1"))
    Abonnement.objects.create(utilisateur=etudiant, offre=mensuel, debut=aujourd_hui + timedelta(days=10),
                              fin=aujourd_hui + timedelta(days=20),
                              paiement=Paiement.objects.create(utilisateur=etudiant, offre=mensuel, montant=1500, operateur="mtn", reference="R2"))
    assert len(Abonnement.periodes(etudiant)) == 2


# --- Pass et mensuel se cumulent sans perte de jours (décision du 27/10) -----------------------------------

def test_un_mois_achete_pendant_un_pass_prolonge_sans_trou(client, paiement_ouvert, etudiant, pass_session, mensuel, session_en_cours):
    acheter(client, etudiant, pass_session)
    acheter(client, etudiant, mensuel, confirme="1")  # « Acheter quand même » (voir le test suivant)

    (periode,) = Abonnement.periodes(etudiant)
    fin_du_pass = session_en_cours.date_fin_officielle
    assert periode["debut"] == timezone.localdate()
    # Le mois commence au lendemain de la fin du Pass : 30 jours entiers, aucun jour perdu.
    assert periode["fin"] == fin_du_pass + timedelta(days=1 + 30)
    assert periode["origines"] == ["Pass session", "Premium 30 jours"]


def test_un_mois_pendant_un_pass_demande_confirmation_avant_tout_debit(client, paiement_ouvert, etudiant, pass_session, mensuel, session_en_cours):
    acheter(client, etudiant, pass_session)
    fin_du_pass = session_en_cours.date_fin_officielle
    adresse = reverse("paiements:commander", args=[mensuel.pk])
    attendu = (f"Votre Pass couvre déjà jusqu'au {fin_du_pass:%d/%m/%Y}. "
               f"Ce mois commencerait le {fin_du_pass + timedelta(days=1):%d/%m/%Y}, après la session.")

    page = client.get(adresse).content.decode()
    assert attendu in page.replace("&#x27;", "'")
    assert "Acheter quand même" in page and "Annuler" in page
    assert 'name="telephone"' not in page  # pas de formulaire de paiement avant la confirmation

    # Paiement envoyé sans la confirmation (formulaire forgé, ancien onglet) : rien n'est débité.
    reponse = commander(client, mensuel)
    assert "Acheter quand même" in reponse.content.decode()
    assert Paiement.objects.filter(utilisateur=etudiant, offre=mensuel).count() == 0

    # « Acheter quand même » : le formulaire apparaît, garde la confirmation, et le paiement part.
    page = client.get(adresse, {"confirme": "1"}).content.decode()
    assert 'name="telephone"' in page and 'name="confirme" value="1"' in page
    commander(client, mensuel, confirme="1")
    assert Paiement.objects.filter(utilisateur=etudiant, offre=mensuel).count() == 1


def test_sans_pass_le_mois_s_achete_sans_avertissement(client, paiement_ouvert, etudiant, mensuel):
    client.force_login(etudiant)
    assert "Acheter quand même" not in client.get(reverse("paiements:commander", args=[mensuel.pk])).content.decode()
    commander(client, mensuel)
    assert Paiement.objects.filter(utilisateur=etudiant).count() == 1


def test_un_pass_achete_pendant_un_mois_prend_la_suite_sans_trou(client, paiement_ouvert, etudiant, pass_session, mensuel, session_en_cours):
    # Cas courant : le mois se termine avant la fin officielle de la session.
    session_en_cours.date_fin_officielle = timezone.localdate() + timedelta(days=120)
    session_en_cours.save()
    acheter(client, etudiant, mensuel)
    acheter(client, etudiant, pass_session)

    mois, passe = Abonnement.objects.filter(utilisateur=etudiant).order_by("debut")
    assert mois.fin == timezone.localdate() + timedelta(days=30)  # le mois reste entier
    assert passe.debut == mois.fin + timedelta(days=1)  # le Pass commence le lendemain
    assert passe.fin == session_en_cours.date_fin_officielle  # et finit à la date officielle de fin
    (periode,) = Abonnement.periodes(etudiant)
    assert periode["debut"] == mois.debut and periode["fin"] == passe.fin


@pytest.mark.offres_de_lancement
def test_les_offres_de_lancement_existent():
    """Migration paiements 0005 : les deux offres validées le 27/10, sans passer par les données de démo."""
    assert Offre.objects.filter(nom="Pass session", type=Offre.Type.SESSION, prix=5000, active=True).count() == 1
    assert Offre.objects.filter(nom="Premium 30 jours", type=Offre.Type.DUREE, duree_jours=30, prix=1500, active=True).count() == 1


def test_pass_inutile_si_le_mois_couvre_deja_toute_la_session(client, paiement_ouvert, etudiant, pass_session, mensuel, session_en_cours):
    """Le mois dépasse la fin de la session : le Pass commencerait après elle ; refusé avec un message clair."""
    acheter(client, etudiant, mensuel)
    reponse = client.get(reverse("paiements:commander", args=[pass_session.pk]), follow=True)
    assert "couvre déjà toute la session" in reponse.content.decode()
    assert Abonnement.objects.filter(utilisateur=etudiant).count() == 1
