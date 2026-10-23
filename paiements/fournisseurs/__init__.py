"""Agrégateurs Mobile Money (CDC 3.8 : Orange Money et MTN MoMo via un agrégateur).

Brancher le vrai agrégateur (CinetPay, NotchPay, Campay…) = écrire une classe comme Simule dans ce dossier,
l'ajouter à FOURNISSEURS, puis régler PAIEMENT_FOURNISSEUR et PAIEMENT_SECRET dans .env.production.
"""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .base import Fournisseur, Notification, NotificationInvalide
from .simule import Simule

FOURNISSEURS = {Simule.code: Simule}


def fournisseur_actif():
    try:
        return FOURNISSEURS[settings.PAIEMENT_FOURNISSEUR]()
    except KeyError as erreur:
        raise ImproperlyConfigured(f"Agrégateur inconnu : {settings.PAIEMENT_FOURNISSEUR}") from erreur


__all__ = ["Fournisseur", "Notification", "NotificationInvalide", "fournisseur_actif"]
