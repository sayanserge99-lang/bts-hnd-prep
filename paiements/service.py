"""Parcours de paiement (CDC 3.8, 10.7) : commande, confirmation par l'agrégateur, abonnement, reçu.

On ne se fie jamais au navigateur : le montant vient de l'offre, et seul l'agrégateur (notification signée,
ou consultation directe) déclare un paiement réussi.
"""

import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import mail_admins, send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext as _

from accounts.models import Consentement

from .fournisseurs import fournisseur_actif
from .models import Abonnement, Paiement

NUMERO = re.compile(r"^(?:\+?237)?(6\d{8})$")


def normaliser_telephone(saisie):
    """« 6 77 12 34 56 », « +237677123456 » → « 237677123456 » ; None si ce n'est pas un mobile camerounais."""
    correspondance = NUMERO.match(re.sub(r"[\s.-]", "", saisie))
    return f"237{correspondance.group(1)}" if correspondance else None


def refuser_second_pass(utilisateur, offre):
    """Un Pass déjà actif ne se rachète pas : le second couvrirait sans le dire la session suivante."""
    if offre.type != offre.Type.SESSION:
        return
    en_cours = Abonnement.pass_en_cours(utilisateur)
    if en_cours:
        raise ValidationError(
            _("Vous avez déjà le Pass session, valable jusqu'au %(fin)s.") % {"fin": f"{en_cours.fin:%d/%m/%Y}"}
        )


def periode(utilisateur, offre):
    """Dates de l'abonnement qu'achèterait l'utilisateur aujourd'hui (affichées avant le paiement)."""
    refuser_second_pass(utilisateur, offre)
    debut = Abonnement.prochain_jour_libre(utilisateur)
    profil = getattr(utilisateur, "profil", None)
    return debut, offre.calculer_fin(profil.examen if profil else None, debut)


def commander(utilisateur, offre, operateur, telephone, request):
    """Crée le paiement en attente et le lance chez l'agrégateur ; renvoie (paiement, adresse ou None)."""
    if not settings.PAIEMENT_ACTIF:
        raise ValidationError(_("Le paiement n'est pas encore ouvert."))
    fournisseur = fournisseur_actif()
    with transaction.atomic():
        paiement = Paiement.objects.create(
            utilisateur=utilisateur, offre=offre, montant=offre.prix, operateur=operateur, telephone=telephone,
            fournisseur=fournisseur.code, reference=f"BHP-{secrets.token_hex(8).upper()}",
        )
        # CDC 10.7 : conditions de vente acceptées avant de payer, et tracées.
        Consentement.objects.create(
            utilisateur=utilisateur, objet=Consentement.Objet.CONDITIONS_DE_VENTE, version=settings.VERSION_POLITIQUES
        )
    return paiement, fournisseur.initier(paiement, request)


def appliquer(notification):
    """Résultat annoncé par l'agrégateur. Sans effet s'il est déjà connu : l'agrégateur peut renvoyer
    la même notification plusieurs fois. Renvoie le paiement, ou None si la référence est inconnue."""
    with transaction.atomic():
        paiement = Paiement.objects.select_for_update().select_related("offre", "utilisateur").filter(reference=notification.reference).first()
        if paiement is None or paiement.statut != Paiement.Statut.EN_ATTENTE:
            return paiement
        if notification.reussi and notification.montant != paiement.montant:
            # Montant inattendu : on n'ouvre rien, l'équipe vérifie (fraude ou erreur de l'agrégateur).
            return _echec(paiement, _("Montant reçu (%(recu)s FCFA) différent du prix (%(prix)s FCFA).") % {
                "recu": notification.montant, "prix": paiement.montant,
            })
        if not notification.reussi:
            return _echec(paiement, notification.motif or _("Paiement refusé ou annulé."))
        paiement.statut = Paiement.Statut.REUSSI
        paiement.confirme_le = timezone.now()
        try:
            debut, fin = periode(paiement.utilisateur, paiement.offre)
        except ValidationError as erreur:
            # L'argent est reçu mais rien ne peut s'ouvrir (deux paiements du même Pass lancés ensemble, plus de
            # session à venir) : on le note, et l'équipe régularise (remboursement) au lieu de laisser le paiement
            # « en attente » et l'agrégateur réessayer sans fin.
            # Le message est copié : Python efface `erreur` à la sortie du bloc, avant l'envoi après validation.
            raison = erreur.messages[0]
            paiement.motif_echec = (_("À régulariser : ") + raison)[:200]
            paiement.save(update_fields=["statut", "confirme_le", "motif_echec"])
            transaction.on_commit(lambda: mail_admins(
                f"Paiement {paiement.reference} à régulariser", f"{paiement.utilisateur} · {paiement.offre} : {raison}",
                fail_silently=True,
            ))
            return paiement
        paiement.save(update_fields=["statut", "confirme_le"])
        Abonnement.objects.create(utilisateur=paiement.utilisateur, offre=paiement.offre, debut=debut, fin=fin, paiement=paiement)
        transaction.on_commit(lambda: envoyer_recu(paiement))
    return paiement


def _echec(paiement, motif):
    paiement.statut = Paiement.Statut.ECHOUE
    paiement.motif_echec = motif[:200]
    paiement.save(update_fields=["statut", "motif_echec"])
    return paiement


def rafraichir(paiement):
    """Page de suivi : demande le statut à l'agrégateur ; abandonne un paiement resté trop longtemps en attente."""
    if paiement.statut != Paiement.Statut.EN_ATTENTE:
        return paiement
    notification = fournisseur_actif().consulter(paiement)
    if notification:
        return appliquer(notification)
    if timezone.now() - paiement.cree_le > timedelta(minutes=settings.PAIEMENT_DELAI_MINUTES):
        with transaction.atomic():
            verrouille = Paiement.objects.select_for_update().get(pk=paiement.pk)
            if verrouille.statut == Paiement.Statut.EN_ATTENTE:
                return _echec(verrouille, _("Délai dépassé : aucune confirmation reçue."))
            return verrouille
    return paiement


def envoyer_recu(paiement):
    """CDC 10.7 : reçu envoyé après chaque paiement (et consultable dans le profil)."""
    send_mail(
        _("Votre reçu BTS-HND Prep n° %(numero)s") % {"numero": paiement.numero_recu},
        render_to_string("paiements/email_recu.txt", {"paiement": paiement, "abonnement": paiement.abonnement, "exploitant": settings.EXPLOITANT}),
        None,
        [paiement.utilisateur.email],
        fail_silently=True,
    )
