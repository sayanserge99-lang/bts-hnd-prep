from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Etablissement(models.Model):
    class Region(models.TextChoices):
        ADAMAOUA = "adamaoua", _("Adamaoua")
        CENTRE = "centre", _("Centre")
        EST = "est", _("Est")
        EXTREME_NORD = "extreme_nord", _("Extrême-Nord")
        LITTORAL = "littoral", _("Littoral")
        NORD = "nord", _("Nord")
        NORD_OUEST = "nord_ouest", _("Nord-Ouest")
        OUEST = "ouest", _("Ouest")
        SUD = "sud", _("Sud")
        SUD_OUEST = "sud_ouest", _("Sud-Ouest")

    nom = models.CharField(max_length=200, unique=True)
    # Facultatives : un établissement cité par les étudiants peut être ajouté avant de connaître son adresse.
    ville = models.CharField(max_length=100, blank=True)
    region = models.CharField(_("région"), max_length=20, choices=Region.choices, blank=True)
    contact = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = _("établissement")
        ordering = ["nom"]

    def __str__(self):
        return f"{self.nom} ({self.ville})" if self.ville else self.nom


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


def a_une_convention_active(etablissement, jour=None):
    jour = jour or timezone.localdate()
    return etablissement.partenariats.filter(
        statut=Partenariat.Statut.ACTIF, date_debut__lte=jour, date_fin__gte=jour
    ).exists()


class ResponsableEtablissement(models.Model):
    """Compte qui gère l'espace d'un établissement (enseignant, secrétariat) : créé par l'administrateur."""

    utilisateur = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="responsable_de"
    )
    etablissement = models.ForeignKey(Etablissement, on_delete=models.CASCADE, related_name="responsables")
    depuis = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("responsable d'établissement")
        verbose_name_plural = _("responsables d'établissement")

    def __str__(self):
        return f"{self.utilisateur} → {self.etablissement}"


class EpreuveInterne(models.Model):
    """Épreuve propre à un établissement (devoir, partiel…), visible par ses seuls étudiants validés."""

    class Type(models.TextChoices):
        DEVOIR = "devoir", _("Devoir")
        PARTIEL = "partiel", _("Partiel")
        EXAMEN_BLANC = "examen_blanc", _("Examen blanc interne")
        RATTRAPAGE = "rattrapage", _("Rattrapage")

    etablissement = models.ForeignKey(Etablissement, on_delete=models.CASCADE, related_name="epreuves")
    titre = models.CharField(max_length=200)
    matiere = models.ForeignKey(
        "catalogue.Matiere", on_delete=models.SET_NULL, null=True, blank=True, related_name="epreuves_internes"
    )
    type = models.CharField(_("type d'épreuve"), max_length=15, choices=Type.choices, default=Type.DEVOIR)
    annee_academique = models.CharField(_("année académique"), max_length=9, help_text=_("Par exemple 2025-2026."))
    fichier = models.FileField(_("fichier PDF"), upload_to="epreuves-internes/%Y/")
    publiee = models.BooleanField(_("publiée"), default=False)
    deposee_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    deposee_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("épreuve interne")
        verbose_name_plural = _("épreuves internes")
        ordering = ["-annee_academique", "titre"]

    def __str__(self):
        return f"{self.titre} ({self.etablissement.nom}, {self.annee_academique})"
