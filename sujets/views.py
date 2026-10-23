from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.mail import mail_admins
from django.db.models import Case, Count, IntegerField, OuterRef, Q, Subquery, Value, When
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import content_disposition_header
from django.utils.text import slugify
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from catalogue.models import Examen, Matiere, SpecialiteMatiere

from communaute.models import Signalement
from paiements.acces import lit_le_corrige_complet

from .models import ConsultationJour, Corrige, Favori, Sujet


def examen_par_defaut(request):
    return "HND" if request.LANGUAGE_CODE == "en" else "BTS"


def est_requete_htmx(request):
    # Une restauration d'historique HTMX attend la page complète, pas le fragment.
    return request.headers.get("HX-Request") and not request.headers.get("HX-History-Restore-Request")


def meilleur_corrige():
    """Statut du corrigé à mettre en badge : vérifié, sinon communauté, sinon « en préparation »."""
    return (
        Corrige.objects.filter(sujet=OuterRef("pk"))
        .exclude(publication=Corrige.Publication.MASQUE)
        .filter(Q(publication=Corrige.Publication.PUBLIE) | Q(statut=Corrige.Statut.EN_PREPARATION))
        .annotate(
            rang=Case(
                When(statut=Corrige.Statut.VERIFIE, then=Value(0)),
                When(statut=Corrige.Statut.COMMUNAUTE, then=Value(1)),
                default=Value(2),
                output_field=IntegerField(),
            )
        )
        .order_by("rang")
        .values("statut")[:1]
    )


def liste(request):
    examen = Examen.objects.filter(code=request.GET.get("examen") or examen_par_defaut(request)).first()
    if examen is None:
        return render(request, "sujets/liste.html", {"examen": None})

    specialites = examen.specialites.order_by("nom")
    specialite = specialites.filter(code=request.GET.get("specialite")).first()

    # Seuls les sujets publiés sont visibles : jamais un brouillon ni un sujet masqué.
    publies = Sujet.objects.publies().filter(session__examen=examen)
    nb_specialites = (
        Sujet.specialites.through.objects.filter(sujet=OuterRef("pk"))
        .values("sujet")
        .annotate(n=Count("*"))
        .values("n")
    )
    sujets = publies.select_related("session", "matiere").annotate(
        nb_specialites=Subquery(nb_specialites), statut_corrige=Subquery(meilleur_corrige())
    )

    filtres = {
        "annee": request.GET.get("annee", ""),
        "matiere": request.GET.get("matiere", ""),
        "type": request.GET.get("type", ""),
        "q": request.GET.get("q", "").strip(),
        "corrige": request.GET.get("corrige", ""),
    }
    if specialite:
        sujets = sujets.filter(specialites=specialite)
    if filtres["annee"].isdigit():
        sujets = sujets.filter(session__annee=int(filtres["annee"]))
    if filtres["matiere"].isdigit():
        sujets = sujets.filter(matiere_id=int(filtres["matiere"]))
    if filtres["corrige"] in (Corrige.Statut.VERIFIE, Corrige.Statut.COMMUNAUTE):
        sujets = sujets.filter(statut_corrige=filtres["corrige"])
    if filtres["type"] in Sujet.TypeEpreuve.values:
        sujets = sujets.filter(type_epreuve=filtres["type"])
    if filtres["q"]:
        sujets = sujets.rechercher(filtres["q"], examen.langue)

    page = Paginator(sujets, settings.SUJETS_PAR_PAGE).get_page(request.GET.get("page"))
    contexte = {
        "examen": examen,
        "examens": Examen.objects.order_by("code"),
        "specialites": specialites,
        "specialite": specialite,
        "annees": publies.order_by("-session__annee").values_list("session__annee", flat=True).distinct(),
        "matieres": Matiere.objects.filter(sujets__in=publies).distinct().order_by("nom"),
        "types": Sujet.TypeEpreuve.choices,
        "filtres": filtres,
        "page": page,
    }
    gabarit = "sujets/_resultats.html" if est_requete_htmx(request) else "sujets/liste.html"
    return render(request, gabarit, contexte)


