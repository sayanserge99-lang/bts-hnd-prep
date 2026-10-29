"""Être trouvé sur Google : plan du site (sitemap.xml) et consignes aux robots (robots.txt).

Seul ce qui est public y figure : sujets publiés, discussions visibles, pages générales. Un sujet d'une
session en cours n'est jamais publié, donc jamais annoncé ici (CDC 4.2).
"""

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.http import HttpResponse
from django.urls import reverse
from django.views.decorators.http import require_GET

from forum.models import Discussion
from sujets.models import Sujet


class PagesGenerales(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return ["accueil", "sujets:liste", "offres", "forum:accueil", "contact", "mentions_legales", "confidentialite", "conditions_de_vente"]

    def location(self, nom):
        return reverse(nom)


class Sujets(Sitemap):
    changefreq = "monthly"
    priority = 0.9  # le cœur du site : ce que les étudiants cherchent

    def items(self):
        return Sujet.objects.publies().order_by("pk")

    def location(self, sujet):
        return reverse("sujets:detail", args=[sujet.pk])

    def lastmod(self, sujet):
        return sujet.modifie_le


class Discussions(Sitemap):
    changefreq = "weekly"
    priority = 0.4

    def items(self):
        return Discussion.objects.visibles().order_by("pk")

    def location(self, discussion):
        return reverse("forum:discussion", args=[discussion.pk])

    def lastmod(self, discussion):
        return discussion.derniere_activite


PLANS = {"pages": PagesGenerales, "sujets": Sujets, "forum": Discussions}

# Espaces personnels : rien à y indexer. L'adresse de l'administration n'est volontairement pas citée
# (robots.txt est public : la nommer la ferait connaître).
INTERDITS = ["/compte/", "/entrainement/", "/paiement/", "/etablissement/", "/contribuer/", "/hors-ligne/"]


@require_GET
def robots(request):
    if settings.SERVEUR_ESSAI:
        # Le serveur d'essai ne doit jamais apparaître dans un moteur de recherche.
        return HttpResponse("User-agent: *\nDisallow: /\n", content_type="text/plain; charset=utf-8")
    lignes = ["User-agent: *", *(f"Disallow: {chemin}" for chemin in INTERDITS), "",
              f"Sitemap: {request.build_absolute_uri(reverse('plan_du_site'))}"]
    return HttpResponse("\n".join(lignes) + "\n", content_type="text/plain; charset=utf-8")
