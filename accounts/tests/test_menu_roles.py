"""Le menu suit le rôle : l'équipe (administration, modération, établissement, enseignant) n'a pas le menu de
l'étudiant ; un compte qui a aussi un profil d'étude garde le menu de l'étudiant."""

import re

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import ProfilEnseignant, ProfilEtude, Utilisateur
from partenaires.models import Etablissement, ResponsableEtablissement
from sujets.models import Corrige, Sujet

pytestmark = pytest.mark.django_db

MENU_ETUDIANT = {"Tableau de bord", "Entraînement", "Examens blancs", "Offres"}


def compte(email, groupe=None):
    utilisateur = Utilisateur.objects.create_user(email=email, password="Equipe-2027-xyz")
    if groupe:
        utilisateur.groups.add(Group.objects.get(name=groupe))
    return utilisateur


def menus(client, utilisateur):
    client.force_login(utilisateur)
    page = client.get(reverse("accounts:profil")).content.decode()
    haut = re.search(r"Navigation principale.*?</nav>", page, re.S).group(0)
    bas = re.search(r"Navigation mobile.*?</nav>", page, re.S).group(0)
    return (set(re.findall(r">\s*([^<>]{3,40}?)\s*</a>", haut)),
            [texte.strip() for texte in re.findall(r"</svg>\s*([^<]+?)\s*</", bas)], page)


def test_administrateur(client):
    haut, bas, page = menus(client, compte("admin@example.com", "Administrateur"))
    assert {"Administration", "Statistiques", "Sujets"} <= haut and not haut & MENU_ETUDIANT
    assert bas == ["Accueil", "Sujets", "Administration", "Compte"]
    assert "Mon compte" in page and "Mes favoris" not in page and "Abonnement" not in page


def test_moderateur(client):
    haut, bas, _ = menus(client, compte("moderateur@example.com", "Modérateur"))
    assert "Modération" in haut and "Statistiques" not in haut and not haut & MENU_ETUDIANT
    assert bas[2] == "Modération"


def test_responsable_d_etablissement(client):
    responsable = compte("responsable@example.com")
    ResponsableEtablissement.objects.create(utilisateur=responsable, etablissement=Etablissement.objects.create(nom="IAI-Cameroun"))
    haut, bas, page = menus(client, responsable)
    assert "Mon établissement" in haut and not haut & MENU_ETUDIANT
    assert bas[2] == "Établissement"
    assert "Partager mes résultats" not in page


def test_enseignant_et_ses_corriges(client, creer_sujet, session_terminee, compta_generale):
    enseignant = compte("mbarga@example.com", "Modérateur")
    ProfilEnseignant.objects.create(utilisateur=enseignant).matieres.add(compta_generale)
    sujet = creer_sujet(session_terminee, statut=Sujet.Statut.PUBLIE)
    Corrige.objects.create(sujet=sujet, auteur="Awa (communauté)", titulaire_droits="Awa", partie_gratuite="Exercice 1",
                           statut=Corrige.Statut.COMMUNAUTE)
    haut, bas, _ = menus(client, enseignant)
    assert "Mes corrigés" in haut and bas[2] == "Mes corrigés" and not haut & MENU_ETUDIANT
    page = client.get(reverse("accounts:mes_corriges")).content.decode()
    assert "Awa (communauté)" in page and "Relire et vérifier" in page


def test_etudiant_et_visiteur_gardent_le_menu_de_l_etudiant(client, comptabilite):
    etudiant = compte("awa@example.com")
    ProfilEtude.objects.create(utilisateur=etudiant, examen=comptabilite.examen, specialite=comptabilite)
    haut, bas, page = menus(client, etudiant)
    assert MENU_ETUDIANT <= haut and "Administration" not in haut
    assert bas == ["Accueil", "Sujets", "Entraînement", "Profil"] and "Mon espace" in page
    client.logout()
    assert "Entraînement" in client.get(reverse("accueil")).content.decode()


def test_un_membre_de_l_equipe_qui_etudie_garde_le_menu_de_l_etudiant(client, comptabilite):
    administrateur = compte("serge@example.com", "Administrateur")
    ProfilEtude.objects.create(utilisateur=administrateur, examen=comptabilite.examen, specialite=comptabilite)
    haut, _, _ = menus(client, administrateur)
    assert MENU_ETUDIANT <= haut


def test_l_equipe_peut_encore_essayer_les_quiz(client):
    _, _, page = menus(client, compte("admin@example.com", "Administrateur"))
    assert "Voir comme un étudiant" in page
    assert client.get(reverse("entrainement:accueil")).status_code == 200