def detail(request, pk):
    sujet = get_object_or_404(Sujet.objects.publies().select_related("session__examen", "matiere"), pk=pk)
    # Le coefficient dépend de la spécialité (décision du point 7).
    coefficients = (
        SpecialiteMatiere.objects.filter(matiere=sujet.matiere, specialite__in=sujet.specialites.all())
        .select_related("specialite")
        .order_by("specialite__nom")
    )
    ConsultationJour.compter(sujet, "fiches", request.user)
    est_favori = request.user.is_authenticated and sujet.favoris.filter(utilisateur=request.user).exists()
    corriges = sujet.corriges.visibles() if settings.FONCTIONNALITES["corriges"] else Corrige.objects.none()
    return render(
        request,
        "sujets/detail.html",
        {
            "sujet": sujet,
            "coefficients": coefficients,
            "est_favori": est_favori,
            "onglet": "corrige" if request.GET.get("onglet") == "corrige" else "sujet",
            "corriges": corriges,
            "en_preparation": sujet.corriges.filter(statut=Corrige.Statut.EN_PREPARATION).exists(),
            "complet": lit_le_corrige_complet(request.user),
        },
    )


@login_required
@require_POST
def basculer_favori(request, pk):
    sujet = get_object_or_404(Sujet.objects.publies(), pk=pk)
    favori, cree = Favori.objects.get_or_create(utilisateur=request.user, sujet=sujet)
    if not cree:
        favori.delete()
    if est_requete_htmx(request):
        return render(request, "sujets/_bouton_favori.html", {"sujet": sujet, "est_favori": cree})
    return redirect("sujets:detail", pk=pk)


def envoyer_pdf(request, fichier, nom):
    telecharger = request.GET.get("telecharger") == "1"
    if settings.FICHIERS_PAR_NGINX:
        # Django a vérifié les droits ; Nginx envoie le fichier depuis un emplacement interne,
        # inaccessible directement (deploy/nginx.conf, location /fichiers-proteges/).
        reponse = HttpResponse(content_type="application/pdf")
        reponse["X-Accel-Redirect"] = "/fichiers-proteges/" + quote(fichier.name)
        reponse["Content-Disposition"] = content_disposition_header(telecharger, nom)
        return reponse
    return FileResponse(fichier.open("rb"), content_type="application/pdf", as_attachment=telecharger, filename=nom)


def pdf(request, pk):
    sujet = get_object_or_404(Sujet.objects.publies().select_related("session"), pk=pk)
    ConsultationJour.compter(sujet, "pdf", request.user)
    return envoyer_pdf(request, sujet.fichier, f"{slugify(sujet.titre)}-{sujet.session.annee}.pdf")


def pdf_corrige(request, pk):
    corrige = get_object_or_404(Corrige.objects.visibles().select_related("sujet__session"), pk=pk)
    # Le PDF est le corrigé entier : réservé à ceux qui lisent le corrigé complet.
    if not corrige.fichier or not lit_le_corrige_complet(request.user):
        raise Http404
    sujet = corrige.sujet
    return envoyer_pdf(request, corrige.fichier, f"corrige-{slugify(sujet.titre)}-{sujet.session.annee}.pdf")


@login_required
@require_POST
def signaler_corrige(request, pk):
    """CDC 3.3 et 10.7 : un étudiant signale une erreur ; le modérateur de la matière la traite."""
    corrige = get_object_or_404(Corrige.objects.visibles(), pk=pk)
    motif = request.POST.get("motif", "").strip()
    if len(motif) < 10:
        messages.error(request, _("Décrivez l'erreur en quelques mots (10 caractères au moins)."))
    else:
        Signalement.objects.create(utilisateur=request.user, corrige=corrige, motif=motif)
        mail_admins(f"Erreur signalée : {corrige}", motif, fail_silently=True)
        messages.success(request, _("Merci ! L'enseignant relira ce passage."))
    return redirect(f"{reverse('sujets:detail', args=[corrige.sujet_id])}?onglet=corrige")