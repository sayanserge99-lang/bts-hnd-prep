from django.contrib import admin

from .models import EpreuveInterne, Etablissement, Partenariat, ResponsableEtablissement


class ResponsableInline(admin.TabularInline):
    model = ResponsableEtablissement
    extra = 1
    autocomplete_fields = ("utilisateur",)


@admin.register(Etablissement)
class EtablissementAdmin(admin.ModelAdmin):
    list_display = ("nom", "ville", "region")
    list_filter = ("region",)
    search_fields = ("nom", "ville")
    inlines = [ResponsableInline]


@admin.register(Partenariat)
class PartenariatAdmin(admin.ModelAdmin):
    list_display = ("etablissement", "date_debut", "date_fin", "taux_partage", "statut")
    list_filter = ("statut",)


@admin.register(EpreuveInterne)
class EpreuveInterneAdmin(admin.ModelAdmin):
    list_display = ("titre", "etablissement", "type", "annee_academique", "publiee", "deposee_le")
    list_filter = ("etablissement", "type", "publiee")
    search_fields = ("titre",)
