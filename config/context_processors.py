from django.conf import settings

from accounts import google
from accounts.moderation import est_administrateur
from partenaires.acces import etablissement_gere_par


def roles(utilisateur):
    """Le menu suit le rôle : un compte sans profil d'étude qui a un rôle d'équipe (administration, modération,
    établissement, enseignant) n'a pas le menu de l'étudiant (tableau de bord, entraînement, offres)."""
    if not utilisateur.is_authenticated:
        return {"compte_equipe": False, "est_moderateur": False, "est_enseignant": False}
    administrateur = utilisateur.is_staff and est_administrateur(utilisateur)
    enseignant = hasattr(utilisateur, "profil_enseignant")
    etablissement = etablissement_gere_par(utilisateur)
    equipe = utilisateur.is_staff or enseignant or etablissement is not None
    return {
        "compte_equipe": equipe and not hasattr(utilisateur, "profil"),
        "est_moderateur": utilisateur.is_staff and not administrateur,
        "est_enseignant": enseignant,
    }


def fonctionnalites(request):
    """Rend les drapeaux V2/V3 et l'état du paiement disponibles dans tous les templates."""
    return {
        "fonctionnalites": settings.FONCTIONNALITES,
        "paiement_actif": settings.PAIEMENT_ACTIF,
        "beta": settings.BETA,
        # En développement, le CSS change souvent : on empêche le téléphone de garder l'ancien en cache.
        # En production, ManifestStaticFilesStorage donne déjà un nom unique à chaque version.
        "mode_developpement": settings.DEBUG,
        # Lien « Statistiques » de l'admin : administrateurs seulement (CDC 3.9).
        "est_administrateur": hasattr(request, "user") and request.user.is_staff and est_administrateur(request.user),
        # Bouton « Continuer avec Google » : seulement une fois les identifiants Google renseignés.
        "connexion_google": google.est_active(),
        # Lien « Mon établissement » du bandeau, pour les responsables d'établissement.
        "etablissement_gere": etablissement_gere_par(request.user) if hasattr(request, "user") else None,
        **(roles(request.user) if hasattr(request, "user") else {}),
    }
