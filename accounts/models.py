from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from catalogue.models import Langue


class UtilisateurManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("L'adresse e-mail est obligatoire.")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra_fields)


class Utilisateur(AbstractUser):
    # Les rôles passent uniquement par les groupes Django (Étudiant, Modérateur, Administrateur).
    username = None
    email = models.EmailField(_("adresse e-mail"), unique=True)
    telephone = models.CharField(
        _("téléphone"), max_length=20, blank=True, help_text=_("Facultatif, utilisé pour le paiement (V3).")
    )
    langue = models.CharField(max_length=2, choices=Langue.choices, default=Langue.FR)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UtilisateurManager()

    class Meta:
        verbose_name = _("utilisateur")

    def __str__(self):
        return self.email


class ProfilEtude(models.Model):
    utilisateur = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profil")
    examen = models.ForeignKey("catalogue.Examen", on_delete=models.PROTECT, verbose_name=_("examen visé"))
    specialite = models.ForeignKey("catalogue.Specialite", on_delete=models.PROTECT)
    etablissement = models.ForeignKey(
        "partenaires.Etablissement", on_delete=models.SET_NULL, null=True, blank=True
    )
    session_prevue = models.ForeignKey(
        "catalogue.Session", on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("session prévue")
    )

    class Meta:
        verbose_name = _("profil d'étude")

    def __str__(self):
        return f"{self.utilisateur} · {self.specialite}"

    def clean(self):
        if self.specialite.examen_id != self.examen_id:
            raise ValidationError({"specialite": _("Cette spécialité n'appartient pas à l'examen choisi.")})


class Consentement(models.Model):
    class Objet(models.TextChoices):
        CGU = "cgu", _("Conditions générales")
        CONFIDENTIALITE = "confidentialite", _("Politique de confidentialité")
        PARTAGE_ETABLISSEMENT = "partage_etablissement", _("Partage des résultats avec l'établissement")

    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="consentements")
    objet = models.CharField(max_length=30, choices=Objet.choices)
    version = models.CharField(_("version de la politique"), max_length=20)
    date = models.DateTimeField(auto_now_add=True)
    date_revocation = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("consentement")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.utilisateur} · {self.get_objet_display()} v{self.version}"

    @property
    def est_actif(self):
        return self.date_revocation is None


class AffectationModerateur(models.Model):
    moderateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="affectations")
    matiere = models.ForeignKey("catalogue.Matiere", on_delete=models.CASCADE, related_name="moderateurs")
    date_attribution = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("affectation de modérateur")
        constraints = [
            models.UniqueConstraint(fields=["moderateur", "matiere"], name="affectation_unique"),
        ]

    def __str__(self):
        return f"{self.moderateur} → {self.matiere}"
