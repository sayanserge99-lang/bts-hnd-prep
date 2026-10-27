from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse

from .base import Fournisseur


class Simule(Fournisseur):
    """Agrégateur factice pour le développement : une page joue le rôle du téléphone de l'étudiant."""

    code = "simule"
    nom = "simulateur (essai)"

    def initier(self, paiement, request):
        if not settings.DEBUG:
            raise ImproperlyConfigured("L'agrégateur simulé ne s'utilise qu'en développement.")
        return reverse("paiements:simulateur", args=[paiement.reference])
