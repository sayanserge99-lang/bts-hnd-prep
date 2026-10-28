"""Langue du compte : un étudiant HND voit l'anglais, un étudiant BTS le français ; la bascule reste prioritaire.
Les e-mails partent dans la langue du destinataire, quel que soit celui qui les déclenche."""

import pytest
from django.conf import settings
from django.core import mail
from django.urls import reverse
from django.utils import translation

from accounts.models import Utilisateur
from forum.models import Discussion
from forum.services import repondre
from paiements.models import Paiement
from paiements.tests.test_paiement import commander, etudiant, mensuel, notifier, paiement_ouvert  # noqa: F401 (fixtures)

pytestmark = pytest.mark.django_db


def test_nouvel_appareil_le_compte_hnd_s_affiche_en_anglais(client):
    utilisateur = Utilisateur.objects.create_user(email="ndi@example.com", password="Revision-HND-2027", langue="en")
    client.force_login(utilisateur)  # aucun cookie de langue : navigateur neuf

    reponse = client.get(reverse("accounts:profil"))

    assert '<html lang="en">' in reponse.content.decode()
    assert reponse.cookies[settings.LANGUAGE_COOKIE_NAME].value == "en"


def test_le_choix_fait_avec_la_bascule_reste_prioritaire(client):
    utilisateur = Utilisateur.objects.create_user(email="ndi@example.com", password="Revision-HND-2027", langue="en")
    client.force_login(utilisateur)
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = "fr"
    assert '<html lang="fr">' in client.get(reverse("accounts:profil")).content.decode()


def test_la_reponse_du_forum_part_dans_la_langue_de_celui_qui_a_pose_la_question(compta_generale):
    auteur = Utilisateur.objects.create_user(email="ndi@example.com", password="x", langue="en")
    repondant = Utilisateur.objects.create_user(email="awa@example.com", password="x", langue="fr")
    discussion = Discussion.objects.create(matiere=compta_generale, auteur=auteur, titre="Depreciation?")
    with translation.override("fr"):  # la requête de celui qui répond est en français
        repondre(discussion, repondant, "Voir le chapitre 3.")
    assert mail.outbox[0].subject == "New answer to your question"


def test_le_recu_part_dans_la_langue_de_l_etudiant(client, paiement_ouvert, etudiant, mensuel, django_capture_on_commit_callbacks):
    etudiant.langue = "en"
    etudiant.save(update_fields=["langue"])
    client.force_login(etudiant)
    commander(client, mensuel)
    client.logout()
    # La notification de l'agrégateur n'a ni cookie ni compte : la langue vient de l'étudiant.
    with django_capture_on_commit_callbacks(execute=True):
        notifier(client, Paiement.objects.get())
    assert mail.outbox[0].subject.startswith("Your BTS-HND Prep receipt no.")


def test_le_menu_du_haut_connecte_comme_la_maquette(client):
    """Connecté : « Tableau de bord » en premier et « Examens blancs » ; la page en cours est signalée."""
    menu = lambda page: page.split('aria-label="Navigation principale"')[1].split("</nav>")[0]  # noqa: E731
    visiteur = menu(client.get(reverse("sujets:liste")).content.decode())
    assert "Tableau de bord" not in visiteur and "Examens blancs" not in visiteur

    client.force_login(Utilisateur.objects.create_user(email="awa@example.com", password="x", langue="fr"))
    connecte = menu(client.get(reverse("entrainement:progression")).content.decode())
    assert connecte.index("Tableau de bord") < connecte.index("Sujets") < connecte.index("Examens blancs")
    assert f'href="{reverse("entrainement:progression")}" class="hover:text-vert aria-[current=page]:text-vert" aria-current="page"' in connecte
