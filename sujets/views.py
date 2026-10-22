from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Count, OuterRef, Subquery
from django.http import FileResponse
from django.shortcuts import get_object_or_404, render
from django.utils.text import slugify

from catalogue.models import Examen, Matiere, SpecialiteMatiere

from .models import Sujet


def examen_par_defaut(request):
    return "HND" if request.LANGUAGE_CODE == "en" else "BTS"


def est_requete_htmx(request):
    # Une restauration d'historique HTMX attend la page complète, pas le fragment.
    return request.headers.get("HX-Request") and not request.headers.get("HX-History-Restore-Request")


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
    sujets = publies.select_related("session", "matiere").annotate(nb_specialites=Subquery(nb_specialites))

    filtres = {
        "annee": request.GET.get("annee", ""),
        "matiere": request.GET.get("matiere", ""),
        "type": request.GET.get("type", ""),
        "q": request.GET.get("q", "").strip(),
    }
    if specialite:
        sujets = sujets.filter(specialites=specialite)
    if filtres["annee"].isdigit():
        sujets = sujets.filter(session__annee=int(filtres["annee"]))
    if filtres["matiere"].isdigit():
        sujets = sujets.filter(matiere_id=int(filtres["matiere"]))
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
    return render(request, "sujets/detail.html", {"sujet": sujet, "coefficients": coefficients})


def pdf(request, pk):
    sujet = get_object_or_404(Sujet.objects.publies().select_related("session"), pk=pk)
    return FileResponse(
        sujet.fichier.open("rb"),
        content_type="application/pdf",
        as_attachment=request.GET.get("telecharger") == "1",
        filename=f"{slugify(sujet.titre)}-{sujet.session.annee}.pdf",
    )
