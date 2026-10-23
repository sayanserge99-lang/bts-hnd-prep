from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from accounts.views import changer_langue
from catalogue.views import accueil, hors_ligne, manifeste, options_specialites, service_worker, statistiques
from communaute.views import demande_retrait
from paiements.views import offres


admin.site.site_header = _("BTS-HND Prep — Administration")
admin.site.site_title = _("BTS-HND Prep")
admin.site.index_title = _("Tableau de bord")


def page(nom):
    return TemplateView.as_view(template_name=f"pages/{nom}.html")


urlpatterns = [
    path("", accueil, name="accueil"),
    path("sw.js", service_worker, name="service_worker"),
    path("manifest.webmanifest", manifeste, name="manifeste"),
    path("hors-ligne/", hors_ligne, name="hors_ligne"),
    path("specialites/", options_specialites, name="options_specialites"),
    path("sujets/", include("sujets.urls")),
    path("compte/", include("accounts.urls")),
    path("entrainement/", include("entrainement.urls")),
    path("etablissement/", include("partenaires.urls")),
    path("contribuer/", include("communaute.urls")),
    path("forum/", include("forum.urls")),
    path("offres/", offres, name="offres"),
    path("paiement/", include("paiements.urls")),
    # CDC 10 : pages légales accessibles depuis toutes les pages (contenu à rédiger).
    path("mentions-legales/", page("mentions_legales"), name="mentions_legales"),
    path("confidentialite/", page("confidentialite"), name="confidentialite"),
    path("conditions-de-vente/", page("conditions_de_vente"), name="conditions_de_vente"),
    path("demande-de-retrait/", demande_retrait, name="demande_de_retrait"),
    path(
        "demande-de-retrait/recue/",
        TemplateView.as_view(template_name="communaute/demande_retrait_recue.html"),
        name="demande_retrait_recue",
    ),
    path("contact/", page("contact"), name="contact"),
    path("langue/", changer_langue, name="set_language"),
    # Avant admin.site.urls : sinon l'admin prendrait « statistiques » pour une application.
    path(f"{settings.ADMIN_URL}statistiques/", admin.site.admin_view(statistiques), name="statistiques"),
    path(settings.ADMIN_URL, admin.site.urls),
]
# Volontairement aucune route vers MEDIA_URL : les PDF passent par sujets:pdf.
