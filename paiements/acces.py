"""Qui a les droits Premium (CDC 7) : la règle est ici, une seule fois, pour tout le site.

Tant que le paiement est fermé (PAIEMENT_ACTIF faux), il n'y a rien à vendre : tout est ouvert aux inscrits.
"""

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


def est_premium(utilisateur):
    """Droits Premium : abonné, équipe, ou tout inscrit tant que le paiement est fermé."""
    if not utilisateur.is_authenticated:
        return False
    return not settings.PAIEMENT_ACTIF or utilisateur.is_staff or a_un_abonnement_actif(utilisateur)


def lit_le_corrige_complet(utilisateur):
    # Seul droit ouvert aussi aux visiteurs tant que le paiement est fermé (le corrigé se lit sans compte).
    if not settings.PAIEMENT_ACTIF:
        return True
    return est_premium(utilisateur)
