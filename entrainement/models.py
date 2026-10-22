from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from catalogue.models import Langue


class Question(models.Model):
    class Type(models.TextChoices):
        CHOIX_UNIQUE = "choix_unique", _("Choix unique")
        CHOIX_MULTIPLE = "choix_multiple", _("Choix multiple")
        VRAI_FAUX = "vrai_faux", _("Vrai / faux")
        REPONSE_COURTE = "reponse_courte", _("Réponse courte")

    class Difficulte(models.IntegerChoices):
        FACILE = 1, _("Facile")
        MOYENNE = 2, _("Moyenne")
        DIFFICILE = 3, _("Difficile")

    chapitre = models.ForeignKey("catalogue.Chapitre", on_delete=models.PROTECT, related_name="questions")
    enonce = models.TextField(_("énoncé"))
    type = models.CharField(max_length=20, choices=Type.choices)
    reponse_attendue = models.CharField(
        max_length=200, blank=True, help_text=_("Uniquement pour une réponse courte.")
    )
    explication = models.TextField(blank=True)
    difficulte = models.PositiveSmallIntegerField(choices=Difficulte.choices, default=Difficulte.MOYENNE)
    langue = models.CharField(max_length=2, choices=Langue.choices)

    class Meta:
        verbose_name = _("question")

    def __str__(self):
        return self.enonce[:80]


class Choix(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choix")
    texte = models.CharField(max_length=300)
    est_correct = models.BooleanField(default=False)

    class Meta:
        verbose_name = _("choix")
        verbose_name_plural = _("choix")

    def __str__(self):
        return self.texte


class Quiz(models.Model):
    class Mode(models.TextChoices):
        RAPIDE = "rapide", _("Quiz rapide")
        REVISION = "revision", _("Révision des erreurs")

    titre = models.CharField(max_length=200)
    mode = models.CharField(max_length=10, choices=Mode.choices)
    matiere = models.ForeignKey("catalogue.Matiere", on_delete=models.PROTECT, related_name="quiz")
    chapitre = models.ForeignKey(
        "catalogue.Chapitre", on_delete=models.PROTECT, null=True, blank=True, related_name="quiz"
    )
    nb_questions = models.PositiveSmallIntegerField(_("nombre de questions"), default=10)
    questions = models.ManyToManyField(Question, related_name="quiz")

    class Meta:
        verbose_name = _("quiz")
        verbose_name_plural = _("quiz")

    def __str__(self):
        return self.titre


class ExamenBlanc(models.Model):
    titre = models.CharField(max_length=200)
    sujet = models.ForeignKey("sujets.Sujet", on_delete=models.PROTECT, related_name="examens_blancs")
    duree = models.PositiveSmallIntegerField(_("durée (minutes)"))
    bareme = models.TextField(_("barème"))
    questions = models.ManyToManyField(Question, related_name="examens_blancs", blank=True)

    class Meta:
        verbose_name = _("examen blanc")
        verbose_name_plural = _("examens blancs")

    def __str__(self):
        return self.titre


class Tentative(models.Model):
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tentatives")
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, null=True, blank=True, related_name="tentatives")
    examen_blanc = models.ForeignKey(
        ExamenBlanc, on_delete=models.CASCADE, null=True, blank=True, related_name="tentatives"
    )
    debut = models.DateTimeField(default=timezone.now)
    fin_prevue = models.DateTimeField(
        _("heure de fin prévue"), null=True, blank=True, help_text=_("Fixée par le serveur : le chrono reprend après une coupure.")
    )
    fin = models.DateTimeField(null=True, blank=True)
    note = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    reponses = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = _("tentative")
        ordering = ["-debut"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(quiz__isnull=False) & Q(examen_blanc__isnull=True))
                | (Q(quiz__isnull=True) & Q(examen_blanc__isnull=False)),
                name="tentative_une_seule_cible",
            ),
        ]

    def __str__(self):
        return f"{self.utilisateur} · {self.quiz or self.examen_blanc}"
