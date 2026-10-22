from django.contrib import admin

from .models import Etablissement, Partenariat


@admin.register(Etablissement)
class EtablissementAdmin(admin.ModelAdmin):
    list_display = ("nom", "ville", "region")
    list_filter = ("region",)
    search_fields = ("nom", "ville")


@admin.register(Partenariat)
class PartenariatAdmin(admin.ModelAdmin):
    list_display = ("etablissement", "date_debut", "date_fin", "taux_partage", "statut")
    list_filter = ("statut",)
