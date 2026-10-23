"""Connexion avec Google (CDC 3.1, V2) : OpenID Connect, consentement jamais présumé."""

import base64
import json
import time
from urllib.parse import parse_qs, urlparse

import pytest
from django.urls import reverse

from accounts import google
from accounts.models import Consentement, Utilisateur

pytestmark = pytest.mark.django_db

CLIENT = "client-test.apps.googleusercontent.com"


@pytest.fixture(autouse=True)
def identifiants(settings):
    settings.GOOGLE_CLIENT_ID = CLIENT
    settings.GOOGLE_CLIENT_SECRET = "secret-test"


def jeton(**champs):
    """Faux jeton d'identité au format JWT (en-tête.contenu.signature)."""
    def encoder(donnees):
        return base64.urlsafe_b64encode(json.dumps(donnees).encode()).rstrip(b"=").decode()

    return f"{encoder({'alg': 'RS256'})}.{encoder(champs)}.signature"


def partir(client, suite=""):
    """Clic sur « Continuer avec Google » : renvoie l'état et le nonce envoyés à Google."""
    reponse = client.get(reverse("accounts:google"), {"next": suite} if suite else {})
    assert reponse.url.startswith(google.AUTORISATION)
    parametres = parse_qs(urlparse(reponse.url).query)
    return parametres["state"][0], parametres["nonce"][0]


def revenir(client, monkeypatch, etat, **identite):
    monkeypatch.setattr(google, "demander_jeton", lambda code, verificateur, adresse: {"id_token": jeton(**identite)})
    return client.get(reverse("accounts:google_retour"), {"state": etat, "code": "code-google"})


def identite_valide(nonce, **autres):
    return {
        "iss": "https://accounts.google.com", "aud": CLIENT, "exp": time.time() + 300, "nonce": nonce,
        "email": "Awa.Ngono@gmail.com", "email_verified": True, "given_name": "Awa", "family_name": "Ngono", **autres,
    }


def test_inactive_sans_identifiants(client, settings):
    settings.GOOGLE_CLIENT_ID = ""
    assert client.get(reverse("accounts:google")).status_code == 404
    assert "Continuer avec Google" not in client.get(reverse("accounts:connexion")).content.decode()


def test_le_bouton_apparait_une_fois_configure(client):
    assert "Continuer avec Google" in client.get(reverse("accounts:connexion")).content.decode()
    assert "Continuer avec Google" in client.get(reverse("accounts:inscription")).content.decode()


def test_la_demande_a_google_contient_les_protections(client):
    reponse = client.get(reverse("accounts:google"))
    parametres = parse_qs(urlparse(reponse.url).query)

    assert parametres["client_id"] == [CLIENT]
    assert parametres["scope"] == ["openid email profile"]
    assert parametres["code_challenge_method"] == ["S256"]
    assert parametres["redirect_uri"] == ["http://testserver/compte/google/retour/"]


def test_un_compte_existant_est_connecte(client, monkeypatch):
    Utilisateur.objects.create_user(email="awa.ngono@gmail.com", password="Revision-2027")
    etat, nonce = partir(client, suite="/entrainement/")

    reponse = revenir(client, monkeypatch, etat, **identite_valide(nonce))

    assert reponse.url == "/entrainement/"
    assert client.get(reverse("accounts:profil")).status_code == 200


def test_premiere_connexion_inscription_avec_consentement(client, monkeypatch, comptabilite):
    etat, nonce = partir(client)
    assert revenir(client, monkeypatch, etat, **identite_valide(nonce)).url == reverse("accounts:google_finir")

    page = client.get(reverse("accounts:google_finir")).content.decode()
    assert "awa.ngono@gmail.com" in page
    assert 'value="Awa"' in page

    # Sans la case cochée, rien n'est créé (CDC 10.2 : consentement jamais présumé).
    donnees = {"first_name": "Awa", "last_name": "Ngono", "langue": "fr", "specialite": comptabilite.pk}
    client.post(reverse("accounts:google_finir"), donnees)
    assert not Utilisateur.objects.exists()

    client.post(reverse("accounts:google_finir"), {**donnees, "accepte_conditions": "on"})
    utilisateur = Utilisateur.objects.get()
    assert utilisateur.email == "awa.ngono@gmail.com"
    assert not utilisateur.has_usable_password()
    assert utilisateur.groups.filter(name="Étudiant").exists()
    assert utilisateur.profil.specialite == comptabilite
    assert set(utilisateur.consentements.values_list("objet", flat=True)) == {
        Consentement.Objet.CGU, Consentement.Objet.CONFIDENTIALITE
    }


@pytest.mark.parametrize(
    "modification",
    [
        {"aud": "autre-site.apps.googleusercontent.com"},
        {"iss": "https://faux-google.example.com"},
        {"exp": time.time() - 10},
        {"nonce": "autre-nonce"},
        {"email_verified": False},
        {"email": ""},
    ],
)
def test_une_identite_douteuse_est_refusee(client, monkeypatch, modification):
    Utilisateur.objects.create_user(email="awa.ngono@gmail.com", password="Revision-2027")
    etat, nonce = partir(client)

    reponse = revenir(client, monkeypatch, etat, **{**identite_valide(nonce), **modification})

    assert reponse.url == reverse("accounts:connexion")
    assert client.get(reverse("accounts:profil")).status_code == 302  # personne n'est connecté


def test_un_lien_rejoue_ou_falsifie_est_refuse(client, monkeypatch):
    Utilisateur.objects.create_user(email="awa.ngono@gmail.com", password="Revision-2027")
    etat, nonce = partir(client)

    assert revenir(client, monkeypatch, "etat-falsifie", **identite_valide(nonce)).url == reverse("accounts:connexion")
    # L'état est à usage unique : même le bon ne sert plus après une tentative.
    assert revenir(client, monkeypatch, etat, **identite_valide(nonce)).url == reverse("accounts:connexion")


def test_pas_de_redirection_vers_un_site_tiers(client, monkeypatch):
    Utilisateur.objects.create_user(email="awa.ngono@gmail.com", password="Revision-2027")
    etat, nonce = partir(client, suite="https://site-pirate.example.com/")

    assert revenir(client, monkeypatch, etat, **identite_valide(nonce)).url == reverse("accounts:profil")


def test_un_compte_desactive_ne_se_connecte_pas(client, monkeypatch):
    Utilisateur.objects.create_user(email="awa.ngono@gmail.com", password="Revision-2027", is_active=False)
    etat, nonce = partir(client)

    assert revenir(client, monkeypatch, etat, **identite_valide(nonce)).url == reverse("accounts:connexion")


def test_on_ne_peut_pas_finir_une_inscription_sans_passer_par_google(client):
    assert client.get(reverse("accounts:google_finir")).url == reverse("accounts:inscription")


def test_un_compte_google_peut_supprimer_son_compte(client):
    utilisateur = Utilisateur(email="awa.ngono@gmail.com")
    utilisateur.set_unusable_password()
    utilisateur.save()
    client.force_login(utilisateur)

    client.post(reverse("accounts:supprimer"), {"mot_de_passe": "autre@gmail.com"})
    assert Utilisateur.objects.exists()
    client.post(reverse("accounts:supprimer"), {"mot_de_passe": "AWA.NGONO@gmail.com"})
    assert not Utilisateur.objects.exists()
