from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone
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
        "partenaires.Etablissement", on_delete=models.SET_NULL, null=True, blank=True, related_name="profils"
    )
    # Déclaré par l'étudiant, puis confirmé par un responsable de l'établissement : seul un étudiant
    # validé voit les épreuves internes (sinon n'importe qui pourrait se dire de l'IAI).
    etablissement_valide_le = models.DateTimeField(_("établissement validé le"), null=True, blank=True)
    etablissement_valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    session_prevue = models.ForeignKey(
        "catalogue.Session", on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("session prévue")
    )

    class Meta:
        verbose_name = _("profil d'étude")

    def __str__(self):
        return f"{self.utilisateur} · {self.specialite}"

    @property
    def etablissement_valide(self):
        return self.etablissement_id is not None and self.etablissement_valide_le is not None

    def save(self, *args, **kwargs):
        # Changer d'établissement annule la validation : le nouvel établissement doit confirmer à son tour.
        if self.pk:
            ancien = ProfilEtude.objects.filter(pk=self.pk).values_list("etablissement_id", flat=True).first()
            if ancien != self.etablissement_id:
                self.etablissement_valide_le = None
                self.etablissement_valide_par = None
        super().save(*args, **kwargs)

    def clean(self):
        if self.specialite.examen_id != self.examen_id:
            raise ValidationError({"specialite": _("Cette spécialité n'appartient pas à l'examen choisi.")})


class Consentement(models.Model):
    class Objet(models.TextChoices):
        CGU = "cgu", _("Conditions générales")
        CONFIDENTIALITE = "confidentialite", _("Politique de confidentialité")
        PARTAGE_ETABLISSEMENT = "partage_etablissement", _("Partage des résultats avec l'établissement")
        CONDITIONS_DE_VENTE = "conditions_de_vente", _("Conditions de vente")
        PROFIL_ENSEIGNANT = "profil_enseignant", _("Profil public d'enseignant")

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

    @classmethod
    def actif(cls, utilisateur, objet):
        return cls.objects.filter(utilisateur=utilisateur, objet=objet, date_revocation__isnull=True).exists()

    @classmethod
    def revoquer(cls, utilisateur, objet):
        cls.objects.filter(utilisateur=utilisateur, objet=objet, date_revocation__isnull=True).update(
            date_revocation=timezone.now()
        )

    @classmethod
    def partage_actif(cls, utilisateur):
        """CDC 10.6 : l'étudiant a-t-il accepté (et pas révoqué) le partage de ses résultats avec son établissement ?"""
        return cls.objects.filter(
            utilisateur=utilisateur, objet=cls.Objet.PARTAGE_ETABLISSEMENT, date_revocation__isnull=True
        ).exists()


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


class DoubleAuthentification(models.Model):
    """Code à 6 chiffres exigé de l'équipe pour entrer dans l'administration (accounts/double_auth.py)."""

    utilisateur = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="double_auth")
    # Partagé avec l'application du téléphone : jamais affiché dans l'administration.
    secret = models.CharField(max_length=64)
    active_le = models.DateTimeField(_("activée le"), null=True, blank=True, help_text=_("Vide : mise en place pas terminée."))
    dernier_pas = models.BigIntegerField(default=0, help_text=_("Dernier code accepté : il ne peut pas resservir."))
    codes_secours = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = _("double authentification")
        verbose_name_plural = _("doubles authentifications")

    def __str__(self):
        return str(self.utilisateur)

    @property
    def active(self):
        return self.active_le is not None


class ProfilEnseignant(models.Model):
    """CDC 11.1 : l'enseignant derrière chaque corrigé vérifié.

    Créé par l'administrateur (établissement, matières). L'enseignant choisit lui-même son affichage et sa photo ;
    sa carte n'apparaît qu'avec son consentement (Consentement « profil public enseignant »), retirable à tout moment.
    Sans lui, le corrigé affiche seulement « Vérifié par un enseignant ».
    """

    class Affichage(models.TextChoices):
        NOM = "nom", _("Nom complet")
        INITIALES = "initiales", _("Initiales seules")

    utilisateur = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profil_enseignant")
    etablissement = models.ForeignKey(
        "partenaires.Etablissement", on_delete=models.SET_NULL, null=True, blank=True, related_name="enseignants"
    )
    matieres = models.ManyToManyField("catalogue.Matiere", blank=True, related_name="enseignants",
                                      verbose_name=_("matières enseignées"))
    # Initiales par défaut : on n'affiche jamais plus que ce que l'enseignant a choisi.
    affichage = models.CharField(_("affichage du nom"), max_length=10, choices=Affichage.choices, default=Affichage.INITIALES)
    # Recadrée et réenregistrée sans métadonnées (accounts.enseignant.preparer_photo) ; servie par une vue qui vérifie
    # le consentement, jamais par son chemin.
    photo = models.ImageField(upload_to="enseignants/", blank=True)

    class Meta:
        verbose_name = _("profil enseignant")
        verbose_name_plural = _("profils enseignants")

    def __str__(self):
        return str(self.utilisateur)

    @property
    def visible(self):
        """Le consentement est la seule source : pas de case « visible » qui pourrait le contredire."""
        return Consentement.actif(self.utilisateur, Consentement.Objet.PROFIL_ENSEIGNANT)

    @property
    def nom_affiche(self):
        prenom, nom = self.utilisateur.first_name.strip(), self.utilisateur.last_name.strip()
        if self.affichage == self.Affichage.NOM and (prenom or nom):
            return f"{prenom} {nom}".strip()
        initiales = " ".join(f"{partie[0].upper()}." for partie in (prenom, nom) if partie)
        return initiales or _("Enseignant")


@receiver(post_delete, sender=ProfilEnseignant)
def effacer_photo(sender, instance, **kwargs):
    # Compte supprimé (CDC 10.2) : la photo part avec lui.
    if instance.photo:
        instance.photo.delete(save=False)
