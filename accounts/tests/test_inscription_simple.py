"""Inscription en un seul mot de passe (maquette) et réinitialisation par e-mail de bout en bout."""

import re

import pytest
from django.contrib.auth import authenticate
from django.core import mail
from django.urls import reverse

from accounts.models import Utilisateur

pytestmark = pytest.mark.django_db

MOT_DE_PASSE = "Revision-BTS-2027"


def inscrire(client, comptabilite, **champs):
    donnees = {"first_name": "Awa", "last_name": "Ngono", "email": "awa@example.com", "specialite": comptabilite.pk,
               "password1": MOT_DE_PASSE, "accepte_conditions": "on", **champs}
    return client.post(reverse("accounts:inscription"), donnees)


def test_un_seul_champ_de_mot_de_passe_avec_son_oeil(client):
    page = client.get(reverse("accounts:inscription")).content.decode()
    assert 'name="password1"' in page and 'name="password2"' not in page
    assert 'aria-label="Afficher le mot de passe"' in page
    assert "8 caractères au minimum." in page
    assert 'name="langue"' not in page
    assert "Établissement" in page and "(facultatif)" in page and "Choisir dans la liste" in page
    assert " :</label>" not in page  # libellés sans deux-points


def test_inscription_sans_confirmation(client, comptabilite):
    reponse = inscrire(client, comptabilite)
    assert reponse.status_code == 302
    assert authenticate(email="awa@example.com", password=MOT_DE_PASSE)


@pytest.mark.parametrize("faible", ["12345678", "court", "awa@example.com", "motdepasse"])
def test_un_mot_de_passe_faible_reste_refuse(client, comptabilite, faible):
    """Sans le champ de confirmation, Django ne vérifiait plus rien : le formulaire contrôle le seul champ."""
    reponse = inscrire(client, comptabilite, password1=faible)
    assert reponse.status_code == 200 and not Utilisateur.objects.exists()


def test_la_langue_est_celle_de_l_interface(client, comptabilite):
    client.cookies["django_language"] = "en"
    inscrire(client, comptabilite)
    assert Utilisateur.objects.get().langue == "en"


def test_reinitialisation_de_bout_en_bout(client, comptabilite):
    inscrire(client, comptabilite)
    client.post(reverse("accounts:deconnexion"))
    mail.outbox.clear()

    client.post(reverse("accounts:mot_de_passe_oublie"), {"email": "Awa@Example.com"})
    assert len(mail.outbox) == 1 and mail.outbox[0].to == ["awa@example.com"]
    lien = re.search(r"https?://[^/\s]+(/compte/mot-de-passe/\S+)", mail.outbox[0].body).group(1)

    # Django remplace le jeton du lien par une adresse de session : on suit la redirection.
    formulaire = client.get(lien, follow=True)
    assert formulaire.status_code == 200 and 'name="new_password1"' in formulaire.content.decode()
    adresse = formulaire.redirect_chain[-1][0]
    nouveau = "Nouveau-Secret-2028"
    reponse = client.post(adresse, {"new_password1": nouveau, "new_password2": nouveau})

    assert reponse.status_code == 302 and reponse.url == reverse("accounts:connexion")
    assert authenticate(email="awa@example.com", password=nouveau)
    assert not authenticate(email="awa@example.com", password=MOT_DE_PASSE)
    # Le lien ne sert qu'une fois.
    assert 'name="new_password1"' not in client.get(lien, follow=True).content.decode()
