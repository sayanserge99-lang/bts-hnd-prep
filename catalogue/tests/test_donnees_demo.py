"""Données de démonstration : jamais en production, et tout le contenu d'activité marqué « [DÉMO] »."""

import pytest
from django.core.management import CommandError, call_command

from communaute.models import Contribution
from entrainement.models import Tentative

pytestmark = pytest.mark.django_db


def test_refusee_en_production(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError, match="Refusé"):
        call_command("donnees_demo")
    assert not Contribution.objects.exists()


def test_activite_de_demonstration(settings):
    settings.DEBUG = True
    call_command("donnees_demo", stdout=open("/dev/null", "w"))

    quiz_fini = Tentative.objects.get(quiz__isnull=False, fin__isnull=False)
    assert quiz_fini.quiz.titre.startswith("[DÉMO]") and quiz_fini.note == 15
    examen = Tentative.objects.get(examen_blanc__isnull=False)
    assert examen.fin is None and examen.examen_blanc.titre.startswith("[DÉMO]") and len(examen.reponses["brouillon"]) == 2
    contributions = Contribution.objects.filter(statut=Contribution.Statut.EN_ATTENTE)
    assert contributions.count() == 3 and all(c.commentaire.startswith("[DÉMO]") for c in contributions)
    assert contributions.filter(annee=2027).exists()  # session pas encore terminée

    # Relancer ne double rien.
    call_command("donnees_demo", stdout=open("/dev/null", "w"))
    assert Contribution.objects.count() == 3 and Tentative.objects.count() == 2
