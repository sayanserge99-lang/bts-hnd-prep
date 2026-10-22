from django.core.management.base import BaseCommand

from sujets.models import Sujet


class Command(BaseCommand):
    help = "Recalcule l'index de recherche de tous les sujets (après un import groupé ou un renommage de matière)."

    def handle(self, *args, **options):
        nombre = 0
        for sujet in Sujet.objects.select_related("session__examen", "matiere").iterator():
            sujet.mettre_a_jour_recherche()
            nombre += 1
        self.stdout.write(self.style.SUCCESS(f"{nombre} sujet(s) réindexé(s)."))
