from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from catalogue.views import accueil, options_specialites


def page(nom):
    return TemplateView.as_view(template_name=f"pages/{nom}.html")


urlpatterns = [
    path("", accueil, name="accueil"),
    path("specialites/", options_specialites, name="options_specialites"),
    path("sujets/", include("sujets.urls")),
    # CDC 10 : pages légales accessibles depuis toutes les pages (contenu à rédiger).
    path("mentions-legales/", page("mentions_legales"), name="mentions_legales"),
    path("confidentialite/", page("confidentialite"), name="confidentialite"),
    path("conditions-de-vente/", page("conditions_de_vente"), name="conditions_de_vente"),
    path("demande-de-retrait/", page("demande_de_retrait"), name="demande_de_retrait"),
    path("contact/", page("contact"), name="contact"),
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", admin.site.urls),
]
# Volontairement aucune route vers MEDIA_URL : les PDF passent par sujets:pdf.
