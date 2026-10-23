"""Espace établissement (CDC 10.6) : validation des étudiants, épreuves internes, résultats partagés."""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Max, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from accounts.models import Consentement, ProfilEtude
from entrainement.models import ReponseQuestion, Tentative
from sujets.views import envoyer_pdf

from .acces import epreuves_visibles, etablissement_gere_par, etablissement_valide_de
from .forms import EpreuveInterneForm
from .models import EpreuveInterne, a_une_convention_active


def responsable_requis(vue):
    """Réservé au responsable de l'établissement ; la vue reçoit son établissement."""

    @login_required
    @wraps(vue)
    def enveloppe(request, *args, **kwargs):
        etablissement = etablissement_gere_par(request.user)
        if etablissement is None:
            raise PermissionDenied
        return vue(request, etablissement, *args, **kwargs)

    return enveloppe


def resultats_partages(etablissement):
    """CDC 10.6 : seuls les étudiants validés qui ont accepté le partage, révocable à tout moment."""
    partageurs = Consentement.objects.filter(
        objet=Consentement.Objet.PARTAGE_ETABLISSEMENT, date_revocation__isnull=True
    ).values("utilisateur")
    profils = (
        ProfilEtude.objects.filter(etablissement=etablissement, etablissement_valide_le__isnull=False, utilisateur__in=partageurs)
        .select_related("utilisateur", "specialite")
        .order_by("utilisateur__last_name", "utilisateur__first_name")
    )
    lignes = []
    for profil in profils:
        tentatives = Tentative.objects.filter(utilisateur=profil.utilisateur, fin__isnull=False)
        reponses = ReponseQuestion.objects.filter(tentative__utilisateur=profil.utilisateur).aggregate(
            total=Count("pk"), justes=Count("pk", filter=Q(correcte=True))
        )
        lignes.append({
            "profil": profil,
            "quiz": tentatives.filter(quiz__isnull=False).count(),
            "examens": tentatives.filter(examen_blanc__isnull=False).count(),
            "reussite": round(100 * reponses["justes"] / reponses["total"]) if reponses["total"] else None,
            "derniere": tentatives.aggregate(derniere=Max("fin"))["derniere"],
        })
    return lignes


@responsable_requis
def espace(request, etablissement):
    profils = ProfilEtude.objects.filter(etablissement=etablissement).select_related("utilisateur", "specialite")
    return render(
        request,
        "partenaires/espace.html",
        {
            "etablissement": etablissement,
            "convention": a_une_convention_active(etablissement),
            "en_attente": profils.filter(etablissement_valide_le__isnull=True).order_by("utilisateur__date_joined"),
            "valides": profils.filter(etablissement_valide_le__isnull=False).order_by("utilisateur__last_name"),
            "resultats": resultats_partages(etablissement),
            "epreuves": etablissement.epreuves.select_related("matiere"),
        },
    )


@responsable_requis
@require_POST
def valider(request, etablissement, pk):
    profil = get_object_or_404(ProfilEtude, pk=pk, etablissement=etablissement)
    profil.etablissement_valide_le = timezone.now()
    profil.etablissement_valide_par = request.user
    profil.save(update_fields=["etablissement_valide_le", "etablissement_valide_par"])
    messages.success(request, _("%(nom)s est validé(e) comme étudiant(e) de l'établissement.") % {"nom": profil.utilisateur})
    return redirect("partenaires:espace")


@responsable_requis
@require_POST
def retirer(request, etablissement, pk):
    """L'étudiant n'est pas (ou plus) de l'établissement : il perd l'accès aux épreuves internes."""
    profil = get_object_or_404(ProfilEtude, pk=pk, etablissement=etablissement)
    profil.etablissement = None
    profil.save()
    messages.success(request, _("%(nom)s n'est plus rattaché(e) à l'établissement.") % {"nom": profil.utilisateur})
    return redirect("partenaires:espace")


@responsable_requis
def deposer(request, etablissement):
    convention = a_une_convention_active(etablissement)
    form = EpreuveInterneForm(request.POST or None, request.FILES or None, convention_active=convention)
    if form.is_valid():
        epreuve = form.save(commit=False)
        epreuve.etablissement = etablissement
        epreuve.deposee_par = request.user
        epreuve.save()
        messages.success(request, _("Épreuve déposée."))
        return redirect("partenaires:espace")
    return render(request, "partenaires/deposer.html", {"form": form, "etablissement": etablissement, "convention": convention})


@responsable_requis
@require_POST
def basculer_publication(request, etablissement, pk):
    epreuve = get_object_or_404(EpreuveInterne, pk=pk, etablissement=etablissement)
    if not epreuve.publiee and not a_une_convention_active(etablissement):
        messages.error(request, _("Publication impossible sans convention de partenariat active."))
    else:
        epreuve.publiee = not epreuve.publiee
        epreuve.save(update_fields=["publiee"])
    return redirect("partenaires:espace")


@responsable_requis
@require_POST
def supprimer_epreuve(request, etablissement, pk):
    epreuve = get_object_or_404(EpreuveInterne, pk=pk, etablissement=etablissement)
    epreuve.fichier.delete(save=False)
    epreuve.delete()
    messages.success(request, _("Épreuve supprimée."))
    return redirect("partenaires:espace")


@login_required
def mes_epreuves(request):
    """Côté étudiant : les épreuves internes de son établissement, une fois validé."""
    etablissement = etablissement_valide_de(request.user)
    profil = getattr(request.user, "profil", None)
    return render(
        request,
        "partenaires/mes_epreuves.html",
        {
            "etablissement": etablissement,
            "declare": profil.etablissement if profil else None,
            "epreuves": epreuves_visibles(etablissement) if etablissement else [],
        },
    )


@login_required
def pdf_epreuve(request, pk):
    epreuve = get_object_or_404(EpreuveInterne.objects.select_related("etablissement"), pk=pk)
    responsable = etablissement_gere_par(request.user) == epreuve.etablissement
    etudiant = etablissement_valide_de(request.user) == epreuve.etablissement
    if not responsable and not (etudiant and epreuves_visibles(epreuve.etablissement).filter(pk=pk).exists()):
        raise Http404
    return envoyer_pdf(request, epreuve.fichier, f"{slugify(epreuve.titre)}-{epreuve.annee_academique}.pdf")
