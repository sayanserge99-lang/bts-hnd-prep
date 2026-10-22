"""CDC 7 : un modérateur n'agit que sur les matières qui lui sont attribuées."""

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import AffectationModerateur, Utilisateur
from catalogue.models import Matiere, SpecialiteMatiere
from communaute.models import DemandeRetrait
from sujets.models import Sujet

pytestmark = pytest.mark.django_db


@pytest.fixture
def marketing_fondamental(bts, marketing):
    matiere = Matiere.objects.create(examen=bts, nom="Marketing fondamental")
    SpecialiteMatiere.objects.create(specialite=marketing, matiere=matiere, coefficient=4)
    return matiere


@pytest.fixture
def moderateur(compta_generale):
    utilisateur = Utilisateur.objects.create_user(email="moderateur@example.com", password="Moderation-2027")
    utilisateur.groups.add(Group.objects.get(name="Modérateur"))
    AffectationModerateur.objects.create(moderateur=utilisateur, matiere=compta_generale)
    return utilisateur


@pytest.fixture
def sujets(creer_sujet, session_terminee, marketing_fondamental):
    sien = creer_sujet(session_terminee, titre="Sujet de comptabilité")
    autre = creer_sujet(session_terminee, titre="Sujet de marketing", matiere=marketing_fondamental)
    return sien, autre


def test_le_groupe_moderateur_ouvre_puis_referme_l_administration(moderateur):
    assert moderateur.is_staff
    moderateur.groups.clear()
    moderateur.refresh_from_db()
    assert not moderateur.is_staff


def test_la_liste_ne_montre_que_ses_matieres(client, moderateur, sujets):
    sien, autre = sujets
    client.force_login(moderateur)

    contenu = client.get(reverse("admin:sujets_sujet_changelist")).content.decode()

    assert sien.titre in contenu
    assert autre.titre not in contenu


def test_impossible_d_ouvrir_ou_de_modifier_un_sujet_d_une_autre_matiere(client, moderateur, sujets):
    _, autre = sujets
    client.force_login(moderateur)

    assert client.get(reverse("admin:sujets_sujet_change", args=[autre.pk])).status_code != 200
    client.post(reverse("admin:sujets_sujet_change", args=[autre.pk]), {"titre": "Modifié"})

    autre.refresh_from_db()
    assert autre.titre == "Sujet de marketing"


def test_l_action_publier_ignore_les_autres_matieres(client, moderateur, sujets):
    sien, autre = sujets
    client.force_login(moderateur)

    client.post(
        reverse("admin:sujets_sujet_changelist"),
        {"action": "publier", "_selected_action": [sien.pk, autre.pk]},
    )

    sien.refresh_from_db()
    autre.refresh_from_db()
    assert sien.statut == Sujet.Statut.PUBLIE
    assert autre.statut == Sujet.Statut.BROUILLON


def test_le_formulaire_ne_propose_que_ses_matieres(client, moderateur, compta_generale, marketing_fondamental):
    client.force_login(moderateur)
    formulaire = client.get(reverse("admin:sujets_sujet_add")).context["adminform"].form

    choix = list(formulaire.fields["matiere"].queryset)
    assert choix == [compta_generale]


def test_les_demandes_de_retrait_suivent_aussi_ses_matieres(client, moderateur, sujets):
    sien, autre = sujets
    for sujet in sujets:
        DemandeRetrait.objects.create(demandeur_nom="X", demandeur_email="x@example.com", sujet=sujet, motif="M")
    client.force_login(moderateur)

    contenu = client.get(reverse("admin:communaute_demanderetrait_changelist")).content.decode()

    assert sien.titre in contenu
    assert autre.titre not in contenu


def test_l_administrateur_voit_toutes_les_matieres(admin_client, sujets):
    contenu = admin_client.get(reverse("admin:sujets_sujet_changelist")).content.decode()
    assert all(sujet.titre in contenu for sujet in sujets)


def test_un_moderateur_sans_matiere_ne_voit_aucun_sujet(client, sujets):
    utilisateur = Utilisateur.objects.create_user(email="nouveau@example.com", password="Moderation-2027")
    utilisateur.groups.add(Group.objects.get(name="Modérateur"))
    client.force_login(utilisateur)

    contenu = client.get(reverse("admin:sujets_sujet_changelist")).content.decode()
    assert not any(sujet.titre in contenu for sujet in sujets)
