from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.paginator import Paginator
from django.db.models import Count, Max, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from catalogue.models import Matiere
from sujets.models import Sujet

from . import services
from .forms import DiscussionForm, ReponseForm, SignalementForm
from .models import Discussion, Reponse


def forum_ouvert(vue):
    @wraps(vue)
    def enveloppe(request, *args, **kwargs):
        if not settings.FONCTIONNALITES["forum"]:
            raise Http404
        return vue(request, *args, **kwargs)

    return enveloppe


def discussions_visibles():
    return Discussion.objects.visibles().select_related("auteur", "matiere", "sujet__session")


@forum_ouvert
def accueil(request):
    """Les matières de sa spécialité (sans profil : toutes), avec leur activité."""
    matieres = Matiere.objects.select_related("examen")
    profil = getattr(request.user, "profil", None)
    if profil:
        matieres = matieres.filter(specialites=profil.specialite)
    visibles = Q(discussions__in=Discussion.objects.visibles())
    matieres = (
        matieres.annotate(nb=Count("discussions", filter=visibles, distinct=True), activite=Max("discussions__derniere_activite", filter=visibles))
        .order_by("examen__code", "-nb", "nom")
        .distinct()
    )
    recentes = discussions_visibles()
    if profil:
        recentes = recentes.filter(matiere__specialites=profil.specialite).distinct()
    return render(request, "forum/accueil.html", {"matieres": matieres, "recentes": recentes[:8]})


@forum_ouvert
def matiere(request, pk):
    matiere = get_object_or_404(Matiere.objects.select_related("examen"), pk=pk)
    # order_by explicite : avec un Count, l'ordre du Meta n'est plus appliqué.
    discussions = (
        discussions_visibles()
        .filter(matiere=matiere)
        .annotate(nb_reponses=Count("reponses", filter=Q(reponses__masquee=False)))
        .order_by("-derniere_activite")
    )
    sujet = None
    if request.GET.get("sujet", "").isdigit():
        sujet = get_object_or_404(Sujet.objects.publies(), pk=request.GET["sujet"], matiere=matiere)
        discussions = discussions.filter(sujet=sujet)
    if request.GET.get("sans_reponse"):
        discussions = discussions.filter(nb_reponses=0)
    page = Paginator(discussions, 20).get_page(request.GET.get("page"))
    return render(request, "forum/matiere.html", {"matiere": matiere, "sujet": sujet, "page": page})


@forum_ouvert
@login_required
def nouvelle(request, pk):
    matiere = get_object_or_404(Matiere, pk=pk)
    sujet = None
    identifiant = request.POST.get("sujet") or request.GET.get("sujet") or ""
    if identifiant.isdigit():
        sujet = get_object_or_404(Sujet.objects.publies().select_related("session"), pk=identifiant, matiere=matiere)
    form = DiscussionForm(request.POST or None)
    if form.is_valid():
        if not services.peut_ecrire(request.user):
            form.add_error(None, _("Vous avez beaucoup écrit aujourd'hui : revenez demain."))
        else:
            discussion = form.save(commit=False)
            discussion.matiere, discussion.sujet, discussion.auteur = matiere, sujet, request.user
            discussion.save()
            return redirect("forum:discussion", pk=discussion.pk)
    return render(request, "forum/nouvelle.html", {"form": form, "matiere": matiere, "sujet": sujet})


@forum_ouvert
def discussion(request, pk):
    discussion = get_object_or_404(discussions_visibles(), pk=pk)
    form = ReponseForm(request.POST or None)
    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect_to_login(request.path)
        if form.is_valid():
            if not services.peut_ecrire(request.user):
                form.add_error(None, _("Vous avez beaucoup écrit aujourd'hui : revenez demain."))
            else:
                reponse = services.repondre(discussion, request.user, form.cleaned_data["texte"])
                return redirect(f"{request.path}#reponse-{reponse.pk}")
    reponses = discussion.reponses.filter(masquee=False).select_related("auteur")
    return render(
        request,
        "forum/discussion.html",
        {"discussion": discussion, "reponses": reponses, "form": form, "est_auteur": request.user == discussion.auteur},
    )


