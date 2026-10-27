from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Langue(models.TextChoices):
    FR = "fr", _("Français")
    EN = "en", _("Anglais")


class Examen(models.Model):
    class Code(models.TextChoices):
        BTS = "BTS", "BTS"
        HND = "HND", "HND"

    code = models.CharField(max_length=3, choices=Code.choices, unique=True)
    nom = models.CharField(_("nom"), max_length=150)
    langue = models.CharField(max_length=2, choices=Langue.choices)

    class Meta:
        verbose_name = _("examen")

    def __str__(self):
        return self.code


def _fin_trop_tardive(session_ou_sessions, fin):
    """Message si des sujets publiés deviendraient « publiés avant la fin officielle » (règle absolue, CDC 4.2)."""
    if fin is None or fin < timezone.localdate():
        return None
    filtre = {"session__in": session_ou_sessions} if isinstance(session_ou_sessions, models.QuerySet) else {"session": session_ou_sessions}
    # Import tardif : les sujets dépendent du catalogue, pas l'inverse.
    from sujets.models import Sujet

    publies = Sujet.objects.filter(statut=Sujet.Statut.PUBLIE, **filtre).count()
    if not publies:
        return None
    return ValidationError(
        _("%(n)s sujet(s) publié(s) dans cette session : la fin officielle ne peut pas passer au %(date)s, qui n'est "
          "pas encore passé. Si la date était fausse, masquez d'abord ces sujets."),
        code="fin_apres_publication",
        params={"n": publies, "date": fin.strftime("%d/%m/%Y")},
    )


class SessionQuerySet(models.QuerySet):
    # Les opérations groupées contournent save() : on y applique la même règle.
    def update(self, **kwargs):
        erreur = _fin_trop_tardive(self, kwargs.get("date_fin_officielle"))
        if erreur:
            raise erreur
        return super().update(**kwargs)

    def prochaine(self, examen, a_partir_du):
        """Première session de l'examen dont la date de fin officielle n'est pas passée."""
        return (
            self.filter(examen=examen, date_fin_officielle__gte=a_partir_du)
            .order_by("date_fin_officielle")
            .first()
        )


class Session(models.Model):
    examen = models.ForeignKey(Examen, on_delete=models.PROTECT, related_name="sessions")
    annee = models.PositiveSmallIntegerField(_("année"))
    date_debut = models.DateField(_("date de début"))
    date_fin_officielle = models.DateField(
        _("date de fin officielle"),
        help_text=_("Aucun sujet de la session ne peut être publié avant le lendemain de cette date."),
    )

    objects = SessionQuerySet.as_manager()

    class Meta:
        verbose_name = _("session")
        ordering = ["-annee"]
        constraints = [
            models.UniqueConstraint(fields=["examen", "annee"], name="session_unique_par_examen"),
            models.CheckConstraint(
                condition=Q(date_fin_officielle__gte=F("date_debut")),
                name="session_fin_apres_debut",
            ),
        ]

    def __str__(self):
        return f"{self.examen} {self.annee}"

    def clean(self):
        if self.pk:
            erreur = _fin_trop_tardive(self, self.date_fin_officielle)
            if erreur:
                raise ValidationError({"date_fin_officielle": erreur})

    def save(self, *args, **kwargs):
        # Aucun rôle, superutilisateur compris, ne peut passer outre (comme pour la publication d'un sujet).
        if self.pk:
            erreur = _fin_trop_tardive(self, self.date_fin_officielle)
            if erreur:
                raise erreur
        super().save(*args, **kwargs)

    def est_terminee(self, aujourd_hui=None):
        # Le jour de fin compte encore comme session en cours.
        return self.date_fin_officielle < (aujourd_hui or timezone.localdate())


class Specialite(models.Model):
    class Filiere(models.TextChoices):
        COMMERCIALE = "commerciale", _("Commerciale")
        INDUSTRIELLE = "industrielle", _("Industrielle")
        SANTE = "sante", _("Santé")

    examen = models.ForeignKey(Examen, on_delete=models.PROTECT, related_name="specialites")
    code = models.CharField(max_length=20)
    nom = models.CharField(_("nom"), max_length=200)
    filiere = models.CharField(_("filière"), max_length=20, choices=Filiere.choices)
    # Les spécialités prioritaires (lancement) s'affichent en premier partout sur le site.
    ordre = models.PositiveSmallIntegerField(_("ordre d'affichage"), default=100, help_text=_("Plus petit = affiché en premier."))
    matieres = models.ManyToManyField("Matiere", through="SpecialiteMatiere", related_name="specialites")

    class Meta:
        verbose_name = _("spécialité")
        ordering = ["ordre", "nom"]
        constraints = [
            models.UniqueConstraint(fields=["examen", "code"], name="specialite_code_unique_par_examen"),
        ]

    def __str__(self):
        return self.nom


class Matiere(models.Model):
    # Une matière appartient à un seul examen : « Comptabilité générale » (BTS)
    # et « Financial Accounting » (HND) sont deux matières distinctes.
    examen = models.ForeignKey(Examen, on_delete=models.PROTECT, related_name="matieres")
    nom = models.CharField(_("nom"), max_length=200)

    class Meta:
        verbose_name = _("matière")

    def __str__(self):
        return self.nom


class SpecialiteMatiere(models.Model):
    specialite = models.ForeignKey(Specialite, on_delete=models.CASCADE)
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE)
    coefficient = models.PositiveSmallIntegerField()

    class Meta:
        verbose_name = _("matière d'une spécialité")
        verbose_name_plural = _("matières des spécialités")
        constraints = [
            models.UniqueConstraint(fields=["specialite", "matiere"], name="specialite_matiere_unique"),
        ]

    def __str__(self):
        return f"{self.specialite} · {self.matiere} (coef. {self.coefficient})"

    def save(self, *args, **kwargs):
        if self.specialite.examen_id != self.matiere.examen_id:
            raise ValidationError(_("La spécialité et la matière doivent appartenir au même examen."))
        super().save(*args, **kwargs)


class Chapitre(models.Model):
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE, related_name="chapitres")
    titre = models.CharField(_("titre"), max_length=200)
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = _("chapitre")
        ordering = ["matiere", "ordre"]

    def __str__(self):
        return self.titre
