import hashlib

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db.models import Max, Min
from django.shortcuts import render
from django.templatetags.static import static
from django.utils.translation import gettext as _

from accounts.moderation import est_administrateur

from .statistiques import tableau_de_bord

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
            "specialites_examen": Specialite.objects.filter(examen__code=code_examen),
            "specialites": Specialite.objects.select_related("examen").order_by("examen__code", "ordre", "nom"),
        },
    )


def service_worker(request):
    """CDC 4 (hors ligne). Servi à la racine du site pour pouvoir intercepter toutes ses pages."""
    # La version change avec les fichiers statiques : un nouveau déploiement remplace l'ancienne coquille.
    version = hashlib.sha256((static("css/app.css") + static("js/hors-ligne.js")).encode()).hexdigest()[:12]
    reponse = render(request, "pwa/sw.js", {"version": version}, content_type="application/javascript")
    reponse["Service-Worker-Allowed"] = "/"
    # Le navigateur doit toujours vérifier s'il existe une nouvelle version du service worker.
    reponse["Cache-Control"] = "no-cache"
    return reponse


def manifeste(request):
    """Rend le site installable sur l'écran d'accueil du téléphone."""
    return render(request, "pwa/manifest.webmanifest", content_type="application/manifest+json")


def hors_ligne(request):
    """Page gardée sur le téléphone : sujets et quiz téléchargés, consultables sans connexion."""
    return render(request, "pwa/hors_ligne.html")


def statistiques(request):
    """CDC 3.9 : statistiques du back-office, réservées aux administrateurs (pas aux modérateurs)."""
    if not est_administrateur(request.user):
        raise PermissionDenied
    return render(
        request,
        "admin/statistiques.html",
        {**admin.site.each_context(request), "title": _("Statistiques"), **tableau_de_bord()},
    )


def options_specialites(request):
    """Fragment HTMX : la liste des spécialités suit l'examen choisi."""
    specialites = Specialite.objects.filter(examen__code=request.GET.get("examen"))
    return render(request, "catalogue/_options_specialites.html", {"specialites": specialites})
