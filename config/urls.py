from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from accounts.views import changer_langue
from catalogue.views import accueil, options_specialites
from communaute.views import demande_retrait


def page(nom):
    return TemplateView.as_view(template_name=f"pages/{nom}.html")


urlpatterns = [
    path("", accueil, name="accueil"),
    path("specialites/", options_specialites, name="options_specialites"),
    path("sujets/", include("sujets.urls")),
    path("compte/", include("accounts.urls")),
    path("entrainement/", include("entrainement.urls")),
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
    path("admin/", admin.site.urls),
]
# Volontairement aucune route vers MEDIA_URL : les PDF passent par sujets:pdf.
