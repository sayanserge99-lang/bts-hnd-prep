import pytest
from django.contrib.auth.models import Group, Permission

pytestmark = pytest.mark.django_db


def test_les_trois_roles_existent():
    assert set(Group.objects.values_list("name", flat=True)) >= {"Étudiant", "Modérateur", "Administrateur"}


def test_le_moderateur_ne_gere_pas_le_catalogue_ni_les_paiements():
    moderateur = Group.objects.get(name="Modérateur")
    codenames = set(moderateur.permissions.values_list("codename", flat=True))

    assert "change_sujet" in codenames
    assert "change_session" not in codenames
    assert not moderateur.permissions.filter(content_type__app_label="paiements").exists()


def test_l_administrateur_a_toutes_les_permissions():
    assert Group.objects.get(name="Administrateur").permissions.count() == Permission.objects.count()
