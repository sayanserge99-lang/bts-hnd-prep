from django.db.models import Max, Min
from django.shortcuts import render

from sujets.models import Sujet
from sujets.views import examen_par_defaut

from .models import Examen, Specialite


def accueil(request):
    publies = Sujet.objects.publies()
    code_examen = examen_par_defaut(request)
    return render(
        request,
        "catalogue/accueil.html",
        {
            "annees": publies.aggregate(debut=Min("session__annee"), fin=Max("session__annee")),
            "derniers_sujets": publies.select_related("session__examen", "matiere").order_by("-date_publication")[:2],
            "examens": Examen.objects.order_by("code"),
            "code_examen": code_examen,
            "specialites_examen": Specialite.objects.filter(examen__code=code_examen).order_by("nom"),
            "specialites": Specialite.objects.select_related("examen").order_by("examen__code", "nom"),
        },
    )


def options_specialites(request):
    """Fragment HTMX : la liste des spécialités suit l'examen choisi."""
    specialites = Specialite.objects.filter(examen__code=request.GET.get("examen")).order_by("nom")
    return render(request, "catalogue/_options_specialites.html", {"specialites": specialites})
