"""Écrit le classeur vide du référentiel (sessions, spécialités, matières, coefficients, chapitres)."""

from django.core.management.base import BaseCommand

from catalogue.referentiel import modele


class Command(BaseCommand):
    help = "Écrit le modèle Excel du référentiel à remplir, puis à importer avec importer_referentiel."

    def add_arguments(self, parser):
        parser.add_argument("chemin", nargs="?", default="referentiel.xlsx")

    def handle(self, chemin, **options):
        modele(chemin)
        self.stdout.write(self.style.SUCCESS(f"Modèle écrit : {chemin}"))
