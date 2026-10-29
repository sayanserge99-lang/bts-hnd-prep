from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .forms import ConnexionAdminForm, UtilisateurChangeForm, UtilisateurCreationForm
from .models import (
    AffectationModerateur, Consentement, DoubleAuthentification, ProfilEnseignant, ProfilEtude, Utilisateur,
)


class AffectationModerateurInline(admin.TabularInline):
    model = AffectationModerateur
    fk_name = "moderateur"
    extra = 1
    verbose_name_plural = _("Matières modérées (rôle Modérateur)")


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    inlines = [AffectationModerateurInline]
    form = UtilisateurChangeForm
    add_form = UtilisateurCreationForm
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "langue", "is_active", "date_joined")
    list_filter = ("is_active", "groups", "langue")
    search_fields = ("email", "first_name", "last_name", "telephone")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Identité"), {"fields": ("first_name", "last_name", "telephone", "langue")}),
        (_("Rôles"), {"fields": ("is_active", "is_staff", "is_superuser", "groups")}),
        (_("Dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),)


@admin.register(ProfilEtude)
class ProfilEtudeAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "examen", "specialite", "etablissement")
    list_filter = ("examen",)


@admin.register(Consentement)
class ConsentementAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "objet", "version", "date", "date_revocation")
    list_filter = ("objet",)


@admin.register(ProfilEnseignant)
class ProfilEnseignantAdmin(admin.ModelAdmin):
    """L'administrateur crée le profil (établissement, matières) ; l'enseignant choisit lui-même son affichage, sa
    photo et donne ou retire son accord depuis son profil (accounts:profil_enseignant)."""

    list_display = ("utilisateur", "etablissement", "affichage", "carte_visible")
    list_filter = ("etablissement",)
    search_fields = ("utilisateur__email", "utilisateur__first_name", "utilisateur__last_name")
    autocomplete_fields = ("utilisateur",)
    filter_horizontal = ("matieres",)
    fields = ("utilisateur", "etablissement", "matieres")

    @admin.display(boolean=True, description=_("carte visible (accord de l'enseignant)"))
    def carte_visible(self, profil):
        return profil.visible


@admin.register(AffectationModerateur)
class AffectationModerateurAdmin(admin.ModelAdmin):
    list_display = ("moderateur", "matiere", "date_attribution")


# Connexion à l'administration : mêmes limites d'essais que le site (accounts.forms.ConnexionLimiteeMixin).
admin.site.login_form = ConnexionAdminForm


@admin.register(DoubleAuthentification)
class DoubleAuthentificationAdmin(admin.ModelAdmin):
    """Téléphone perdu : supprimer la ligne oblige la personne à scanner un nouveau QR code à sa prochaine connexion."""

    list_display = ("utilisateur", "active_le", "codes_restants")
    search_fields = ("utilisateur__email",)
    fields = ("utilisateur", "active_le", "codes_restants")
    readonly_fields = fields  # le secret n'est jamais montré

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    @admin.display(description=_("codes de secours restants"))
    def codes_restants(self, appareil):
        return len(appareil.codes_secours)
