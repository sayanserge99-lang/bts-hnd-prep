from django.core.exceptions import ValidationError
from django.db.models.signals import m2m_changed, post_save, pre_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from catalogue.models import Matiere

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


@receiver(pre_save, sender=Matiere)
def retenir_anciens_noms(sender, instance, **kwargs):
    instance._anciens_noms = (
        Matiere.objects.filter(pk=instance.pk).values_list("nom_fr", "nom_en").first() if instance.pk else None
    )


@receiver(post_save, sender=Matiere)
def reindexer_apres_renommage(sender, instance, created, **kwargs):
    """Le nom de la matière fait partie de l'index de recherche de ses sujets : un renommage le met à jour."""
    if created or getattr(instance, "_anciens_noms", None) == (instance.nom_fr, instance.nom_en):
        return
    for sujet in Sujet.objects.filter(matiere=instance).select_related("session__examen", "matiere"):
        sujet.mettre_a_jour_recherche()
