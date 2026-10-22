from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Etablissement(models.Model):
    class Region(models.TextChoices):
        ADAMAOUA = "adamaoua", "Adamaoua"
        CENTRE = "centre", "Centre"
        EST = "est", "Est"
        EXTREME_NORD = "extreme_nord", "Extrême-Nord"
        LITTORAL = "littoral", "Littoral"
        NORD = "nord", "Nord"
        NORD_OUEST = "nord_ouest", "Nord-Ouest"
        OUEST = "ouest", "Ouest"
        SUD = "sud", "Sud"
        SUD_OUEST = "sud_ouest", "Sud-Ouest"

    nom = models.CharField(max_length=200)
    ville = models.CharField(max_length=100)
    region = models.CharField(_("région"), max_length=20, choices=Region.choices)
    contact = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = _("établissement")

    def __str__(self):
        return f"{self.nom} ({self.ville})"


class Partenariat(models.Model):
    class Statut(models.TextChoices):
        BROUILLON = "brouillon", _("En négociation")
        ACTIF = "actif", _("Actif")
        RESILIE = "resilie", _("Résilié")

    etablissement = models.ForeignKey(Etablissement, on_delete=models.PROTECT, related_name="partenariats")
    convention = models.FileField(_("convention signée (PDF)"), upload_to="conventions/", blank=True)
    date_debut = models.DateField()
    date_fin = models.DateField()
    taux_partage = models.DecimalField(
        _("taux de partage (%)"), max_digits=5, decimal_places=2, help_text=_("Part des revenus reversée à l'IPES.")
    )
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.BROUILLON)

    class Meta:
        verbose_name = _("partenariat")
        constraints = [
            models.CheckConstraint(condition=Q(date_fin__gte=F("date_debut")), name="partenariat_fin_apres_debut"),
            # Un partenariat ne peut être actif sans convention signée (CDC 10.6).
            models.CheckConstraint(
                condition=~Q(statut="actif") | ~Q(convention=""),
                name="partenariat_actif_avec_convention",
            ),
        ]

    def __str__(self):
        return f"{self.etablissement} · {self.date_debut:%Y}-{self.date_fin:%Y}"

    def est_actif(self, jour=None):
        jour = jour or timezone.localdate()
        return self.statut == self.Statut.ACTIF and self.date_debut <= jour <= self.date_fin
