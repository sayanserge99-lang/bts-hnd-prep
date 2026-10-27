from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from paiements.acces import lit_le_corrige_complet

from . import examen_blanc
from .models import ExamenBlanc, Question, Tentative


def refuser_sans_acces(request):
    messages.error(request, _("Les examens blancs sont réservés aux abonnés du Pass session."))
    return redirect("entrainement:accueil")


@login_required
def liste(request):
    return render(
        request,
        "entrainement/examens/liste.html",
        {
            "examens": examen_blanc.examens_proposes(request.user),
            "acces": examen_blanc.peut_passer_un_examen(request.user),
            "passees": Tentative.objects.filter(utilisateur=request.user, examen_blanc__isnull=False)
            .select_related("examen_blanc")
            .order_by("-debut")[:5],
        },
    )


@login_required
def consignes(request, pk):
    examen = get_object_or_404(ExamenBlanc.objects.visibles().select_related("sujet__session"), pk=pk)
    en_cours = Tentative.objects.filter(utilisateur=request.user, examen_blanc=examen, fin__isnull=True).first()
    return render(request, "entrainement/examens/consignes.html", {"examen": examen, "en_cours": en_cours})


@login_required
@require_POST
def demarrer(request, pk):
    examen = get_object_or_404(ExamenBlanc.objects.visibles(), pk=pk)
    if not examen_blanc.peut_passer_un_examen(request.user):
        return refuser_sans_acces(request)
    return redirect("entrainement:epreuve", pk=examen_blanc.demarrer(request.user, examen).pk)


def tentative_de(request, pk):
    return get_object_or_404(
        Tentative.objects.select_related("examen_blanc__sujet__session"),
        pk=pk,
        utilisateur=request.user,
        examen_blanc__isnull=False,
    )


@login_required
def epreuve(request, pk):
    tentative = tentative_de(request, pk)
    examen_blanc.cloturer_si_expiree(tentative)
    if tentative.fin is not None:
        return redirect("entrainement:auto_evaluation", pk=tentative.pk)
    brouillon = tentative.reponses.get("brouillon", {})
    questions = list(Question.objects.filter(pk__in=tentative.ordre).prefetch_related("choix").order_by("pk"))
    marquees = tentative.reponses.get(examen_blanc.CHAMP_MARQUEES, [])
    for question in questions:
        # Réponses déjà enregistrées : la page rechargée après une coupure les retrouve cochées.
        question.deja = brouillon.get(str(question.pk), [] if question.type != Question.Type.REPONSE_COURTE else "")
        question.repondue = bool(question.deja)
        question.marquee = question.pk in marquees
    return render(
        request,
        "entrainement/examens/epreuve.html",
        {
            "tentative": tentative,
            "examen": tentative.examen_blanc,
            "questions": questions,
            # Le navigateur compte à rebours depuis cette valeur : pas de dépendance à l'horloge du téléphone.
            "secondes_restantes": examen_blanc.secondes_restantes(tentative),
            "copie": tentative.reponses.get(examen_blanc.CHAMP_COPIE, ""),
            "marquees": ",".join(str(pk) for pk in marquees),
        },
    )


@login_required
@require_POST
def enregistrer(request, pk):
    """Sauvegarde continue (HTMX) : renvoie l'heure de la dernière sauvegarde, ou 409 si l'épreuve est close."""
    tentative = tentative_de(request, pk)
    if not examen_blanc.enregistrer(tentative, request.POST):
        return HttpResponse(_("Épreuve terminée : réponses non enregistrées."), status=409)
    return render(request, "entrainement/examens/_etat_sauvegarde.html", {"heure": timezone.localtime()})


@login_required
@require_POST
def rendre(request, pk):
    tentative = tentative_de(request, pk)
    examen_blanc.rendre(tentative, request.POST)
    return redirect("entrainement:auto_evaluation", pk=tentative.pk)


@login_required
def auto_evaluation(request, pk):
    tentative = tentative_de(request, pk)
    examen_blanc.cloturer_si_expiree(tentative)
    if tentative.fin is None:
        return redirect("entrainement:epreuve", pk=tentative.pk)
    examen = tentative.examen_blanc
    if request.method == "POST":
        examen_blanc.auto_evaluer(tentative, request.POST)
        return redirect("entrainement:resultat_examen", pk=tentative.pk)
    reponses = tentative.reponses_donnees.select_related("question").prefetch_related("question__choix").order_by("question_id")
    deja = tentative.reponses.get("auto_evaluation", {})
    criteres = list(examen.criteres.all())
    for critere in criteres:
        critere.deja = deja.get(str(critere.pk), "")
    return render(
        request,
        "entrainement/examens/auto_evaluation.html",
        {
            "tentative": tentative,
            "examen": examen,
            "reponses": reponses,
            "criteres": criteres,
            # Le corrigé n'apparaît qu'une fois la copie rendue.
            "corriges": examen.sujet.corriges.visibles(),
            "complet": lit_le_corrige_complet(request.user),
            "copie": tentative.reponses.get(examen_blanc.CHAMP_COPIE, ""),
        },
    )


@login_required
def resultat(request, pk):
    tentative = tentative_de(request, pk)
    if tentative.note is None:
        return redirect("entrainement:auto_evaluation", pk=tentative.pk)
    examen = tentative.examen_blanc
    auto = tentative.reponses.get("auto_evaluation", {})
    return render(
        request,
        "entrainement/examens/resultat.html",
        {
            "tentative": tentative,
            "examen": examen,
            "lignes": [(critere, auto.get(str(critere.pk), "0")) for critere in examen.criteres.all()],
        },
    )
