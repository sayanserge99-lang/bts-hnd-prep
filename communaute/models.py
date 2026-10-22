from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from sujets.models import Corrige, Sujet

# Signalement et DemandeRetrait visent soit un sujet, soit un corrigé, jamais les deux.
UNE_SEULE_CIBLE = (Q(sujet__isnull=False) & Q(corrige__isnull=True)) | (
    Q(sujet__isnull=True) & Q(corrige__isnull=False)
)


class Contribution(models.Model):
    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", _("En attente")
        VALIDEE = "validee", _("Validée")
        REJETEE = "rejetee", _("Rejetée")

    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="contributions")
    fichier = models.FileField(upload_to="contributions/%Y/")
    annee = models.PositiveSmallIntegerField(_("année proposée"))
    specialite = models.ForeignKey("catalogue.Specialite", on_delete=models.PROTECT)
    matiere = models.ForeignKey("catalogue.Matiere", on_delete=models.PROTECT)
    commentaire = models.TextField(blank=True)
    certifie_droits = models.BooleanField(_("je certifie avoir le droit de partager ce document"))
    date_certification = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE)
    motif_rejet = models.TextField(blank=True)
    sujet = models.ForeignKey(
        "sujets.Sujet", on_delete=models.SET_NULL, null=True, blank=True, help_text=_("Renseigné une fois validée.")
    )
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("contribution")
        constraints = [
            # CDC 10.1 : case obligatoire, enregistrée avec la date.
            models.CheckConstraint(condition=Q(certifie_droits=True), name="contribution_droits_certifies"),
            models.CheckConstraint(
                condition=~Q(statut="rejetee") | ~Q(motif_rejet=""), name="contribution_rejet_motive"
            ),
        ]

    def __str__(self):
        return f"{self.matiere} {self.annee} · {self.utilisateur}"


class Signalement(models.Model):
    class Statut(models.TextChoices):
        OUVERT = "ouvert", _("Ouvert")
        TRAITE = "traite", _("Traité")
        REJETE = "rejete", _("Rejeté")

    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="signalements")
    sujet = models.ForeignKey(Sujet, on_delete=models.CASCADE, null=True, blank=True, related_name="signalements")
    corrige = models.ForeignKey(Corrige, on_delete=models.CASCADE, null=True, blank=True, related_name="signalements")
    motif = models.TextField()
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.OUVERT)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("signalement")
        constraints = [models.CheckConstraint(condition=UNE_SEULE_CIBLE, name="signalement_une_seule_cible")]

    def __str__(self):
        return f"Signalement · {self.sujet or self.corrige}"


class DemandeRetrait(models.Model):
    class Statut(models.TextChoices):
        RECUE = "recue", _("Reçue")
        ACCEPTEE = "acceptee", _("Acceptée (contenu supprimé)")
        REFUSEE = "refusee", _("Refusée (contenu republié)")

    # L'ayant droit n'a pas forcément de compte sur la plateforme.
    demandeur_nom = models.CharField(_("nom du demandeur"), max_length=200)
    demandeur_email = models.EmailField(_("e-mail du demandeur"))
    sujet = models.ForeignKey(Sujet, on_delete=models.CASCADE, null=True, blank=True, related_name="demandes_retrait")
    corrige = models.ForeignKey(
        Corrige, on_delete=models.CASCADE, null=True, blank=True, related_name="demandes_retrait"
    )
    motif = models.TextField()
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.RECUE)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("demande de retrait")
        verbose_name_plural = _("demandes de retrait")
        constraints = [models.CheckConstraint(condition=UNE_SEULE_CIBLE, name="demande_retrait_une_seule_cible")]

    def __str__(self):
        return f"Retrait · {self.sujet or self.corrige}"

    def save(self, *args, **kwargs):
        nouvelle = self._state.adding
        super().save(*args, **kwargs)
        # CDC 10.1 : le contenu est masqué dès réception, en attente d'examen.
        if nouvelle:
            if self.sujet_id:
                Sujet.objects.filter(pk=self.sujet_id).update(statut=Sujet.Statut.MASQUE)
            else:
                Corrige.objects.filter(pk=self.corrige_id).update(publication=Corrige.Publication.MASQUE)
