"""Qui lit le corrigé complet (CDC 7) : abonnés Premium, équipe, et tout le monde tant que le paiement est fermé."""

from django.conf import settings
from django.utils import timezone

from .models import Abonnement


def a_un_abonnement_actif(utilisateur):
    if not utilisateur.is_authenticated:
        return False
    aujourd_hui = timezone.localdate()
    return Abonnement.objects.filter(
        utilisateur=utilisateur, statut=Abonnement.Statut.ACTIF, debut__lte=aujourd_hui, fin__gte=aujourd_hui
    ).exists()


def lit_le_corrige_complet(utilisateur):
    # Accès partiel = V3 : sans paiement ouvert, il n'y a rien à vendre, donc tout est visible.
    if not settings.PAIEMENT_ACTIF:
        return True
    return utilisateur.is_authenticated and (utilisateur.is_staff or a_un_abonnement_actif(utilisateur))
