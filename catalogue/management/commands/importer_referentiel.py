"""Importe le référentiel rempli. Par défaut, vérifie seulement ; --appliquer enregistre.

En production, le fichier est sur l'ordinateur, pas dans le conteneur : on le passe par l'entrée standard.
    docker compose -f compose.prod.yaml exec -T web python manage.py importer_referentiel - < referentiel.xlsx
"""

import io
import sys

from django.core.management.base import BaseCommand, CommandError

from catalogue.referentiel import ErreurClasseur, importer


class Command(BaseCommand):
    help = "Vérifie (puis, avec --appliquer, enregistre) un référentiel Excel rempli à partir du modèle."

    def add_arguments(self, parser):
        parser.add_argument("fichier", help="Chemin du classeur .xlsx, ou - pour le lire sur l'entrée standard.")
        parser.add_argument("--appliquer", action="store_true", help="Enregistrer (sans cette option : essai à blanc).")

    def handle(self, fichier, appliquer, **options):
        source = io.BytesIO(sys.stdin.buffer.read()) if fichier == "-" else fichier
        try:
            rapport = importer(source, appliquer=appliquer)
        except (ErreurClasseur, FileNotFoundError) as exc:
            raise CommandError(str(exc))

        for feuille, comptes in rapport.comptes.items():
            self.stdout.write(f"{feuille} : " + ", ".join(f"{n} {quoi}" for quoi, n in comptes.items()))
        for avertissement in rapport.avertissements:
            self.stdout.write(self.style.WARNING(f"Attention : {avertissement}"))
        if rapport.erreurs:
            for erreur in rapport.erreurs:
                self.stderr.write(self.style.ERROR(erreur))
            raise CommandError(f"{len(rapport.erreurs)} erreur(s) : rien n'est enregistré. Corrigez le fichier et relancez.")
        if appliquer:
            self.stdout.write(self.style.SUCCESS("Référentiel enregistré."))
        else:
            self.stdout.write(self.style.SUCCESS("Aucune erreur. Essai à blanc : relancez avec --appliquer pour enregistrer."))
