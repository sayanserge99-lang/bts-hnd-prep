"""Règles du forum : limite quotidienne, signalements, avis à l'auteur de la question."""

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import Discussion, Reponse, SignalementForum


def messages_aujourd_hui(utilisateur):
    jour = timezone.localdate()
    return (
        Discussion.objects.filter(auteur=utilisateur, cree_le__date=jour).count()
        + Reponse.objects.filter(auteur=utilisateur, cree_le__date=jour).count()
    )


def peut_ecrire(utilisateur):
    return messages_aujourd_hui(utilisateur) < settings.FORUM_MESSAGES_PAR_JOUR


@transaction.atomic
def signaler(utilisateur, cible, motif):
    """Enregistre le signalement (une fois par compte) ; masque la cible quand assez de personnes l'ont signalée.

    Renvoie False si ce compte l'avait déjà signalée.
    """
    champ = "discussion" if isinstance(cible, Discussion) else "reponse"
    try:
        with transaction.atomic():
            SignalementForum.objects.create(utilisateur=utilisateur, motif=motif[:300], **{champ: cible})
    except IntegrityError:
        return False
    ouverts = SignalementForum.objects.filter(traite=False, **{champ: cible}).count()
    if ouverts >= settings.FORUM_SIGNALEMENTS_POUR_MASQUER and not cible.masquee:
        type(cible).objects.filter(pk=cible.pk).update(masquee=True)
    return True


def repondre(discussion, auteur, texte):
    reponse = Reponse.objects.create(discussion=discussion, auteur=auteur, texte=texte)
    Discussion.objects.filter(pk=discussion.pk).update(derniere_activite=reponse.cree_le)
    if discussion.auteur_id != auteur.pk:
        send_mail(
            _("Nouvelle réponse à votre question"),
            render_to_string("forum/email_nouvelle_reponse.txt", {"discussion": discussion, "reponse": reponse}),
            None,
            [discussion.auteur.email],
            fail_silently=True,
        )
    return reponse
