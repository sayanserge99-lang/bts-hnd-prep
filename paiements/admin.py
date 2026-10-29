from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.translation import gettext_lazy as _

from partenaires.models import Partenariat

from . import codes
from django.db.models import Count, Q, Sum

from .models import Abonnement, CodeAcces, CodeReduction, Offre, Paiement, UtilisationCode


@admin.register(Offre)
class OffreAdmin(admin.ModelAdmin):
    list_display = ("nom", "prix", "type", "duree_jours", "active")


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    """Lecture seule : seul l'agrégateur fait changer un paiement d'état."""

    list_display = ("reference", "utilisateur", "offre", "prix_initial", "remise", "montant", "operateur", "statut", "motif_echec", "cree_le")
    list_filter = ("statut", "operateur", "fournisseur")
    search_fields = ("reference", "utilisateur__email", "telephone")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class UtilisationCodeInline(admin.TabularInline):
    model = UtilisationCode
    fields = readonly_fields = ("utilisateur", "paiement", "remise", "reservee_le", "confirmee_le")
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(CodeReduction)
class CodeReductionAdmin(admin.ModelAdmin):
    """CDC 11.1 : codes de réduction, créés par l'administrateur seulement (le groupe Modérateur n'a aucun droit
    dessus) ; utilisations et chiffre d'affaires généré."""

    list_display = ("code", "type", "valeur", "debut", "fin", "etablissement", "actif", "utilisations", "chiffre_affaires")
    list_filter = ("actif", "type", "offres")
    search_fields = ("code",)
    filter_horizontal = ("offres",)
    inlines = [UtilisationCodeInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            nb_confirmees=Count("utilisations", filter=Q(utilisations__confirmee_le__isnull=False)),
            ca=Sum("utilisations__paiement__montant", filter=Q(utilisations__paiement__statut=Paiement.Statut.REUSSI)),
        )

    @admin.display(description=_("utilisations"), ordering="nb_confirmees")
    def utilisations(self, code):
        maximum = code.utilisations_max if code.utilisations_max is not None else "∞"
        return f"{code.nb_confirmees} / {maximum}"

    @admin.display(description=_("chiffre d'affaires (FCFA)"), ordering="ca")
    def chiffre_affaires(self, code):
        return f"{code.ca or 0:,}".replace(",", " ")


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
