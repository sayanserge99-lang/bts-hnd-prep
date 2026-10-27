"""Avant le lancement : contact, plan du site, retrait hors ligne, recherche après renommage."""

import pytest
from django.core import mail
from django.urls import reverse

from accounts.models import Utilisateur
from communaute.models import MessageContact
from config import securite
from forum.models import Discussion
from sujets.models import Sujet

pytestmark = pytest.mark.django_db


# --- Contact -----------------------------------------------------------------------------------------------

def ecrire(client, **autres):
    donnees = {"nom": "Awa", "email": "awa@example.com", "objet": "question", "message": "Quand arrivent les sujets 2025 ?", **autres}
    return client.post(reverse("contact"), donnees)


def test_le_message_est_garde_et_l_equipe_prevenue(client, settings):
    settings.ADMINS = [("Équipe", "equipe@example.com")]
    assert "demande de retrait" in client.get(reverse("contact")).content.decode()  # la bonne procédure est indiquée
    reponse = ecrire(client)
    assert reponse.url == reverse("contact_envoye")
    message = MessageContact.objects.get()
    assert message.email == "awa@example.com" and not message.traite
    assert len(mail.outbox) == 1 and mail.outbox[0].to == ["equipe@example.com"]
    assert "Quand arrivent" in mail.outbox[0].body


def test_rien_n_est_envoye_a_l_adresse_saisie(client, settings):
    """Sinon n'importe qui ferait envoyer des e-mails par le site à n'importe quelle adresse."""
    settings.ADMINS = [("Équipe", "equipe@example.com")]
    ecrire(client, email="victime@example.com")
    assert all("victime@example.com" not in envoi.to for envoi in mail.outbox)


def test_un_robot_ne_laisse_rien(client):
    reponse = ecrire(client, site_web="http://pub.example")
    assert reponse.url == reverse("contact_envoye") and not MessageContact.objects.exists()


def test_messages_limites_par_jour(client):
    for _ in range(securite.CONTACTS_PAR_IP.maximum + 2):
        ecrire(client)
    assert MessageContact.objects.count() == securite.CONTACTS_PAR_IP.maximum


def test_message_trop_court(client):
    ecrire(client, message="Salut")
    assert not MessageContact.objects.exists()


def test_formulaire_prerempli_pour_un_inscrit(client):
    client.force_login(Utilisateur.objects.create_user(email="ben@example.com", password="Revision-2027", first_name="Ben", last_name="Mbia"))
    page = client.get(reverse("contact")).content.decode()
    assert 'value="ben@example.com"' in page and 'value="Ben Mbia"' in page


# --- Plan du site et robots ---------------------------------------------------------------------------------------

def test_robots_txt(client, settings):
    contenu = client.get("/robots.txt").content.decode()
    assert "Disallow: /compte/" in contenu and "Disallow: /paiement/" in contenu
    assert "Sitemap: http://testserver/sitemap.xml" in contenu
    assert settings.ADMIN_URL not in contenu  # l'adresse de l'administration n'est pas révélée


def test_le_plan_ne_contient_que_le_public(client, creer_sujet, session_terminee, session_en_cours, compta_generale):
    publie = creer_sujet(session_terminee, statut=Sujet.Statut.PUBLIE)
    brouillon = creer_sujet(session_en_cours)
    awa = Utilisateur.objects.create_user(email="awa@example.com", password="Revision-2027")
    visible = Discussion.objects.create(matiere=compta_generale, auteur=awa, titre="Q visible", texte="")
    masquee = Discussion.objects.create(matiere=compta_generale, auteur=awa, titre="Q masquée", texte="", masquee=True)

    contenu = client.get("/sitemap.xml").content.decode()

    assert f"/sujets/{publie.pk}/</loc>" in contenu and f"/sujets/{brouillon.pk}/</loc>" not in contenu
    assert f"/forum/discussion/{visible.pk}/</loc>" in contenu and f"/forum/discussion/{masquee.pk}/</loc>" not in contenu
    assert "/offres/</loc>" in contenu and "<lastmod>" in contenu


# --- Retrait hors ligne -------------------------------------------------------------------------------------------

def test_les_sujets_retires_sont_signales_aux_telephones(client, creer_sujet, session_terminee):
    publie = creer_sujet(session_terminee, statut=Sujet.Statut.PUBLIE)
    retire = creer_sujet(session_terminee, statut=Sujet.Statut.PUBLIE, type_epreuve=Sujet.TypeEpreuve.PRATIQUE)
    Sujet.objects.filter(pk=retire.pk).update(statut=Sujet.Statut.MASQUE)  # demande de retrait reçue

    reponse = client.get(reverse("sujets_retires"), {"ids": f"{publie.pk},{retire.pk},999999,abc"})

    assert reponse.json() == {"retires": sorted([retire.pk, 999999])}
    assert reponse["Cache-Control"] == "no-store"


def test_le_service_worker_efface_une_page_devenue_introuvable(client):
    assert "reponse.status === 404" in client.get(reverse("service_worker")).content.decode()


# --- Recherche après renommage d'une matière ----------------------------------------------------------------------

def test_renommer_une_matiere_met_a_jour_la_recherche(creer_sujet, session_terminee, compta_generale):
    sujet = creer_sujet(session_terminee, statut=Sujet.Statut.PUBLIE, titre="Épreuve 2025")
    assert not Sujet.objects.rechercher("financière", "fr").filter(pk=sujet.pk).exists()

    compta_generale.nom_fr = "Comptabilité financière"
    compta_generale.save()

    assert Sujet.objects.rechercher("financière", "fr").filter(pk=sujet.pk).exists()
