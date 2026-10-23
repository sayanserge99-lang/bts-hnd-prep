"""Qui voit quoi côté établissement (CDC 10.6)."""

from .models import EpreuveInterne, ResponsableEtablissement, a_une_convention_active


def etablissement_gere_par(utilisateur):
    """L'établissement dont l'utilisateur est responsable, ou None."""
    if not utilisateur.is_authenticated:
        return None
    rattachement = ResponsableEtablissement.objects.filter(utilisateur=utilisateur).select_related("etablissement").first()
    return rattachement.etablissement if rattachement else None


def etablissement_valide_de(utilisateur):
    """L'établissement de l'étudiant, seulement si l'établissement l'a confirmé."""
    profil = getattr(utilisateur, "profil", None) if utilisateur.is_authenticated else None
    return profil.etablissement if profil and profil.etablissement_valide else None


def epreuves_visibles(etablissement):
    """Épreuves internes visibles par les étudiants : publiées, et convention de partenariat en cours."""
    if not a_une_convention_active(etablissement):
        return EpreuveInterne.objects.none()
    return etablissement.epreuves.filter(publiee=True).select_related("matiere")
