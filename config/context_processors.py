from django.conf import settings

from accounts import google
from accounts.moderation import est_administrateur
from partenaires.acces import etablissement_gere_par


def fonctionnalites(request):
    """Rend les drapeaux V2/V3 et l'état du paiement disponibles dans tous les templates."""
    return {
        "fonctionnalites": settings.FONCTIONNALITES,
        "paiement_actif": settings.PAIEMENT_ACTIF,
        # En développement, le CSS change souvent : on empêche le téléphone de garder l'ancien en cache.
        # En production, ManifestStaticFilesStorage donne déjà un nom unique à chaque version.
        "mode_developpement": settings.DEBUG,
        # Lien « Statistiques » de l'admin : administrateurs seulement (CDC 3.9).
        "est_administrateur": hasattr(request, "user") and request.user.is_staff and est_administrateur(request.user),
        # Bouton « Continuer avec Google » : seulement une fois les identifiants Google renseignés.
        "connexion_google": google.est_active(),
        # Lien « Mon établissement » du bandeau, pour les responsables d'établissement.
        "etablissement_gere": etablissement_gere_par(request.user) if hasattr(request, "user") else None,
    }
