"""Protections contre le piratage : essais de mot de passe, robots, inondation d'e-mails, en-têtes de sécurité."""

import re
from pathlib import Path

import pytest
from django.conf import settings
from django.core import mail
from django.urls import reverse

from accounts.models import Utilisateur
from config import securite

pytestmark = pytest.mark.django_db
MOT_DE_PASSE = "Bon-Secret-2027"


@pytest.fixture
def admin_compte():
    return Utilisateur.objects.create_superuser(email="admin@example.com", password=MOT_DE_PASSE)


def connexion_admin(client, email, mot_de_passe, ip="203.0.113.5"):
    return client.post(
        reverse("admin:login"), {"username": email, "password": mot_de_passe, "next": reverse("admin:index")}, REMOTE_ADDR=ip
    )


# --- Mots de passe devinés ------------------------------------------------------------------------------------------

def test_la_connexion_a_l_administration_est_limitee(client, admin_compte):
    """Le plus sensible : un compte administrateur publie les sujets."""
    for _ in range(settings.CONNEXION_ESSAIS_MAX):
        connexion_admin(client, "admin@example.com", "mauvais")
    # Même le bon mot de passe est refusé pendant le blocage : deviner ne sert à rien.
    reponse = connexion_admin(client, "admin@example.com", MOT_DE_PASSE)
    assert reponse.status_code == 200 and "Trop de tentatives" in reponse.content.decode()
    assert "_auth_user_id" not in client.session


def test_un_meme_mot_de_passe_essaye_sur_beaucoup_de_comptes_est_bloque(client, admin_compte):
    """Attaque « pulvérisation » : un mot de passe courant essayé sur des milliers d'adresses, depuis une machine."""
    for numero in range(securite.CONNEXION_PAR_IP.maximum):
        client.post(reverse("accounts:connexion"), {"username": f"victime{numero}@example.com", "password": "Cameroun2027"}, REMOTE_ADDR="198.51.100.7")
    reponse = connexion_admin(client, "admin@example.com", MOT_DE_PASSE, ip="198.51.100.7")
    assert "Trop de tentatives" in reponse.content.decode()
    # Une autre connexion (une autre adresse) n'est pas pénalisée.
    connexion_admin(client, "admin@example.com", MOT_DE_PASSE, ip="192.0.2.44")
    assert client.session.get("_auth_user_id") == str(admin_compte.pk)


# --- Robots et inondation -------------------------------------------------------------------------------------------

def test_creation_de_comptes_en_serie(client, comptabilite):
    for numero in range(securite.INSCRIPTIONS_PAR_IP.maximum + 2):
        client.post(reverse("accounts:inscription"), {
            "email": f"robot{numero}@example.com", "first_name": "Robot", "last_name": "Test",
            "password1": MOT_DE_PASSE, "password2": MOT_DE_PASSE, "specialite": comptabilite.pk,
            "langue": "fr", "accepte_conditions": "on", "examen": "BTS",
        }, REMOTE_ADDR="198.51.100.9")
        client.logout()
    assert Utilisateur.objects.filter(email__startswith="robot").count() == securite.INSCRIPTIONS_PAR_IP.maximum


def test_mot_de_passe_oublie_n_inonde_pas_une_boite_mail(client):
    Utilisateur.objects.create_user(email="awa@example.com", password=MOT_DE_PASSE)
    for _ in range(6):
        reponse = client.post(reverse("accounts:mot_de_passe_oublie"), {"email": "awa@example.com"})
        # Toujours la même réponse : rien n'indique qu'une limite est atteinte, ni si le compte existe.
        assert reponse.url == reverse("accounts:mot_de_passe_envoye")
    assert len(mail.outbox) == securite.REINITIALISATIONS_PAR_EMAIL.maximum


def test_signalements_de_corrige_limites(client, settings, creer_sujet, session_terminee):
    from sujets.models import Corrige, Sujet

    sujet = creer_sujet(session_terminee, statut=Sujet.Statut.PUBLIE)
    corrige = Corrige.objects.create(
        sujet=sujet, statut=Corrige.Statut.VERIFIE, publication=Corrige.Publication.PUBLIE,
        auteur="Équipe", titulaire_droits="Équipe", partie_gratuite="Début",
    )
    client.force_login(Utilisateur.objects.create_user(email="ben@example.com", password=MOT_DE_PASSE))
    for _ in range(securite.SIGNALEMENTS_CORRIGE_PAR_COMPTE.maximum + 3):
        client.post(reverse("sujets:signaler_corrige", args=[corrige.pk]), {"motif": "Erreur ligne 3 du corrigé"})
    assert corrige.signalements.count() == securite.SIGNALEMENTS_CORRIGE_PAR_COMPTE.maximum


# --- En-têtes et scripts ---------------------------------------------------------------------------------------------

def test_en_tetes_de_securite(client):
    reponse = client.get(reverse("accueil"))
    csp = reponse["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "'unsafe-inline'" not in csp.split("script-src")[1].split(";")[0]
    assert "object-src 'none'" in csp and "frame-ancestors 'none'" in csp and "base-uri 'self'" in csp
    assert "camera=()" in reponse["Permissions-Policy"]
    assert reponse["X-Frame-Options"] == "DENY"


def test_aucun_script_en_ligne_dans_les_gabarits():
    """La CSP interdit le JavaScript écrit dans les pages : ce test empêche d'en rajouter par mégarde."""
    racine = Path(settings.BASE_DIR) / "templates"
    fautes = []
    for gabarit in racine.rglob("*.html"):
        texte = gabarit.read_text(encoding="utf-8")
        for balise in re.findall(r"<script\b[^>]*>", texte):
            if "src=" not in balise and 'type="application/json"' not in balise:
                fautes.append(f"{gabarit.name} : {balise}")
        fautes += [f"{gabarit.name} : {attribut}" for attribut in re.findall(r"\son[a-z]+=\"", texte)]
        fautes += [f"{gabarit.name} : javascript:" for _ in re.findall(r"javascript:", texte)]
    assert not fautes, fautes


def test_le_service_worker_ne_garde_jamais_l_administration(client):
    contenu = client.get(reverse("service_worker")).content.decode()
    assert f'startsWith("/{settings.ADMIN_URL}")' in contenu


def test_la_mise_en_ligne_refuse_l_adresse_d_administration_par_defaut(settings):
    from django.core.checks import run_checks

    settings.ADMIN_URL = "admin/"
    assert "accounts.W001" in [alerte.id for alerte in run_checks(include_deployment_checks=True)]
    settings.ADMIN_URL = "gestion-7f3k/"
    assert "accounts.W001" not in [alerte.id for alerte in run_checks(include_deployment_checks=True)]
