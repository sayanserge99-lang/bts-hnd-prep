"""Codes d'accès prépayés (CDC 3.9) : génération, activation par l'étudiant, suivi par l'établissement."""

import re
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from accounts.models import ProfilEtude, Utilisateur
from catalogue.models import Session
from paiements import codes
from paiements.acces import lit_le_corrige_complet
from paiements.models import Abonnement, CodeAcces, Offre
from partenaires.models import Etablissement, Partenariat, ResponsableEtablissement

pytestmark = pytest.mark.django_db
FORMAT = re.compile(r"^[A-HJ-NP-Z2-9]{4}-[A-HJ-NP-Z2-9]{4}-[A-HJ-NP-Z2-9]{4}$")


@pytest.fixture
def iai():
    return Etablissement.objects.create(nom="IAI-Cameroun", ville="Yaoundé")


@pytest.fixture
def partenariat(iai):
    aujourd_hui = timezone.localdate()
    return Partenariat.objects.create(
        etablissement=iai, convention="conventions/iai.pdf", date_debut=aujourd_hui - timedelta(days=30),
        date_fin=aujourd_hui + timedelta(days=300), taux_partage=10, statut=Partenariat.Statut.ACTIF,
    )


@pytest.fixture
def mensuel():
    return Offre.objects.create(nom="Premium 30 jours", prix=1500, type=Offre.Type.DUREE, duree_jours=30)


@pytest.fixture
def etudiant(comptabilite):
    utilisateur = Utilisateur.objects.create_user(email="awa@example.com", password="Revision-2027")
    ProfilEtude.objects.create(utilisateur=utilisateur, examen=comptabilite.examen, specialite=comptabilite)
    return utilisateur


@pytest.fixture
def un_code(partenariat, mensuel):
    return codes.generer(partenariat, mensuel, 1)[0]


# --- Génération -------------------------------------------------------------------------------------------

def test_generer_des_codes_lisibles_et_uniques(partenariat, mensuel):
    lot = codes.generer(partenariat, mensuel, 50)
    assert len({code.code for code in lot}) == 50
    assert all(FORMAT.match(code.code) for code in lot)  # ni O, ni I, ni 0, ni 1


def test_pas_de_codes_sans_convention_active(partenariat, mensuel):
    Partenariat.objects.filter(pk=partenariat.pk).update(statut=Partenariat.Statut.RESILIE)
    partenariat.refresh_from_db()
    with pytest.raises(ValidationError):
        codes.generer(partenariat, mensuel, 5)
    assert not CodeAcces.objects.exists()


def test_generer_depuis_l_admin_telecharge_le_csv(client, partenariat, mensuel):
    client.force_login(Utilisateur.objects.create_superuser(email="admin@example.com", password="Administration-2027"))
    assert reverse("admin:paiements_codeacces_generer") in client.get(reverse("admin:paiements_codeacces_changelist")).content.decode()

    reponse = client.post(reverse("admin:paiements_codeacces_generer"), {"partenariat": partenariat.pk, "offre": mensuel.pk, "nombre": 3})

    assert reponse["Content-Type"].startswith("text/csv") and "attachment" in reponse["Content-Disposition"]
    lignes = reponse.content.decode("utf-8-sig").strip().splitlines()
    assert len(lignes) == 4 and all(code.code in reponse.content.decode() for code in CodeAcces.objects.all())


# --- Activation ---------------------------------------------------------------------------------------------

def test_activer_un_code(client, etudiant, un_code, iai):
    client.force_login(etudiant)
    saisie = un_code.code.lower().replace("-", " ")  # tapé à la main, en minuscules
    reponse = client.post(reverse("accounts:activer_code"), {"code": saisie})

    assert reponse.url == reverse("accounts:profil")
    abonnement = Abonnement.objects.get(utilisateur=etudiant)
    aujourd_hui = timezone.localdate()
    assert abonnement.code_acces == un_code and abonnement.debut == aujourd_hui and abonnement.fin == aujourd_hui + timedelta(days=30)
    un_code.refresh_from_db()
    assert un_code.utilise_par == etudiant and un_code.date_utilisation
    # Le code vient de l'établissement : l'étudiant y est rattaché et confirmé.
    etudiant.profil.refresh_from_db()
    assert etudiant.profil.etablissement == iai and etudiant.profil.etablissement_valide
    assert "Premium 30 jours" in client.get(reverse("accounts:profil")).content.decode()


def test_le_code_ouvre_le_premium(settings, etudiant, un_code):
    settings.PAIEMENT_ACTIF = True
    assert not lit_le_corrige_complet(etudiant)
    codes.activer(etudiant, un_code.code)
    assert lit_le_corrige_complet(etudiant)


