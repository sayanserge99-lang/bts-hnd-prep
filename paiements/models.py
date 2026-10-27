from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from catalogue.models import Session


class Offre(models.Model):
    class Type(models.TextChoices):
        DUREE = "duree", _("Durée en jours")
        SESSION = "session", _("Pass session")

    nom = models.CharField(max_length=100)
    prix = models.PositiveIntegerField(_("prix (FCFA TTC)"))
    type = models.CharField(max_length=10, choices=Type.choices)
    duree_jours = models.PositiveSmallIntegerField(null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("offre")
        constraints = [
            models.CheckConstraint(
                condition=(Q(type="duree") & Q(duree_jours__isnull=False))
                | (Q(type="session") & Q(duree_jours__isnull=True)),
                name="offre_duree_selon_type",
            ),
        ]

    def __str__(self):
        return f"{self.nom} · {self.prix} FCFA"

    def calculer_fin(self, examen, debut):
        """Date de fin d'un abonnement commencé le jour `debut` (une date)."""
        if self.type == self.Type.DUREE:
            return debut + timedelta(days=self.duree_jours)
        # Le Pass couvre la prochaine session dont la date de fin officielle n'est pas passée.
        session = Session.objects.prochaine(examen, debut)
        if session is None:
            raise ValidationError(_("Aucune session à venir n'est enregistrée pour cet examen."))
        return session.date_fin_officielle


class Paiement(models.Model):
    class Operateur(models.TextChoices):
        ORANGE = "orange", "Orange Money"
        MTN = "mtn", "MTN MoMo"

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", _("En attente")
        REUSSI = "reussi", _("Réussi")
        ECHOUE = "echoue", _("Échoué")

    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="paiements")
    offre = models.ForeignKey(Offre, on_delete=models.PROTECT)
    # Fixé par le serveur à la commande (prix de l'offre), jamais reçu du navigateur.
    montant = models.PositiveIntegerField(_("montant (FCFA)"))
    operateur = models.CharField(max_length=10, choices=Operateur.choices)
    telephone = models.CharField(_("numéro Mobile Money"), max_length=15, blank=True)
    fournisseur = models.CharField(_("agrégateur"), max_length=20, blank=True)
    reference = models.CharField(_("référence de l'agrégateur"), max_length=100, unique=True)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE)
    motif_echec = models.CharField(max_length=200, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    confirme_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("paiement")
        ordering = ["-cree_le"]

    def __str__(self):
        return f"{self.reference} · {self.montant} FCFA"

    @property
    def numero_recu(self):
        """CDC 10.7 : numéro de reçu, suivi et sans trou dans l'ordre des paiements."""
        return f"R{self.cree_le:%Y}-{self.pk:06d}"


class CodeAcces(models.Model):
    # La durée vient de l'offre : pas de champ « durée » ici.
    code = models.CharField(max_length=20, unique=True)
    offre = models.ForeignKey(Offre, on_delete=models.PROTECT)
    partenariat = models.ForeignKey("partenaires.Partenariat", on_delete=models.PROTECT, related_name="codes")
    utilise_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="codes_utilises"
    )
    date_utilisation = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("code d'accès")
        verbose_name_plural = _("codes d'accès")

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        if self._state.adding and not self.partenariat.est_actif():
            raise ValidationError(_("Un établissement sans convention active ne peut pas recevoir de codes."))
        super().save(*args, **kwargs)


class Abonnement(models.Model):
    class Statut(models.TextChoices):
        ACTIF = "actif", _("Actif")
        EXPIRE = "expire", _("Expiré")
        ANNULE = "annule", _("Annulé")

    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="abonnements")
    # Vide pour des jours offerts à un contributeur : ils ne viennent d'aucune offre.
    offre = models.ForeignKey(Offre, on_delete=models.PROTECT, null=True, blank=True)
    debut = models.DateField()
    fin = models.DateField()
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.ACTIF)
    rappel_envoye_le = models.DateTimeField(
        _("rappel envoyé le"), null=True, blank=True, help_text=_("Rappel de fin d'abonnement : un seul par abonnement.")
    )
    # Créé à la réception du webhook de succès, ou à l'utilisation d'un code.
    paiement = models.OneToOneField(Paiement, on_delete=models.PROTECT, null=True, blank=True)
    code_acces = models.OneToOneField(CodeAcces, on_delete=models.PROTECT, null=True, blank=True)
    # CDC 3.7 : jours d'abonnement offerts pour chaque sujet validé.
    contribution = models.OneToOneField(
        "communaute.Contribution", on_delete=models.PROTECT, null=True, blank=True, related_name="recompense"
    )

    class Meta:
        verbose_name = _("abonnement")
        constraints = [
            models.CheckConstraint(
                condition=(Q(paiement__isnull=False) & Q(code_acces__isnull=True) & Q(contribution__isnull=True))
                | (Q(paiement__isnull=True) & Q(code_acces__isnull=False) & Q(contribution__isnull=True))
                | (Q(paiement__isnull=True) & Q(code_acces__isnull=True) & Q(contribution__isnull=False)),
                name="abonnement_une_seule_origine",
            ),
            models.CheckConstraint(
                condition=Q(offre__isnull=False) | Q(contribution__isnull=False), name="abonnement_offre_sauf_recompense"
            ),
        ]

    def __str__(self):
        origine = self.offre or _("jours offerts")
        return f"{self.utilisateur} · {origine} jusqu'au {self.fin:%d/%m/%Y}"

    @classmethod
    def prochain_jour_libre(cls, utilisateur):
        """Lendemain de l'abonnement en cours, ou aujourd'hui : un nouvel abonnement s'ajoute, il ne se superpose pas."""
        aujourd_hui = timezone.localdate()
        en_cours = (
            cls.objects.filter(utilisateur=utilisateur, statut=cls.Statut.ACTIF, fin__gte=aujourd_hui)
            .order_by("-fin")
            .values_list("fin", flat=True)
            .first()
        )
        return en_cours + timedelta(days=1) if en_cours else aujourd_hui

    @classmethod
    def offrir_jours(cls, utilisateur, jours, contribution):
        debut = cls.prochain_jour_libre(utilisateur)
        return cls.objects.create(
            utilisateur=utilisateur, debut=debut, fin=debut + timedelta(days=jours - 1), contribution=contribution
        )
