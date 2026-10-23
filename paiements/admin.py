from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.translation import gettext_lazy as _

from partenaires.models import Partenariat

from . import codes
from .models import Abonnement, CodeAcces, Offre, Paiement


@admin.register(Offre)
class OffreAdmin(admin.ModelAdmin):
    list_display = ("nom", "prix", "type", "duree_jours", "active")


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    """Lecture seule : seul l'agrégateur fait changer un paiement d'état."""

    list_display = ("reference", "utilisateur", "offre", "montant", "operateur", "statut", "motif_echec", "cree_le")
    list_filter = ("statut", "operateur", "fournisseur")
    search_fields = ("reference", "utilisateur__email", "telephone")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class GenerationCodesForm(forms.Form):
    partenariat = forms.ModelChoiceField(
        queryset=Partenariat.objects.filter(statut=Partenariat.Statut.ACTIF).select_related("etablissement"),
        label=_("Établissement (convention active)"),
    )
    offre = forms.ModelChoiceField(queryset=Offre.objects.filter(active=True), label=_("Offre donnée par chaque code"))
    nombre = forms.IntegerField(min_value=1, max_value=2000, label=_("Nombre de codes"))


def reponse_csv(liste, nom):
    reponse = HttpResponse(codes.en_csv(liste), content_type="text/csv; charset=utf-8")
    reponse["Content-Disposition"] = f'attachment; filename="{nom}"'
    return reponse


@admin.register(CodeAcces)
class CodeAccesAdmin(admin.ModelAdmin):
    """CDC 3.9 : codes prépayés vendus aux IPES pour leurs étudiants."""

    list_display = ("code", "offre", "partenariat", "utilise_par", "date_utilisation")
    list_filter = ("partenariat__etablissement", "offre", ("utilise_par", admin.EmptyFieldListFilter))
    search_fields = ("code", "utilise_par__email")
    readonly_fields = ("code", "utilise_par", "date_utilisation")
    actions = ["exporter"]

    def has_add_permission(self, request):
        return False  # les codes se créent par lot (« Générer des codes »), jamais à la main

    def get_urls(self):
        return [
            path("generer/", self.admin_site.admin_view(self.vue_generer), name="paiements_codeacces_generer"),
        ] + super().get_urls()

    def vue_generer(self, request):
        if not self.has_change_permission(request):
            raise PermissionDenied
        form = GenerationCodesForm(request.POST or None)
        if form.is_valid():
            partenariat = form.cleaned_data["partenariat"]
            try:
                lot = codes.generer(partenariat, form.cleaned_data["offre"], form.cleaned_data["nombre"])
            except ValidationError as erreur:
                form.add_error("partenariat", erreur)
            else:
                # Le fichier part directement : c'est lui qu'on remet à l'établissement.
                return reponse_csv(lot, f"codes-{partenariat.etablissement.nom}.csv".replace(" ", "-"))
        contexte = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": _("Générer des codes d'accès"),
            "form": form,
        }
        return TemplateResponse(request, "admin/paiements/codeacces/generer.html", contexte)

    @admin.action(description=_("Exporter les codes sélectionnés (CSV)"))
    def exporter(self, request, queryset):
        return reponse_csv(queryset.select_related("offre", "partenariat__etablissement"), "codes.csv")


@admin.register(Abonnement)
class AbonnementAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "offre", "debut", "fin", "statut", "origine")
    list_filter = ("statut",)
    search_fields = ("utilisateur__email",)

    @admin.display(description=_("origine"))
    def origine(self, abonnement):
        if abonnement.paiement_id:
            return _("paiement")
        if abonnement.code_acces_id:
            return _("code d'accès")
        return _("contribution")