@forum_ouvert
@login_required
@require_POST
def accepter(request, pk):
    """L'auteur de la question indique la réponse qui l'a aidé (une seule ; un nouveau clic la retire)."""
    reponse = get_object_or_404(Reponse.objects.filter(masquee=False), pk=pk, discussion__in=Discussion.objects.visibles())
    discussion = reponse.discussion
    if discussion.auteur != request.user:
        raise Http404
    discussion.reponse_acceptee = None if discussion.reponse_acceptee_id == reponse.pk else reponse
    discussion.save(update_fields=["reponse_acceptee"])
    return redirect(reverse("forum:discussion", args=[discussion.pk]) + f"#reponse-{reponse.pk}")


@forum_ouvert
@login_required
@require_POST
def signaler(request, type_cible, pk):
    if type_cible not in ("discussion", "reponse"):
        raise Http404
    if type_cible == "discussion":
        cible = get_object_or_404(Discussion.objects.visibles(), pk=pk)
        discussion = cible
    else:
        cible = get_object_or_404(Reponse.objects.filter(masquee=False, discussion__in=Discussion.objects.visibles()), pk=pk)
        discussion = cible.discussion
    form = SignalementForm(request.POST)
    if not form.is_valid():
        messages.error(request, _("Indiquez en quelques mots pourquoi vous signalez ce message."))
    elif services.signaler(request.user, cible, form.cleaned_data["motif"]):
        messages.success(request, _("Merci, un modérateur va regarder ce message."))
    else:
        messages.info(request, _("Vous avez déjà signalé ce message."))
    # Masquée par ce signalement, la discussion n'est plus affichable : retour à la matière.
    if not Discussion.objects.visibles().filter(pk=discussion.pk).exists():
        return redirect("forum:matiere", pk=discussion.matiere_id)
    return redirect("forum:discussion", pk=discussion.pk)


def message_de_l_auteur(request, type_cible, pk):
    """Sa propre question ou réponse, visible : on ne retouche pas un message que la modération a masqué."""
    if type_cible == "discussion":
        return get_object_or_404(Discussion.objects.visibles(), pk=pk, auteur=request.user)
    if type_cible == "reponse":
        return get_object_or_404(
            Reponse.objects.filter(masquee=False, discussion__in=Discussion.objects.visibles()), pk=pk, auteur=request.user
        )
    raise Http404


@forum_ouvert
@login_required
def modifier(request, type_cible, pk):
    message = message_de_l_auteur(request, type_cible, pk)
    discussion = message if type_cible == "discussion" else message.discussion
    classe = DiscussionForm if type_cible == "discussion" else ReponseForm
    form = classe(request.POST or None, instance=message)
    if form.is_valid():
        message = form.save(commit=False)
        message.modifie_le = timezone.now()
        message.save()
        ancre = "" if type_cible == "discussion" else f"#reponse-{message.pk}"
        return redirect(reverse("forum:discussion", args=[discussion.pk]) + ancre)
    return render(request, "forum/modifier.html", {"form": form, "discussion": discussion, "type_cible": type_cible})


@forum_ouvert
@login_required
@require_POST
def supprimer(request, type_cible, pk):
    message = message_de_l_auteur(request, type_cible, pk)
    if type_cible == "reponse":
        discussion = message.discussion
        message.delete()
        messages.success(request, _("Votre réponse est supprimée."))
        return redirect("forum:discussion", pk=discussion.pk)
    # Une question à laquelle d'autres ont répondu ne disparaît pas : ce serait effacer leurs réponses.
    if message.reponses.exclude(auteur=request.user).exists():
        messages.error(request, _("D'autres personnes ont répondu : la question reste. Modifiez-la, ou demandez au modérateur."))
        return redirect("forum:discussion", pk=message.pk)
    matiere = message.matiere_id
    message.delete()
    messages.success(request, _("Votre question est supprimée."))
    return redirect("forum:matiere", pk=matiere)
