from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from sujets.models import Corrige, Sujet

# Une demande de retrait vise soit un sujet, soit un corrigé, jamais les deux.
UNE_SEULE_CIBLE = (Q(sujet__isnull=False) & Q(corrige__isnull=True)) | (
    Q(sujet__isnull=True) & Q(corrige__isnull=False)
)
# Un signalement vise exactement un sujet, un corrigé ou une question de quiz (maquette, écran 8).
UNE_SEULE_CIBLE_SIGNALEMENT = (
    (Q(sujet__isnull=False) & Q(corrige__isnull=True) & Q(question__isnull=True))
    | (Q(sujet__isnull=True) & Q(corrige__isnull=False) & Q(question__isnull=True))
    | (Q(sujet__isnull=True) & Q(corrige__isnull=True) & Q(question__isnull=False))
)


class Contribution(models.Model):
    """Sujet envoyé ou corrigé proposé par un étudiant ou un enseignant (CDC 3.7), en file de modération."""

    class Type(models.TextChoices):
        SUJET = "sujet", _("Sujet")
        CORRIGE = "corrige", _("Corrigé")

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", _("En attente")
        VALIDEE = "validee", _("Validée")
        REJETEE = "rejetee", _("Rejetée")

    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="contributions")
    type = models.CharField(max_length=10, choices=Type.choices, default=Type.SUJET)
    # Toujours un PDF : les photos sont assemblées à l'envoi. Vide pour un corrigé rédigé en texte,
    # et supprimé au rejet (CDC 4.2 : une contribution suspecte est rejetée et supprimée).
    fichier = models.FileField(upload_to="contributions/%Y/", blank=True)
    texte = models.TextField(_("corrigé rédigé"), blank=True)
    annee = models.PositiveSmallIntegerField(_("année proposée"), null=True, blank=True)
    specialite = models.ForeignKey("catalogue.Specialite", on_delete=models.PROTECT, null=True, blank=True)
    matiere = models.ForeignKey("catalogue.Matiere", on_delete=models.PROTECT)
    sujet_vise = models.ForeignKey(
        "sujets.Sujet", on_delete=models.CASCADE, null=True, blank=True, related_name="corriges_proposes",
        verbose_name=_("sujet corrigé"), help_text=_("Pour un corrigé proposé : le sujet publié qu'il corrige."),
    )
    commentaire = models.TextField(blank=True)
    certifie_droits = models.BooleanField(_("je certifie avoir le droit de partager ce document"))
    date_certification = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE)
    motif_rejet = models.TextField(blank=True)
    sujet = models.ForeignKey(
        "sujets.Sujet", on_delete=models.SET_NULL, null=True, blank=True, help_text=_("Renseigné une fois validée.")
    )
    corrige = models.ForeignKey(
        "sujets.Corrige", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text=_("Renseigné une fois validée."),
    )
    jours_offerts = models.PositiveSmallIntegerField(_("jours d'abonnement offerts"), default=0)
    traitee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    traitee_le = models.DateTimeField(null=True, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("contribution")
        ordering = ["-cree_le"]
        constraints = [
            # CDC 10.1 : case obligatoire, enregistrée avec la date.
            models.CheckConstraint(condition=Q(certifie_droits=True), name="contribution_droits_certifies"),
            models.CheckConstraint(
                condition=~Q(statut="rejetee") | ~Q(motif_rejet=""), name="contribution_rejet_motive"
            ),
            models.CheckConstraint(
                condition=(Q(type="sujet") & Q(annee__isnull=False) & Q(sujet_vise__isnull=True))
                | (Q(type="corrige") & Q(sujet_vise__isnull=False)),
                name="contribution_cible_selon_type",
            ),
        ]

    def __str__(self):
        return f"{self.libelle} · {self.utilisateur}"

    @property
    def libelle(self):
        if self.type == self.Type.CORRIGE:
            return _("Corrigé de « %(sujet)s »") % {"sujet": self.sujet_vise}
        return f"{self.matiere} {self.annee}"

    @property
    def session_terminee(self):
        """Faux si la session de cette année n'est pas finie : la contribution ne peut alors pas être validée."""
        from .contributions import session_non_terminee

        return self.type != self.Type.SUJET or not session_non_terminee(self.matiere, self.annee)

    @property
    def doublons(self):
        """CDC 3.7 : sujets déjà présents pour la même année et la même matière."""
        if self.type != self.Type.SUJET:
            return Sujet.objects.none()
        return Sujet.objects.filter(matiere_id=self.matiere_id, session__annee=self.annee)


class Signalement(models.Model):
    class Statut(models.TextChoices):
        OUVERT = "ouvert", _("Ouvert")
        TRAITE = "traite", _("Traité")
        REJETE = "rejete", _("Rejeté")

    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="signalements")
    sujet = models.ForeignKey(Sujet, on_delete=models.CASCADE, null=True, blank=True, related_name="signalements")
    corrige = models.ForeignKey(Corrige, on_delete=models.CASCADE, null=True, blank=True, related_name="signalements")
    question = models.ForeignKey(
        "entrainement.Question", on_delete=models.CASCADE, null=True, blank=True, related_name="signalements"
    )
    motif = models.TextField()
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.OUVERT)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("signalement")
        constraints = [models.CheckConstraint(condition=UNE_SEULE_CIBLE_SIGNALEMENT, name="signalement_une_seule_cible")]

    def __str__(self):
        if self.question_id:
            return f"Signalement · {_('question')} « {str(self.question.enonce)[:60]} »"
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
    certifie_titulaire = models.BooleanField(
        _("je certifie être titulaire des droits sur ce contenu ou mandaté par lui"), default=False
    )
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.RECUE)
    cree_le = models.DateTimeField(auto_now_add=True)
    traitee_le = models.DateTimeField(null=True, blank=True)

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

    def accepter(self):
        """Le fichier est supprimé ; le contenu reste masqué et la demande garde la trace du retrait."""
        if self.sujet_id:
            self.sujet.fichier.delete(save=False)
            Sujet.objects.filter(pk=self.sujet_id).update(fichier="")
        else:
            if self.corrige.fichier:
                self.corrige.fichier.delete(save=False)
            Corrige.objects.filter(pk=self.corrige_id).update(
                fichier="", partie_gratuite="", contenu="[Retiré à la demande du titulaire des droits · Removed at the request of the rights holder]"
            )
        self._clore(self.Statut.ACCEPTEE)

    def refuser(self):
        """Le contenu est republié, sauf si une autre demande sur le même contenu est encore ouverte."""
        self._clore(self.Statut.REFUSEE)
        autres = DemandeRetrait.objects.filter(
            sujet_id=self.sujet_id, corrige_id=self.corrige_id, statut=self.Statut.RECUE
        )
        if autres.exists():
            return
        if self.sujet_id:
            # Un sujet dont la session n'est pas terminée redevient brouillon : la règle de publication prime.
            sujet = self.sujet
            sujet.statut = Sujet.Statut.PUBLIE if sujet.peut_etre_publie() else Sujet.Statut.BROUILLON
            sujet.save()
        else:
            corrige = self.corrige
            corrige.publication = (
                Corrige.Publication.PUBLIE if corrige.sujet.peut_etre_publie() else Corrige.Publication.BROUILLON
            )
            corrige.save()

    def _clore(self, statut):
        self.statut = statut
        self.traitee_le = timezone.now()
        self.save(update_fields=["statut", "traitee_le"])


class MessageContact(models.Model):
    """Message envoyé depuis la page Contact : gardé ici, donc jamais perdu si un e-mail n'arrive pas."""

    class Objet(models.TextChoices):
        QUESTION = "question", _("Question sur le site")
        ERREUR = "erreur", _("Erreur dans un sujet ou un corrigé")
        ETABLISSEMENT = "etablissement", _("Partenariat pour un établissement")
        PAIEMENT = "paiement", _("Paiement ou abonnement")
        AUTRE = "autre", _("Autre")

    nom = models.CharField(max_length=150)
    email = models.EmailField(_("e-mail"))
    objet = models.CharField(max_length=20, choices=Objet.choices)
    message = models.TextField(max_length=3000)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="messages_contact"
    )
    traite = models.BooleanField(_("traité"), default=False)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("message de contact")
        verbose_name_plural = _("messages de contact")
        ordering = ["traite", "-cree_le"]

    def __str__(self):
        return f"{self.get_objet_display()} · {self.nom}"
