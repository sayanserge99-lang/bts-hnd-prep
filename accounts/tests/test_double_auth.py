"""Double authentification de l'équipe : un mot de passe volé ne suffit plus pour entrer dans l'administration."""

import base64
import importlib
import re

import pytest
from django.urls import reverse

from accounts import double_auth
from accounts.models import DoubleAuthentification, ProfilEtude, Utilisateur

pytestmark = pytest.mark.django_db
MOT_DE_PASSE = "Bon-Secret-2027"


@pytest.fixture(autouse=True)
def double_auth_active(settings):
    settings.DOUBLE_AUTH_EQUIPE = True


@pytest.fixture
def admin_compte():
    return Utilisateur.objects.create_superuser(email="admin@example.com", password=MOT_DE_PASSE)


def code_du_moment(appareil):
    return double_auth.code(appareil.secret, double_auth.pas_actuel())


def activer(client, utilisateur):
    """Mise en place complète, comme le ferait la personne avec son téléphone ; renvoie l'appareil."""
    client.force_login(utilisateur)
    client.get(reverse("accounts:double_auth_configurer"))
    appareil = DoubleAuthentification.objects.get(utilisateur=utilisateur)
    page = client.post(reverse("accounts:double_auth_configurer"), {"code": code_du_moment(appareil)}).content.decode()
    appareil.refresh_from_db()
    return appareil, re.findall(r"<li>([0-9A-F]{4}-[0-9A-F]{4})</li>", page)


# --- L'algorithme ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("instant,attendu", [
    (59, "94287082"), (1111111109, "07081804"), (1111111111, "14050471"),
    (1234567890, "89005924"), (2000000000, "69279037"), (20000000000, "65353130"),
])
def test_valeurs_d_essai_de_la_rfc_6238(instant, attendu):
    secret = base64.b32encode(b"12345678901234567890").decode()
    assert double_auth.code(secret, instant // 30, chiffres=8) == attendu


def test_exigee_par_defaut():
    # La valeur du fichier de réglages, pas celle des tests (qui la coupent ailleurs) : jamais désactivée par mégarde.
    assert importlib.import_module("config.settings").DOUBLE_AUTH_EQUIPE is True


# --- Mise en place et utilisation -----------------------------------------------------------------------------------

def test_l_administration_exige_la_mise_en_place(client, admin_compte):
    client.force_login(admin_compte)
    reponse = client.get(reverse("admin:index"))
    assert reponse.status_code == 302 and reponse.url.startswith(reverse("accounts:double_auth_configurer"))

    page = client.get(reponse.url).content.decode()
    appareil = DoubleAuthentification.objects.get(utilisateur=admin_compte)
    assert "<svg" in page and appareil.secret[:4] in page and not appareil.active
    assert client.post(reverse("accounts:double_auth_configurer"), {"code": "000000"}).status_code == 200
    appareil.refresh_from_db()
    assert not appareil.active


def test_activation_puis_acces(client, admin_compte):
    appareil, codes = activer(client, admin_compte)
    assert appareil.active and len(codes) == 10
    assert all(code not in str(appareil.codes_secours) for code in codes)  # seules les empreintes sont gardées
    assert client.get(reverse("admin:index")).status_code == 200


def test_chaque_session_redemande_le_code_et_un_code_ne_sert_qu_une_fois(client, admin_compte):
    appareil, _ = activer(client, admin_compte)
    client.logout()
    client.force_login(admin_compte)
    reponse = client.get(reverse("admin:index"))
    assert reponse.url.startswith(reverse("accounts:double_auth"))

    # Le code déjà donné à l'activation ne repasse pas (rejeu d'un code intercepté).
    code = double_auth.code(appareil.secret, appareil.dernier_pas)
    client.post(reverse("accounts:double_auth"), {"code": code})
    assert client.get(reverse("admin:index")).status_code == 302

    appareil.dernier_pas -= 1  # simule le passage au code suivant de l'application
    appareil.save()
    client.post(reverse("accounts:double_auth"), {"code": double_auth.code(appareil.secret, appareil.dernier_pas + 1)})
    assert client.get(reverse("admin:index")).status_code == 200


def test_code_de_secours_a_usage_unique(client, admin_compte):
    _, codes = activer(client, admin_compte)
    for _ in range(2):
        client.logout()
        client.force_login(admin_compte)
        client.post(reverse("accounts:double_auth"), {"code": codes[0].lower()})
    # Second usage refusé : toujours bloqué.
    assert client.get(reverse("admin:index")).status_code == 302
    assert len(DoubleAuthentification.objects.get().codes_secours) == 9


def test_les_essais_sont_limites(client, admin_compte):
    appareil, _ = activer(client, admin_compte)
    client.logout()
    client.force_login(admin_compte)
    for _ in range(5):
        client.post(reverse("accounts:double_auth"), {"code": "123456"})
    page = client.post(reverse("accounts:double_auth"), {"code": double_auth.code(appareil.secret, double_auth.pas_actuel() + 1)}).content.decode()
    assert "Trop d&#x27;essais" in page or "Trop d'essais" in page
    assert client.get(reverse("admin:index")).status_code == 302


def test_pas_de_redirection_vers_un_autre_site(client, admin_compte):
    appareil, _ = activer(client, admin_compte)
    client.logout()
    client.force_login(admin_compte)
    reponse = client.post(
        reverse("accounts:double_auth") + "?next=https://pirate.example/",
        {"code": double_auth.code(appareil.secret, double_auth.pas_actuel() + 1), "next": "https://pirate.example/"},
    )
    assert reponse.url == reverse("admin:index")


def test_les_etudiants_ne_sont_pas_concernes(client, comptabilite):
    etudiant = Utilisateur.objects.create_user(email="awa@example.com", password=MOT_DE_PASSE)
    ProfilEtude.objects.create(utilisateur=etudiant, examen=comptabilite.examen, specialite=comptabilite)
    client.force_login(etudiant)
    assert client.get(reverse("accounts:profil")).status_code == 200
    assert client.get(reverse("accounts:double_auth_configurer")).status_code == 404
    assert not DoubleAuthentification.objects.exists()


def test_telephone_perdu_un_administrateur_reinitialise(client, admin_compte):
    appareil, _ = activer(client, admin_compte)
    fiche = client.get(reverse("admin:accounts_doubleauthentification_change", args=[appareil.pk])).content.decode()
    assert appareil.secret not in fiche  # le secret n'est jamais affiché

    autre = Utilisateur.objects.create_user(email="mod@example.com", password=MOT_DE_PASSE, is_staff=True)
    activer(client, autre)
    client.force_login(admin_compte)
    client.post(reverse("accounts:double_auth"), {"code": double_auth.code(appareil.secret, double_auth.pas_actuel() + 1)})
    client.post(reverse("admin:accounts_doubleauthentification_delete", args=[autre.double_auth.pk]), {"post": "yes"})

    client.force_login(autre)
    assert client.get(reverse("admin:index")).url.startswith(reverse("accounts:double_auth_configurer"))


def test_se_deconnecter_reste_possible(client, admin_compte):
    client.force_login(admin_compte)
    client.post(reverse("admin:logout"))
    assert "_auth_user_id" not in client.session
