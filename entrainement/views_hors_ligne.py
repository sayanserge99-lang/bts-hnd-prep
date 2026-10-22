"""Quiz hors ligne (CDC 4) : téléchargés avec leur correction, rejoués sans réseau, puis synchronisés."""

import json

from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from catalogue.models import Chapitre, Matiere
from sujets.rendu import rendre, rendre_ligne

from . import quiz
from .correction import est_correcte
from .models import Question, ReponseQuestion, Tentative


def paquet(tentative):
    """Le quiz avec ses réponses : sans réseau, la correction se fait sur le téléphone.

    Ce n'est pas un risque de fraude (questions d'entraînement) ; au retour du réseau,
    le serveur recorrige tout et ne se fie jamais au téléphone.
    """
    questions = Question.objects.filter(pk__in=tentative.ordre).prefetch_related("choix")
    par_id = {question.pk: question for question in questions}
    return {
        "tentative": tentative.pk,
        "titre": tentative.quiz.titre,
        "matiere": str(tentative.quiz.matiere.nom),
        "telecharge_le": timezone.now().isoformat(),
        "url_synchro": reverse("entrainement:synchroniser_hors_ligne", args=[tentative.pk]),
        "questions": [
            {
                "id": question.pk,
                "type": question.type,
                "enonce": str(rendre(question.enonce)),
                "choix": [
                    {"id": choix.pk, "texte": str(rendre_ligne(choix.texte)), "correct": choix.est_correct}
                    for choix in question.choix.all()
                ],
                "acceptees": [r.strip() for r in question.reponse_attendue.split("|") if r.strip()],
                "explication": str(rendre(question.explication)),
            }
            for question in (par_id[identifiant] for identifiant in tentative.ordre)
        ],
    }


@login_required
@require_POST
def telecharger_quiz(request):
    matiere = get_object_or_404(Matiere, pk=request.POST.get("matiere"))
    chapitre = None
    if request.POST.get("chapitre"):
        chapitre = get_object_or_404(Chapitre, pk=request.POST["chapitre"], matiere=matiere)
    # Un quiz téléchargé compte comme un quiz joué (limite quotidienne de l'offre gratuite).
    if quiz.quiz_restants_aujourd_hui(request.user) == 0:
        return JsonResponse({"erreur": _("Vous avez fait tous vos quiz gratuits du jour.")}, status=403)
    tentative = quiz.lancer_quiz_rapide(request.user, matiere, chapitre)
    if tentative is None:
        return JsonResponse({"erreur": _("Aucune question disponible pour ce choix pour le moment.")}, status=404)
    return JsonResponse(paquet(tentative))


def reponse_valide(question, valeur):
    """Même contrôle qu'en ligne : seuls des choix de cette question, et le bon nombre."""
    if question.type == Question.Type.REPONSE_COURTE:
        if not isinstance(valeur, str):
            return None
        return valeur.strip()[:200] or None
    if not isinstance(valeur, list):
        return None
    permis = set(question.choix.values_list("pk", flat=True))
    cochees = sorted({int(v) for v in valeur if isinstance(v, int | str) and str(v).isdigit() and int(v) in permis})
    if not cochees or (question.type != Question.Type.CHOIX_MULTIPLE and len(cochees) != 1):
        return None
    return cochees


@login_required
@require_POST
def synchroniser(request, pk):
    """Réponses données sans réseau : corrigées ici (jamais la note du téléphone), une seule fois par question."""
    tentative = get_object_or_404(Tentative, pk=pk, utilisateur=request.user, quiz__isnull=False)
    try:
        reponses = json.loads(request.body)["reponses"]
        if not isinstance(reponses, dict):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        return JsonResponse({"erreur": "format"}, status=400)

    deja = set(tentative.reponses_donnees.values_list("question_id", flat=True))
    questions = Question.objects.filter(pk__in=tentative.ordre).prefetch_related("choix")
    for question in questions:
        if question.pk in deja or str(question.pk) not in reponses:
            continue
        valeur = reponse_valide(question, reponses[str(question.pk)])
        if valeur is None:
            continue
        try:
            ReponseQuestion.objects.create(
                tentative=tentative, question=question, reponse=valeur, correcte=est_correcte(question, valeur)
            )
        except IntegrityError:
            # Deux synchronisations en même temps : la première a gagné.
            continue

    repondues = tentative.reponses_donnees.count()
    if tentative.fin is None and repondues == len(tentative.ordre):
        quiz.terminer(tentative)
    tentative.refresh_from_db()
    return JsonResponse({"repondues": repondues, "note": str(tentative.note) if tentative.note is not None else None})
