from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from accounts.views import changer_langue
from catalogue.views import (
    accueil, hors_ligne, manifeste, options_specialites, service_worker, statistiques, sujets_retires,
)
from communaute.views import contact, demande_retrait
from config import plan_du_site
from paiements.views import offres

admin.site.site_header = _("BTS-HND Prep — Administration")
admin.site.site_title = _("BTS-HND Prep")
admin.site.index_title = _("Tableau de bord")


def page(nom, texte=None):
    """Page fixe ; `texte` : page légale dont le contenu est dans pages/textes/<texte>_<langue>.html."""
    contexte = {"texte": texte, "version": settings.VERSION_POLITIQUES} if texte else None
    return TemplateView.as_view(template_name=f"pages/{nom}.html", extra_context=contexte)


urlpatterns = [
    path("", accueil, name="accueil"),
    path("sw.js", service_worker, name="service_worker"),
    path("robots.txt", plan_du_site.robots, name="robots"),
    path("sitemap.xml", sitemap, {"sitemaps": plan_du_site.PLANS}, name="plan_du_site"),
    path("manifest.webmanifest", manifeste, name="manifeste"),
    path("hors-ligne/", hors_ligne, name="hors_ligne"),
    path("hors-ligne/retires/", sujets_retires, name="sujets_retires"),
    path("specialites/", options_specialites, name="options_specialites"),
    path("sujets/", include("sujets.urls")),
    path("compte/", include("accounts.urls")),
    path("entrainement/", include("entrainement.urls")),
    path("etablissement/", include("partenaires.urls")),
    path("contribuer/", include("communaute.urls")),
    path("forum/", include("forum.urls")),
    path("offres/", offres, name="offres"),
    path("paiement/", include("paiements.urls")),
    # CDC 10 : pages légales accessibles depuis toutes les pages (brouillons FR/EN, à relire par un juriste).
    path("mentions-legales/", page("mentions_legales", "mentions_legales"), name="mentions_legales"),
    path("confidentialite/", page("confidentialite", "confidentialite"), name="confidentialite"),
    path("conditions-d-utilisation/", page("conditions_utilisation", "conditions_utilisation"), name="conditions_utilisation"),
    path("conditions-de-vente/", page("conditions_de_vente"), name="conditions_de_vente"),
    path("demande-de-retrait/", demande_retrait, name="demande_de_retrait"),
    path(
        "demande-de-retrait/recue/",
        TemplateView.as_view(template_name="communaute/demande_retrait_recue.html"),
        name="demande_retrait_recue",
    ),
    path("contact/", contact, name="contact"),
    path("contact/envoye/", TemplateView.as_view(template_name="communaute/contact_envoye.html"), name="contact_envoye"),
    path("langue/", changer_langue, name="set_language"),
    # Avant admin.site.urls : sinon l'admin prendrait « statistiques » pour une application.
    path(f"{settings.ADMIN_URL}statistiques/", admin.site.admin_view(statistiques), name="statistiques"),
    path(settings.ADMIN_URL, admin.site.urls),
]
# Volontairement aucune route vers MEDIA_URL : les PDF passent par sujets:pdf.
