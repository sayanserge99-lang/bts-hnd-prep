"""Tâches programmées des abonnements (CDC 3.8), lancées chaque matin par le worker Celery."""

from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Exists, OuterRef
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import override

from .models import Abonnement


def expirer(aujourd_hui):
    """Les abonnements finis passent à « expiré » (l'accès, lui, suit déjà les dates)."""
    return Abonnement.objects.filter(statut=Abonnement.Statut.ACTIF, fin__lt=aujourd_hui).update(statut=Abonnement.Statut.EXPIRE)


def rappeler(aujourd_hui):
    """Un e-mail, une seule fois, quelques jours avant la fin d'un abonnement acheté ou obtenu par un code,
    sauf si la personne a déjà de quoi continuer (un abonnement qui prend la suite)."""
    if not settings.PAIEMENT_ACTIF:
        return 0  # rien à renouveler tant que le paiement est fermé
    suite = Abonnement.objects.filter(utilisateur=OuterRef("utilisateur"), statut=Abonnement.Statut.ACTIF, debut__gt=OuterRef("fin"))
    a_prevenir = (
        Abonnement.objects.filter(
            statut=Abonnement.Statut.ACTIF, offre__isnull=False, rappel_envoye_le__isnull=True,
            fin__gte=aujourd_hui, fin__lte=aujourd_hui + timedelta(days=settings.JOURS_AVANT_RAPPEL),
        )
        .exclude(Exists(suite))
        .select_related("utilisateur", "offre")
    )
    envoyes = 0
    for abonnement in a_prevenir:
        utilisateur = abonnement.utilisateur
        # L'e-mail part dans la langue choisie par l'étudiant.
        with override(utilisateur.langue):
            send_mail(
                _("Votre accès Premium se termine le %(fin)s") % {"fin": abonnement.fin.strftime("%d/%m/%Y")},
                render_to_string("paiements/email_rappel.txt", {"abonnement": abonnement, "site": settings.SITE_URL}),
                None,
                [utilisateur.email],
                fail_silently=True,
            )
        Abonnement.objects.filter(pk=abonnement.pk).update(rappel_envoye_le=timezone.now())
        envoyes += 1
    return envoyes


@shared_task
def suivre_les_abonnements():
    aujourd_hui = timezone.localdate()
    return {"expires": expirer(aujourd_hui), "rappels": rappeler(aujourd_hui)}
