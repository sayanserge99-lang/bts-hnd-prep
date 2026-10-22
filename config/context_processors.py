from django.conf import settings


def fonctionnalites(request):
    """Rend les drapeaux V2/V3 et l'état du paiement disponibles dans tous les templates."""
    return {
        "fonctionnalites": settings.FONCTIONNALITES,
        "paiement_actif": settings.PAIEMENT_ACTIF,
    }
