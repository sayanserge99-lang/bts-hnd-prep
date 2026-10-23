from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Case, Count, Prefetch, Q, When
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from catalogue.models import Chapitre, Matiere
from sujets.views import est_requete_htmx

from . import progression, quiz
from .correction import est_correcte
from .models import Question, Quiz, ReponseQuestion, Tentative


def matieres_proposees(utilisateur):
    """Toutes les matières de la spécialité de l'étudiant (sans profil : toutes), avec leurs chapitres.

    Celles qui ont déjà des questions publiées passent en premier ; les autres s'affichent « bientôt ».
    """
    matieres = Matiere.objects.select_related("examen")
    profil = getattr(utilisateur, "profil", None)
    if profil:
        matieres = matieres.filter(specialites=profil.specialite)
    chapitres = Chapitre.objects.annotate(nb=Count("questions", filter=Q(questions__publiee=True))).filter(nb__gt=0)
    return (
        matieres.annotate(nb_questions=Count("chapitres__questions", filter=Q(chapitres__questions__publiee=True), distinct=True))
        .prefetch_related(Prefetch("chapitres", queryset=chapitres.order_by("ordre"), to_attr="chapitres_actifs"))
        .order_by("examen__code", Case(When(nb_questions=0, then=1), default=0), "nom")
        .distinct()
    )


@login_required
def accueil(request):
    erreurs = {
        ligne["chapitre__matiere"]: ligne["n"]
        for ligne in quiz.erreurs_a_reviser(request.user).values("chapitre__matiere").annotate(n=Count("pk"))
    }
    matieres = list(matieres_proposees(request.user))
    for matiere in matieres:
        matiere.nb_erreurs = erreurs.get(matiere.pk, 0)
    return render(
        request,
        "entrainement/accueil.html",
        {
            "matieres": matieres,
            "restants": quiz.quiz_restants_aujourd_hui(request.user),
            "dernieres": Tentative.objects.filter(utilisateur=request.user, quiz__isnull=False, fin__isnull=False)
            .select_related("quiz")
            .order_by("-fin")[:5],
        },
    )


@login_required
@require_POST
def lancer(request):
    matiere = get_object_or_404(Matiere, pk=request.POST.get("matiere"))
    restants = quiz.quiz_restants_aujourd_hui(request.user)
    if restants == 0:
        messages.error(request, _("Vous avez fait tous vos quiz gratuits du jour. Revenez demain ou passez au Pass session."))
        return redirect("entrainement:accueil")

    if request.POST.get("mode") == Quiz.Mode.REVISION:
        tentative = quiz.lancer_revision(request.user, matiere)
    else:
        chapitre = None
        if request.POST.get("chapitre"):
            chapitre = get_object_or_404(Chapitre, pk=request.POST["chapitre"], matiere=matiere)
        tentative = quiz.lancer_quiz_rapide(request.user, matiere, chapitre)
    if tentative is None:
        messages.info(request, _("Aucune question disponible pour ce choix pour le moment."))
        return redirect("entrainement:accueil")
    return redirect("entrainement:tentative", pk=tentative.pk)


def tentative_de(request, pk):
    # Une tentative n'est visible que par l'étudiant qui l'a commencée.
    return get_object_or_404(Tentative.objects.select_related("quiz__matiere"), pk=pk, utilisateur=request.user, quiz__isnull=False)


@login_required
def tentative(request, pk):
    tentative = tentative_de(request, pk)
    question = quiz.prochaine_question(tentative)
    if question is None:
        if tentative.fin is None:
            quiz.terminer(tentative)
        return redirect("entrainement:resultat", pk=tentative.pk)
    return render(request, "entrainement/question.html", contexte_question(tentative, question))


def contexte_question(tentative, question, **autres):
    return {
        "tentative": tentative,
        "question": question,
        "numero": tentative.ordre.index(question.pk) + 1,
        "total": len(tentative.ordre),
        **autres,
    }


def lire_reponse(request, question):
    """Réponse envoyée par le formulaire, ou None si elle est vide ou incohérente avec le type de question."""
    if question.type == Question.Type.REPONSE_COURTE:
        texte = request.POST.get("reponse", "").strip()
        return texte or None
    permis = {str(pk) for pk in question.choix.values_list("pk", flat=True)}
    cochees = sorted({int(valeur) for valeur in request.POST.getlist("choix") if valeur in permis})
    if not cochees or (question.type != Question.Type.CHOIX_MULTIPLE and len(cochees) != 1):
        return None
    return cochees


@login_required
@require_POST
def repondre(request, pk):
    tentative = tentative_de(request, pk)
    question = quiz.prochaine_question(tentative)
    # On ne répond qu'à la question en cours, dans l'ordre : pas de retour en arrière après la correction.
    if question is None or str(question.pk) != request.POST.get("question"):
        return redirect("entrainement:tentative", pk=tentative.pk)

    reponse = lire_reponse(request, question)
    if reponse is None:
        contexte = contexte_question(tentative, question, erreur=_("Choisissez une réponse avant de valider."))
        gabarit = "entrainement/_formulaire_question.html" if est_requete_htmx(request) else "entrainement/question.html"
        return render(request, gabarit, contexte)
    try:
        donnee = ReponseQuestion.objects.create(
            tentative=tentative, question=question, reponse=reponse, correcte=est_correcte(question, reponse)
        )
    except IntegrityError:
        # Double envoi (connexion lente) : la première réponse compte.
        return redirect("entrainement:tentative", pk=tentative.pk)

    derniere = quiz.prochaine_question(tentative) is None
    if derniere:
        quiz.terminer(tentative)
    contexte = contexte_question(tentative, question, correction=donnee, derniere=derniere)
    gabarit = "entrainement/_correction.html" if est_requete_htmx(request) else "entrainement/question.html"
    return render(request, gabarit, contexte)


@login_required
def progression_etudiant(request):
    """CDC 3.6 : historique, taux de réussite par matière et par chapitre, points faibles, compte à rebours."""
    completes = progression.voit_les_statistiques_completes(request.user)
    chapitres = progression.taux_par_chapitre(request.user) if completes else []
    session = progression.prochaine_session(request.user)
    historique = Paginator(
        Tentative.objects.filter(utilisateur=request.user, fin__isnull=False)
        .select_related("quiz__matiere", "examen_blanc__sujet__matiere")
        .order_by("-fin"),
        20,
    ).get_page(request.GET.get("page"))
    return render(
        request,
        "entrainement/progression.html",
        {
            "completes": completes,
            "matieres": progression.taux_par_matiere(request.user),
            "chapitres": chapitres,
            "points_faibles": progression.points_faibles(request.user, chapitres) if completes else [],
            "reponses_minimum": progression.REPONSES_MINIMUM,
            "session": session,
            "jours": progression.jours_restants(session),
            "historique": historique,
        },
    )


@login_required
def resultat(request, pk):
    tentative = tentative_de(request, pk)
    if tentative.fin is None:
        return redirect("entrainement:tentative", pk=tentative.pk)
    reponses = tentative.reponses_donnees.select_related("question__chapitre").order_by("pk")
    return render(
        request,
        "entrainement/resultat.html",
        {
            "tentative": tentative,
            "reponses": reponses,
            "justes": sum(reponse.correcte for reponse in reponses),
            "a_reviser": any(not reponse.correcte for reponse in reponses),
        },
    )
