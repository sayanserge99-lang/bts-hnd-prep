from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .forms import UtilisateurChangeForm, UtilisateurCreationForm
from .models import AffectationModerateur, Consentement, ProfilEtude, Utilisateur


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
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


@admin.register(AffectationModerateur)
class AffectationModerateurAdmin(admin.ModelAdmin):
    list_display = ("moderateur", "matiere", "date_attribution")
