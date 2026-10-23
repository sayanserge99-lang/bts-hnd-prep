from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.mail import mail_admins, send_mail
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils.translation import gettext as _

from sujets.models import Corrige, Sujet

from .forms import DemandeRetraitForm, EnvoiSujetForm, PropositionCorrigeForm


def adresse_ip(request):
    # Derrière Nginx, REMOTE_ADDR est celle de Nginx : l'adresse du visiteur est dans X-Real-IP,
    # que Nginx écrase toujours (deploy/nginx.conf). Sans proxy, cet en-tête serait falsifiable.
    if settings.DERRIERE_PROXY:
        return request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR", "")
    return request.META.get("REMOTE_ADDR", "")


def document_vise(request):
    """Le sujet ou le corrigé visé par ?sujet= ou ?corrige= (uniquement s'il est visible du public)."""
    for champ, documents in (("sujet", Sujet.objects.publies()), ("corrige", Corrige.objects.visibles())):
        identifiant = request.POST.get(champ) or request.GET.get(champ) or ""
        if identifiant.isdigit():
            document = documents.filter(pk=identifiant).first()
            if document:
                return champ, document
    return None, None


def demande_retrait(request):
    champ, document = document_vise(request)
    if document is None:
        # Sans document précis, la page explique comment faire la demande depuis la fiche du sujet.
        return render(request, "communaute/demande_retrait.html", {"form": None})

    form = DemandeRetraitForm(request.POST or None, initial={champ: document})
    if form.is_valid():
        # Le masquage est immédiat (CDC 10.1) : on limite les demandes pour éviter qu'un tiers masque tout.
        cle = f"demandes-retrait:{adresse_ip(request)}"
        if cache.get(cle, 0) >= settings.DEMANDES_RETRAIT_PAR_JOUR:
            form.add_error(None, _("Trop de demandes envoyées aujourd'hui. Écrivez-nous depuis la page Contact."))
        else:
            demande = form.save()
            cache.set(cle, cache.get(cle, 0) + 1, timeout=24 * 60 * 60)
            send_mail(
                _("Votre demande de retrait a bien été reçue"),
                render_to_string("communaute/email_accuse_retrait.txt", {"demande": demande}),
                None,
                [demande.demandeur_email],
                fail_silently=True,
            )
            mail_admins(f"Demande de retrait : {document}", demande.motif, fail_silently=True)
            return redirect("demande_retrait_recue")
    return render(request, "communaute/demande_retrait.html", {"form": form, "document": document})


def contributions_ouvertes(vue):
    """Les pages de contribution n'existent que si la fonctionnalité est ouverte (settings.FONCTIONNALITES)."""

    @wraps(vue)
    def enveloppe(request, *args, **kwargs):
        if not settings.FONCTIONNALITES["contributions"]:
            raise Http404
        return vue(request, *args, **kwargs)

    return login_required(enveloppe)


@contributions_ouvertes
def envoyer_sujet(request):
    """CDC 3.7 : un étudiant ou un enseignant envoie un sujet, qui passe en file de modération."""
    profil = getattr(request.user, "profil", None)
    initial = {"specialite": profil.specialite} if profil else {}
    form = EnvoiSujetForm(request.POST or None, request.FILES or None, utilisateur=request.user, initial=initial)
    if form.is_valid():
        form.save()
        messages.success(request, _("Merci ! Votre sujet est en attente de vérification par un modérateur."))
        return redirect("communaute:mes_contributions")
    return render(request, "communaute/envoyer_sujet.html", {"form": form, "jours_par_sujet": settings.JOURS_OFFERTS_PAR_SUJET})


@contributions_ouvertes
def proposer_corrige(request, pk):
    sujet = get_object_or_404(Sujet.objects.publies().select_related("session", "matiere"), pk=pk)
    form = PropositionCorrigeForm(request.POST or None, request.FILES or None, utilisateur=request.user, sujet=sujet)
    if form.is_valid():
        form.save()
        messages.success(request, _("Merci ! Votre corrigé sera relu par un modérateur avant d'être publié."))
        return redirect("communaute:mes_contributions")
    return render(request, "communaute/proposer_corrige.html", {"form": form, "sujet": sujet})


@contributions_ouvertes
def mes_contributions(request):
    """CDC 2 : suivi de ses contributions (statut, motif d'un rejet, jours offerts)."""
    return render(
        request,
        "communaute/mes_contributions.html",
        {
            "contributions": request.user.contributions.select_related("matiere__examen", "sujet_vise__session"),
            "jours_par_sujet": settings.JOURS_OFFERTS_PAR_SUJET,
        },
    )