def test_un_code_ne_sert_qu_une_fois(comptabilite, etudiant, un_code):
    codes.activer(etudiant, un_code.code)
    autre = Utilisateur.objects.create_user(email="ben@example.com", password="Revision-2027")
    ProfilEtude.objects.create(utilisateur=autre, examen=comptabilite.examen, specialite=comptabilite)
    with pytest.raises(codes.CodeRefuse, match="déjà été utilisé"):
        codes.activer(autre, un_code.code)
    assert Abonnement.objects.count() == 1


def test_codes_refuses(etudiant, un_code, partenariat):
    with pytest.raises(codes.CodeRefuse, match="n'existe pas"):
        codes.activer(etudiant, "AAAA-BBBB-CCCC")
    Partenariat.objects.filter(pk=partenariat.pk).update(statut=Partenariat.Statut.RESILIE)
    with pytest.raises(codes.CodeRefuse, match="convention"):
        codes.activer(etudiant, un_code.code)
    assert not Abonnement.objects.exists()


def test_les_essais_sont_limites(etudiant, un_code):
    for _ in range(codes.ESSAIS_PAR_HEURE):
        with pytest.raises(codes.CodeRefuse):
            codes.activer(etudiant, "AAAA-BBBB-CCCC")
    with pytest.raises(codes.CodeRefuse, match="Trop d'essais"):
        codes.activer(etudiant, un_code.code)  # même un bon code, le temps de la pause


def test_le_code_s_ajoute_a_l_abonnement_en_cours(etudiant, partenariat, mensuel):
    premier, second = codes.generer(partenariat, mensuel, 2)
    codes.activer(etudiant, premier.code)
    abonnement = codes.activer(etudiant, second.code)
    assert abonnement.debut == timezone.localdate() + timedelta(days=31)


def test_pass_session(etudiant, partenariat, bts):
    aujourd_hui = timezone.localdate()
    session = Session.objects.create(examen=bts, annee=aujourd_hui.year + 1, date_debut=aujourd_hui + timedelta(days=100), date_fin_officielle=aujourd_hui + timedelta(days=120))
    passe = Offre.objects.create(nom="Pass session", prix=5000, type=Offre.Type.SESSION)
    code = codes.generer(partenariat, passe, 1)[0]

    assert codes.activer(etudiant, code.code).fin == session.date_fin_officielle

    sans_profil = Utilisateur.objects.create_user(email="ben@example.com", password="Revision-2027")
    autre = codes.generer(partenariat, passe, 1)[0]
    with pytest.raises(codes.CodeRefuse, match="profil"):
        codes.activer(sans_profil, autre.code)


def test_un_autre_etablissement_declare_n_est_pas_change(etudiant, un_code):
    hintel = Etablissement.objects.create(nom="HINTEL")
    profil = etudiant.profil
    profil.etablissement = hintel
    profil.save()

    codes.activer(etudiant, un_code.code)

    profil.refresh_from_db()
    assert profil.etablissement == hintel and not profil.etablissement_valide


# --- Espace établissement --------------------------------------------------------------------------------------

def test_le_responsable_suit_ses_codes_sans_savoir_qui_les_a_utilises(client, iai, etudiant, partenariat, mensuel):
    premier, *_ = codes.generer(partenariat, mensuel, 3)
    codes.activer(etudiant, premier.code)
    autre_partenariat = Partenariat.objects.create(
        etablissement=Etablissement.objects.create(nom="HINTEL"), convention="c.pdf", date_debut=partenariat.date_debut,
        date_fin=partenariat.date_fin, taux_partage=10, statut=Partenariat.Statut.ACTIF,
    )
    etranger = codes.generer(autre_partenariat, mensuel, 1)[0]
    responsable = Utilisateur.objects.create_user(email="secretariat@iai.example.com", password="Responsable-2027")
    ResponsableEtablissement.objects.create(utilisateur=responsable, etablissement=iai)
    client.force_login(responsable)

    page = client.get(reverse("partenaires:espace")).content.decode()
    assert "1 utilisé(s) sur 3" in page

    contenu = client.get(reverse("partenaires:codes_restants")).content.decode("utf-8-sig")
    restants = [code.code for code in CodeAcces.objects.filter(partenariat=partenariat, utilise_par__isnull=True)]
    assert all(code in contenu for code in restants)
    assert premier.code not in contenu and etranger.code not in contenu and etudiant.email not in contenu

    client.force_login(etudiant)
    assert client.get(reverse("partenaires:codes_restants")).status_code == 403
