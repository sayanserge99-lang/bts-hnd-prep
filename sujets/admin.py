from collections import Counter

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from accounts.moderation import LimiteAuxMatieresDuModerateur

from . import importation
from .models import Corrige, Favori, Sujet
from .rendu import rendre
from .tasks import traiter_pdf_du_sujet


class SujetAdminForm(forms.ModelForm):
    class Meta:
        model = Sujet
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        matiere = cleaned_data.get("matiere")
        specialites = cleaned_data.get("specialites")
        if matiere and specialites is not None:
            if specialites.exclude(pk__in=matiere.specialites.values("pk")).exists():
                self.add_error("specialites", _("Choisissez uniquement des spécialités rattachées à cette matière."))
        return cleaned_data


class ImportForm(forms.Form):
    lot = forms.FileField(
        label=_("Fichier ZIP"),
        help_text=_("Le ZIP contient sujets.csv et les fichiers (PDF, ou photos JPG/PNG) qu'il cite."),
    )
    simulation = forms.BooleanField(
        label=_("Simulation : vérifier sans rien enregistrer"), required=False, initial=True
    )


@admin.register(Sujet)
class SujetAdmin(LimiteAuxMatieresDuModerateur, admin.ModelAdmin):
    form = SujetAdminForm
    change_list_template = "admin/sujets/sujet/change_list.html"

    def get_urls(self):
        propres = [
            path("importer/", self.admin_site.admin_view(self.vue_import), name="sujets_sujet_importer"),
            path("importer/modele.csv", self.admin_site.admin_view(self.vue_modele), name="sujets_sujet_modele_import"),
        ]
        return propres + super().get_urls()

    def vue_import(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        form = ImportForm(request.POST or None, request.FILES or None)
        rapport, simulation = None, True
        if form.is_valid():
            simulation = form.cleaned_data["simulation"]
            try:
                source = importation.SourceZip(form.cleaned_data["lot"])
                rapport = importation.Importateur(request.user).importer(
                    source, importation.tableau_du_zip(source), simulation=simulation
                )
            except importation.ImportImpossible as erreur:
                form.add_error("lot", str(erreur))
        contexte = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": _("Importer des sujets"),
            "form": form,
            "rapport": rapport,
            "simulation": simulation,
            "totaux": Counter(ligne.statut for ligne in rapport or []),
        }
        return TemplateResponse(request, "admin/sujets/sujet/importer.html", contexte)

    def vue_modele(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        reponse = HttpResponse(importation.modele_csv(), content_type="text/csv; charset=utf-8")
        reponse["Content-Disposition"] = 'attachment; filename="sujets.csv"'
        return reponse
    list_display = ("titre", "matiere", "session", "type_epreuve", "statut", "date_publication")
    list_filter = ("statut", "session__examen", "session__annee", "type_epreuve", "fourni_par")
    search_fields = ("titre", "texte_extrait")
    filter_horizontal = ("specialites",)
    actions = ["publier", "depublier", "retraiter_pdf"]

    @admin.action(description=_("Publier les sujets sélectionnés"))
    def publier(self, request, queryset):
        # Les sujets masqués (demande de retrait) ne sont jamais republiés en groupe.
        a_publier = queryset.filter(statut=Sujet.Statut.BROUILLON)
        autorises = a_publier.publiables()
        refuses = a_publier.count() - autorises.count()
        publies = autorises.update(statut=Sujet.Statut.PUBLIE, date_publication=timezone.now())
        if publies:
            self.message_user(
                request,
                ngettext("%d sujet publié.", "%d sujets publiés.", publies) % publies,
                messages.SUCCESS,
            )
        if refuses:
            self.message_user(
                request,
                ngettext(
                    "%d sujet refusé : sa session n'est pas officiellement terminée.",
                    "%d sujets refusés : leur session n'est pas officiellement terminée.",
                    refuses,
                )
                % refuses,
                messages.WARNING,
            )

    @admin.action(description=_("Dépublier les sujets sélectionnés"))
    def depublier(self, request, queryset):
        nombre = queryset.filter(statut=Sujet.Statut.PUBLIE).update(
            statut=Sujet.Statut.BROUILLON, date_publication=None
        )
        self.message_user(request, ngettext("%d sujet dépublié.", "%d sujets dépubliés.", nombre) % nombre)

    @admin.action(description=_("Relancer le traitement des PDF (texte, OCR, compression)"))
    def retraiter_pdf(self, request, queryset):
        identifiants = list(queryset.values_list("pk", flat=True))
        for identifiant in identifiants:
            traiter_pdf_du_sujet.delay(identifiant)
        self.message_user(
            request,
            ngettext("%d PDF mis en file de traitement.", "%d PDF mis en file de traitement.", len(identifiants))
            % len(identifiants),
        )


@admin.register(Corrige)
class CorrigeAdmin(LimiteAuxMatieresDuModerateur, admin.ModelAdmin):
    chemins_matiere = ("sujet__matiere",)
    list_display = ("sujet", "statut", "publication", "auteur", "titulaire_droits")
    list_filter = ("statut", "publication", "sujet__session__examen")
    search_fields = ("sujet__titre", "auteur")
    autocomplete_fields = ("sujet",)
    readonly_fields = ("apercu",)
    actions = ["publier"]

    @admin.display(description=_("Aperçu (tel que l'étudiant le verra)"))
    def apercu(self, corrige):
        if not corrige.pk:
            return _("Enregistrez une première fois pour voir l'aperçu.")
        return format_html(
            '<div style="max-width:48rem">{}<hr>{}</div>', rendre(corrige.partie_gratuite), rendre(corrige.contenu)
        )

    @admin.action(description=_("Publier les corrigés sélectionnés"))
    def publier(self, request, queryset):
        # Même règle que les sujets : la mise à jour groupée refuse une session non terminée.
        autorises = queryset.exclude(publication=Corrige.Publication.MASQUE).filter(
            sujet__session__date_fin_officielle__lt=timezone.localdate()
        )
        refuses = queryset.exclude(publication=Corrige.Publication.MASQUE).count() - autorises.count()
        publies = autorises.update(publication=Corrige.Publication.PUBLIE)
        self.message_user(request, ngettext("%d corrigé publié.", "%d corrigés publiés.", publies) % publies)
        if refuses:
            self.message_user(
                request,
                ngettext(
                    "%d corrigé refusé : la session de son sujet n'est pas officiellement terminée.",
                    "%d corrigés refusés : la session de leur sujet n'est pas officiellement terminée.",
                    refuses,
                )
                % refuses,
                messages.WARNING,
            )


@admin.register(Favori)
class FavoriAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "sujet", "date_ajout")
