from django.core.management.base import BaseCommand, CommandError

from sujets import importation


class Command(BaseCommand):
    help = (
        "Importe des sujets depuis un ZIP ou un dossier contenant sujets.csv et les fichiers cités. "
        "Simulation par défaut ; ajouter --appliquer pour enregistrer. Les sujets arrivent en brouillon."
    )

    def add_arguments(self, parser):
        parser.add_argument("chemin", help="Fichier ZIP ou dossier")
        parser.add_argument("--appliquer", action="store_true", help="Enregistrer pour de bon")

    def handle(self, chemin, appliquer, **options):
        try:
            if chemin.lower().endswith(".zip"):
                with open(chemin, "rb") as fichier:
                    source = importation.SourceZip(fichier)
                    rapport = self._importer(source, appliquer)
            else:
                rapport = self._importer(importation.SourceDossier(chemin), appliquer)
        except (importation.ImportImpossible, FileNotFoundError) as erreur:
            raise CommandError(str(erreur)) from erreur

        for ligne in rapport:
            self.stdout.write(f"ligne {ligne.numero:>4}  {ligne.statut:<8} {ligne.fichier}  {ligne.message}")
        compte = {statut: sum(l.statut == statut for l in rapport) for statut in ("pret", "importe", "doublon", "erreur")}
        self.stdout.write(self.style.SUCCESS(
            f"{'Simulation' if not appliquer else 'Import'} : {compte['pret'] + compte['importe']} sujet(s) "
            f"{'prêt(s)' if not appliquer else 'importé(s)'}, {compte['doublon']} doublon(s), {compte['erreur']} erreur(s)."
        ))

    def _importer(self, source, appliquer):
        return importation.Importateur().importer(source, importation.tableau_du_zip(source), simulation=not appliquer)
