"""Quiz rapide et révision des erreurs (CDC 3.4)."""

from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import OuterRef, Subquery
from django.utils import timezone
from django.utils.translation import gettext as _

from paiements.acces import a_un_abonnement_actif

from .models import Question, Quiz, ReponseQuestion, Tentative

QUESTIONS_PAR_QUIZ = 10


def questions_publiees():
    return Question.objects.filter(publiee=True)


def quiz_restants_aujourd_hui(utilisateur):
    """None = illimité. CDC 3.8 : quiz limités par jour pour l'offre gratuite, illimités en Premium (V3)."""
    if not settings.PAIEMENT_ACTIF or utilisateur.is_staff or a_un_abonnement_actif(utilisateur):
        return None
    faits = Tentative.objects.filter(
        utilisateur=utilisateur, quiz__isnull=False, debut__date=timezone.localdate()
    ).count()
    return max(settings.QUIZ_GRATUITS_PAR_JOUR - faits, 0)


def erreurs_a_reviser(utilisateur):
    """Questions dont la dernière réponse de l'étudiant était fausse (une bonne réponse ensuite les retire)."""
    derniere = (
        ReponseQuestion.objects.filter(tentative__utilisateur=utilisateur, question=OuterRef("pk"))
        .order_by("-repondu_le", "-pk")
        .values("correcte")[:1]
    )
    return questions_publiees().annotate(derniere_correcte=Subquery(derniere)).filter(derniere_correcte=False)


@transaction.atomic
def creer_tentative(utilisateur, questions, mode, matiere, chapitre=None):
    questions = list(questions)
    if not questions:
        return None
    titre = chapitre.titre if chapitre else matiere.nom
    quiz = Quiz.objects.create(
        titre=titre if mode == Quiz.Mode.RAPIDE else _("Révision : %(titre)s") % {"titre": titre},
        mode=mode,
        matiere=matiere,
        chapitre=chapitre,
        nb_questions=len(questions),
    )
    quiz.questions.set(questions)
    return Tentative.objects.create(
        utilisateur=utilisateur, quiz=quiz, reponses={"ordre": [question.pk for question in questions]}
    )


def lancer_quiz_rapide(utilisateur, matiere, chapitre=None):
    questions = questions_publiees().filter(chapitre__matiere=matiere)
    if chapitre:
        questions = questions.filter(chapitre=chapitre)
    return creer_tentative(utilisateur, questions.order_by("?")[:QUESTIONS_PAR_QUIZ], Quiz.Mode.RAPIDE, matiere, chapitre)


def lancer_revision(utilisateur, matiere):
    questions = erreurs_a_reviser(utilisateur).filter(chapitre__matiere=matiere).order_by("?")[:QUESTIONS_PAR_QUIZ]
    return creer_tentative(utilisateur, questions, Quiz.Mode.REVISION, matiere)


def prochaine_question(tentative):
    deja = set(tentative.reponses_donnees.values_list("question_id", flat=True))
    for identifiant in tentative.ordre:
        if identifiant not in deja:
            return Question.objects.prefetch_related("choix").get(pk=identifiant)
    return None


def terminer(tentative):
    """Note sur 20 (CDC 3.5 : note calculée immédiatement)."""
    total = len(tentative.ordre)
    justes = tentative.reponses_donnees.filter(correcte=True).count()
    tentative.note = (Decimal(justes * 20) / Decimal(total)).quantize(Decimal("0.01"), ROUND_HALF_UP) if total else None
    tentative.fin = timezone.now()
    tentative.save(update_fields=["note", "fin"])
