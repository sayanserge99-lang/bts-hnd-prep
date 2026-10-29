"""CDC 11.1 : codes de réduction. La remise se calcule seulement ici, sur le serveur.

Une utilisation est réservée à la commande, sous verrou de la ligne du code : deux paiements lancés en même temps sur
la dernière utilisation ne passent pas tous les deux. Elle est confirmée par le webhook de succès et effacée si le
paiement échoue ou expire (service._echec) : un paiement raté ne consomme rien.
"""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import CodeReduction, Paiement


class CodeRefuse(Exception):
    """Message montré tel quel à l'étudiant (code inconnu, expiré, épuisé…)."""


def trouver(saisie):
    """Insensible à la casse et aux espaces autour."""
    return CodeReduction.objects.filter(code=saisie.strip().upper()).first() if saisie.strip() else None


def remise_pour(code, prix):
    """Remise en FCFA ; le montant payé ne descend jamais sous PAIEMENT_PRIX_MINIMUM (frais de l'agrégateur)."""
    brute = round(prix * code.valeur / 100) if code.type == CodeReduction.Type.POURCENTAGE else code.valeur
    plancher = min(prix, settings.PAIEMENT_PRIX_MINIMUM)
    return prix - max(prix - brute, plancher)


def places_prises(code):
    # Réservées (paiement en attente) et confirmées : les paiements échoués ont déjà effacé la leur.
    return code.utilisations.count()


def verifier(code, utilisateur, offre):
    if code is None or not code.actif:
        raise CodeRefuse(_("Ce code de réduction n'existe pas. Vérifiez l'orthographe."))
    aujourd_hui = timezone.localdate()
    if aujourd_hui < code.debut:
        raise CodeRefuse(_("Ce code n'est valable qu'à partir du %(debut)s.") % {"debut": f"{code.debut:%d/%m/%Y}"})
    if aujourd_hui > code.fin:
        raise CodeRefuse(_("Ce code a expiré le %(fin)s.") % {"fin": f"{code.fin:%d/%m/%Y}"})
    if not code.offres.filter(pk=offre.pk).exists():
        raise CodeRefuse(_("Ce code ne vaut pas pour l'offre « %(offre)s ».") % {"offre": offre.nom})
    if code.etablissement_id:
        profil = getattr(utilisateur, "profil", None)
        if not (profil and profil.etablissement_id == code.etablissement_id and profil.etablissement_valide):
            raise CodeRefuse(
                _("Ce code est réservé aux étudiants confirmés par %(etablissement)s.") % {"etablissement": code.etablissement.nom}
            )
    if code.utilisations.filter(utilisateur=utilisateur).exists():
        raise CodeRefuse(_("Vous avez déjà utilisé ce code (un seul usage par étudiant)."))
    if code.utilisations_max is not None and places_prises(code) >= code.utilisations_max:
        raise CodeRefuse(_("Ce code est épuisé : toutes ses utilisations ont été prises."))
    if remise_pour(code, offre.prix) == 0:
        raise CodeRefuse(_("Ce code n'apporte aucune remise sur cette offre."))


def evaluer(saisie, utilisateur, offre):
    """Pour l'affichage avant de payer : (code, remise), ou CodeRefuse."""
    code = trouver(saisie)
    liberer_les_reservations_expirees(code)
    verifier(code, utilisateur, offre)
    return code, remise_pour(code, offre.prix)


def liberer_les_reservations_expirees(code):
    """Un paiement resté en attente au-delà du délai de l'agrégateur rend son utilisation (même règle que la page de
    suivi : on consulte l'agrégateur, puis on abandonne)."""
    if code is None or code.utilisations_max is None:
        return
    from .service import rafraichir  # service importe ce module

    limite = timezone.now() - timedelta(minutes=settings.PAIEMENT_DELAI_MINUTES)
    for paiement in Paiement.objects.filter(
        utilisation_code__code=code, statut=Paiement.Statut.EN_ATTENTE, cree_le__lt=limite
    ):
        rafraichir(paiement)


def verrouiller(code, utilisateur, offre):
    """Dans la transaction de la commande : verrou sur le code, puis toutes les vérifications refaites (la limite a pu
    être atteinte depuis l'affichage). Le second paiement simultané attend le verrou, puis compte la réservation du
    premier."""
    code = CodeReduction.objects.select_for_update().get(pk=code.pk)
    verifier(code, utilisateur, offre)
    return code, remise_pour(code, offre.prix)
