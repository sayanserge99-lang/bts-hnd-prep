from django.conf import settings
from django.core.checks import Error, register


@register()
def agregateur_reel_en_production(app_configs, **kwargs):
    """Jamais d'agrégateur simulé quand le paiement est ouvert hors développement."""
    if settings.PAIEMENT_ACTIF and not settings.DEBUG and settings.PAIEMENT_FOURNISSEUR == "simule":
        return [Error(
            "Paiement ouvert avec l'agrégateur simulé.",
            hint="Réglez PAIEMENT_FOURNISSEUR et PAIEMENT_SECRET (agrégateur réel) dans .env.production.",
            id="paiements.E001",
        )]
    if settings.PAIEMENT_ACTIF and not settings.DEBUG and settings.PAIEMENT_SECRET.startswith("simule-"):
        return [Error("PAIEMENT_SECRET n'est pas réglé.", hint="Secret fourni par l'agrégateur.", id="paiements.E002")]
    return []
