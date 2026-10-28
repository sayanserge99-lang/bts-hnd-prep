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
               "password1": MOT_DE_PASSE, "accepte_conditions": "on", "examen": "BTS", **champs}
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


def test_un_etudiant_bts_est_en_francais_meme_inscrit_depuis_l_interface_anglaise(client, comptabilite):
    client.cookies["django_language"] = "en"
    inscrire(client, comptabilite)
    assert Utilisateur.objects.get().langue == "fr"
    assert '<html lang="fr">' in client.get(reverse("accounts:profil")).content.decode()


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


# --- Examen préparé en deux cartes (maquette) --------------------------------------------------------------

@pytest.fixture
def software(db):
    from catalogue.models import Examen, Specialite

    hnd = Examen.objects.create(code="HND", nom="Higher National Diploma", langue="en")
    return Specialite.objects.create(examen=hnd, code="SWE", nom="Software Engineering", filiere="industrielle")


def test_les_deux_cartes_d_examen(client, comptabilite):
    page = client.get(reverse("accounts:inscription")).content.decode()
    assert 'name="examen" value="BTS"' in page and 'name="examen" value="HND"' in page
    assert "En français" in page and "In English" in page
    assert 'hx-get="/specialites/?valeur=pk"' in page


def test_une_specialite_d_un_autre_examen_est_refusee(client, comptabilite, software):
    reponse = inscrire(client, comptabilite, specialite=software.pk, examen="BTS")
    assert reponse.status_code == 200 and "n&#x27;appartient pas au BTS" in reponse.content.decode()
    assert not Utilisateur.objects.exists()
    assert inscrire(client, comptabilite, specialite=software.pk, examen="HND").status_code == 302


def test_la_liste_suit_l_examen_et_garde_le_choix(client, comptabilite, software):
    fragment = client.get(reverse("options_specialites"), {"examen": "HND", "valeur": "pk", "specialite": software.pk}).content.decode()
    assert f'value="{software.pk}" selected' in fragment and "Comptabilité" not in fragment


def test_un_etudiant_hnd_voit_l_anglais_par_defaut_et_garde_la_bascule(client, comptabilite, software):
    reponse = inscrire(client, comptabilite, specialite=software.pk, examen="HND")
    assert reponse.status_code == 302 and Utilisateur.objects.get().langue == "en"
    page = client.get(reverse("accounts:profil")).content.decode()
    assert '<html lang="en">' in page

    # La bascule reste disponible : un clic, et le français est gardé (cookie et compte).
    client.post(reverse("set_language"), {"language": "fr", "next": "/"})
    assert '<html lang="fr">' in client.get(reverse("accounts:profil")).content.decode()
    assert Utilisateur.objects.get().langue == "fr"
