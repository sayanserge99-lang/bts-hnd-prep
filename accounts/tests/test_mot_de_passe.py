"""Changer son mot de passe, ou en définir un pour un compte créé avec Google."""

import pytest
from django.urls import reverse

from accounts.models import Utilisateur

pytestmark = pytest.mark.django_db

NOUVEAU = "Nouveau-Secret-2027"


def test_un_compte_google_definit_un_mot_de_passe(client):
    utilisateur = Utilisateur.objects.create_user(email="awa@example.com")
    utilisateur.set_unusable_password()
    utilisateur.save()
    client.force_login(utilisateur)
    assert "Définir un mot de passe" in client.get(reverse("accounts:profil")).content.decode()

    reponse = client.post(reverse("accounts:mot_de_passe"), {"new_password1": NOUVEAU, "new_password2": NOUVEAU})

    assert reponse.url == reverse("accounts:profil")
    utilisateur.refresh_from_db()
    assert utilisateur.check_password(NOUVEAU)
    # Toujours connecté après le changement, et la connexion par e-mail marche désormais.
    assert client.get(reverse("accounts:profil")).status_code == 200
    client.logout()
    assert client.login(email="awa@example.com", password=NOUVEAU)


def test_changer_exige_l_ancien_mot_de_passe(client):
    utilisateur = Utilisateur.objects.create_user(email="awa@example.com", password="Ancien-Secret-2027")
    client.force_login(utilisateur)
    assert "Changer mon mot de passe" in client.get(reverse("accounts:profil")).content.decode()

    client.post(reverse("accounts:mot_de_passe"), {"old_password": "faux", "new_password1": NOUVEAU, "new_password2": NOUVEAU})
    utilisateur.refresh_from_db()
    assert not utilisateur.check_password(NOUVEAU)

    client.post(reverse("accounts:mot_de_passe"), {"old_password": "Ancien-Secret-2027", "new_password1": NOUVEAU, "new_password2": NOUVEAU})
    utilisateur.refresh_from_db()
    assert utilisateur.check_password(NOUVEAU)


def test_un_mot_de_passe_trop_faible_est_refuse(client):
    utilisateur = Utilisateur.objects.create_user(email="awa@example.com")
    utilisateur.set_unusable_password()
    utilisateur.save()
    client.force_login(utilisateur)
    client.post(reverse("accounts:mot_de_passe"), {"new_password1": "1234", "new_password2": "1234"})
    utilisateur.refresh_from_db()
    assert not utilisateur.has_usable_password()


def test_la_page_exige_une_connexion(client):
    assert client.get(reverse("accounts:mot_de_passe")).status_code == 302
