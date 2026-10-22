from django.core.exceptions import ValidationError
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from .models import Sujet


@receiver(m2m_changed, sender=Sujet.specialites.through)
def verifier_specialites(sender, instance, action, reverse, pk_set, **kwargs):
    """Les spécialités d'un sujet doivent faire partie de celles de sa matière."""
    if action != "pre_add" or not pk_set:
        return
    if reverse:
        # specialite.sujets.add(...) : instance est la spécialité
        invalides = Sujet.objects.filter(pk__in=pk_set).exclude(matiere__specialites=instance).exists()
    else:
        autorisees = set(instance.matiere.specialites.values_list("pk", flat=True))
        invalides = bool(pk_set - autorisees)
    if invalides:
        raise ValidationError(_("Une spécialité choisie n'est pas rattachée à la matière du sujet."))
