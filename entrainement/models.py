from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from catalogue.models import Langue


def filtre_questions_visibles(prefixe=""):
    """Questions qui peuvent entrer dans un quiz : publiées, et dont le sujet éventuel est publié.

    Une question tirée d'un sujet en dévoile le contenu : elle suit la visibilité du sujet (CDC 4.2),
    sinon un quiz rapide de la matière ferait fuiter un sujet dont la session n'est pas terminée.
    """
    return Q(**{f"{prefixe}publiee": True}) & (
        Q(**{f"{prefixe}sujet__isnull": True})
        | Q(**{f"{prefixe}sujet__statut": "publie", f"{prefixe}sujet__session__date_fin_officielle__lt": timezone.localdate()})
    )


class QuestionQuerySet(models.QuerySet):
    def visibles(self):
        return self.filter(filtre_questions_visibles())


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
    sujet = models.ForeignKey(
        "sujets.Sujet",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="questions",
        help_text=_("Facultatif : le sujet dont la question est tirée (« Quiz sur cette épreuve »)."),
    )
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

    objects = QuestionQuerySet.as_manager()

    class Meta:
        verbose_name = _("question")

    def __str__(self):
        return self.enonce[:80]

    def clean(self):
        if self.sujet_id and self.chapitre_id and self.sujet.matiere_id != self.chapitre.matiere_id:
            raise ValidationError({"sujet": _("Ce sujet n'est pas de la même matière que le chapitre.")})

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
        SUJET = "sujet", _("Quiz sur une épreuve")

    titre = models.CharField(max_length=200)
    mode = models.CharField(max_length=10, choices=Mode.choices)
    matiere = models.ForeignKey("catalogue.Matiere", on_delete=models.PROTECT, related_name="quiz")
    chapitre = models.ForeignKey(
        "catalogue.Chapitre", on_delete=models.PROTECT, null=True, blank=True, related_name="quiz"
    )
    sujet = models.ForeignKey("sujets.Sujet", on_delete=models.SET_NULL, null=True, blank=True, related_name="quiz")
    nb_questions = models.PositiveSmallIntegerField(_("nombre de questions"), default=10)
    questions = models.ManyToManyField(Question, related_name="quiz")

    class Meta:
        verbose_name = _("quiz")
        verbose_name_plural = _("quiz")

    def __str__(self):
        return self.titre


class ExamenBlancQuerySet(models.QuerySet):
    def visibles(self):
        # Un examen blanc reprend un sujet : il n'est visible que si ce sujet est publié (CDC 4.2).
        return self.filter(publie=True, sujet__statut="publie", sujet__session__date_fin_officielle__lt=timezone.localdate())


class ExamenBlanc(models.Model):
    titre = models.CharField(max_length=200)
    sujet = models.ForeignKey("sujets.Sujet", on_delete=models.PROTECT, related_name="examens_blancs")
    duree = models.PositiveSmallIntegerField(_("durée (minutes)"), help_text=_("Durée réelle de l'épreuve (CDC 3.5)."))
    bareme = models.TextField(_("consignes"), blank=True, help_text=_("Affichées avant le départ du minuteur."))
    questions = models.ManyToManyField(Question, related_name="examens_blancs", blank=True)
    points_qcm = models.PositiveSmallIntegerField(
        _("points de la partie QCM"), default=0, help_text=_("La partie QCM est notée sur ces points ; 0 s'il n'y en a pas.")
    )
    publie = models.BooleanField(_("publié"), default=False)

    objects = ExamenBlancQuerySet.as_manager()

    class Meta:
        verbose_name = _("examen blanc")
        verbose_name_plural = _("examens blancs")

    def __str__(self):
        return self.titre

    @property
    def points_total(self):
        return self.points_qcm + sum(critere.points for critere in self.criteres.all())

    def clean(self):
        if self.publie and self.sujet_id and self.sujet.statut != "publie":
            raise ValidationError({"publie": _("Publiez d'abord le sujet : un examen blanc ne peut pas le dévoiler avant.")})


class CritereBareme(models.Model):
    """Partie rédactionnelle : l'étudiant s'auto-évalue critère par critère, corrigé sous les yeux (CDC 3.5)."""

    examen_blanc = models.ForeignKey(ExamenBlanc, on_delete=models.CASCADE, related_name="criteres")
    libelle = models.CharField(_("critère"), max_length=200)
    points = models.PositiveSmallIntegerField()
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = _("critère du barème")
        verbose_name_plural = _("critères du barème")
        ordering = ["ordre", "pk"]

    def __str__(self):
        return f"{self.libelle} ({self.points})"


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
