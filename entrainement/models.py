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
        max_length=200,
        blank=True,
        help_text=_("Réponse courte uniquement. Plusieurs réponses acceptées : séparez-les par | (exemple : 40 %|40%|0,4)."),
    )
    explication = models.TextField(blank=True, help_text=_("Affichée après la réponse (CDC 3.4)."))
    difficulte = models.PositiveSmallIntegerField(choices=Difficulte.choices, default=Difficulte.MOYENNE)
    langue = models.CharField(max_length=2, choices=Langue.choices)
    # Validée par le modérateur de la matière : seule une question publiée entre dans les quiz.
    publiee = models.BooleanField(_("publiée"), default=False)

    class Meta:
        verbose_name = _("question")

    def __str__(self):
        return self.enonce[:80]

    @property
    def reponse_affichee(self):
        """Première des réponses acceptées : celle qu'on montre à l'étudiant après correction."""
        return self.reponse_attendue.split("|")[0].strip()

    def problemes(self, choix=None):
        """Ce qui empêche de publier la question. `choix` : liste de (texte, est_correct), sinon ceux en base."""
        if choix is None:
            choix = list(self.choix.values_list("texte", "est_correct"))
        bonnes = sum(1 for _texte, correct in choix if correct)
        if self.type == self.Type.REPONSE_COURTE:
            return [] if self.reponse_attendue.strip() else [_("Indiquez la réponse attendue.")]
        if self.type == self.Type.VRAI_FAUX and len(choix) != 2:
            return [_("Une question vrai/faux a exactement deux choix (Vrai et Faux).")]
        if len(choix) < 2:
            return [_("Il faut au moins deux choix.")]
        if self.type in (self.Type.CHOIX_UNIQUE, self.Type.VRAI_FAUX) and bonnes != 1:
            return [_("Il faut exactement une bonne réponse.")]
        if self.type == self.Type.CHOIX_MULTIPLE and bonnes < 1:
            return [_("Il faut au moins une bonne réponse.")]
        return []


class Choix(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choix")
    texte = models.CharField(max_length=300)
    est_correct = models.BooleanField(default=False)

    class Meta:
        verbose_name = _("choix")
        verbose_name_plural = _("choix")
        # L'ordre saisi par l'enseignant (sinon PostgreSQL ne garantit aucun ordre).
        ordering = ["pk"]

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

    @property
    def ordre(self):
        """Identifiants des questions, dans l'ordre où elles sont posées."""
        return self.reponses.get("ordre", [])


class ReponseQuestion(models.Model):
    """Une réponse donnée à une question : base des statistiques par chapitre (CDC 3.6)."""

    tentative = models.ForeignKey(Tentative, on_delete=models.CASCADE, related_name="reponses_donnees")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="reponses_donnees")
    reponse = models.JSONField(help_text=_("Identifiants des choix cochés, ou texte de la réponse courte."))
    correcte = models.BooleanField()
    repondu_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("réponse")
        constraints = [
            # Une seule réponse par question et par tentative : pas de seconde chance après la correction.
            models.UniqueConstraint(fields=["tentative", "question"], name="une_reponse_par_question"),
        ]

    def __str__(self):
        return f"{self.tentative} · {self.question} · {'✓' if self.correcte else '✗'}"
