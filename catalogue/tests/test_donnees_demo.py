"""Données de démonstration : jamais en production, et tout le contenu d'activité marqué « [DÉMO] »."""

import pytest
from django.core.management import CommandError, call_command

from communaute.models import Contribution
from entrainement.models import ExamenBlanc, Tentative

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
    court = ExamenBlanc.objects.get(titre="[DÉMO] Examen court")
    assert court.duree == 5 and court.publie and court.questions.count() == 3

    # Relancer ne double rien.
    call_command("donnees_demo", stdout=open("/dev/null", "w"))
    assert Contribution.objects.count() == 3 and Tentative.objects.count() == 2
    assert ExamenBlanc.objects.filter(titre="[DÉMO] Examen court").count() == 1


def test_les_sujets_de_demo_contiennent_une_epreuve_provisoire_lisible(settings):
    """Chaque sujet publié de démonstration a une vraie épreuve d'entraînement, annoncée comme provisoire."""
    from pypdf import PdfReader
    from sujets.models import Sujet

    settings.DEBUG = True
    call_command("donnees_demo", stdout=open("/dev/null", "w"))
    publies = Sujet.objects.filter(statut=Sujet.Statut.PUBLIE).select_related("session__examen")
    assert publies.count() == 70
    for sujet in publies:
        assert sujet.source.startswith("Épreuve provisoire")
        texte = PdfReader(sujet.fichier.path).pages[0].extract_text()
        mention = "PROVISIONAL PRACTICE PAPER" if sujet.session.examen.code == "HND" else "ÉPREUVE PROVISOIRE D'ENTRAÎNEMENT"
        assert mention in texte and f"{sujet.session.annee}" in texte, sujet
        assert len(sujet.texte_extrait) > 400  # une épreuve complète, pas une ligne
    # La session à venir reste sans épreuve (et en brouillon : règle de publication).
    assert not Sujet.objects.filter(session__annee=2027, texte_extrait__icontains="provisoire").exists()

    fichiers = dict(publies.values_list("pk", "fichier"))
    call_command("donnees_demo", stdout=open("/dev/null", "w"))
    assert dict(Sujet.objects.filter(pk__in=fichiers).values_list("pk", "fichier")) == fichiers  # rien de réécrit
