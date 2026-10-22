from django.contrib import admin

from .models import Abonnement, CodeAcces, Offre, Paiement


@admin.register(Offre)
class OffreAdmin(admin.ModelAdmin):
    list_display = ("nom", "prix", "type", "duree_jours", "active")


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = ("reference", "utilisateur", "montant", "operateur", "statut", "cree_le")
    list_filter = ("statut", "operateur")
    search_fields = ("reference", "utilisateur__email")


@admin.register(CodeAcces)
class CodeAccesAdmin(admin.ModelAdmin):
    list_display = ("code", "offre", "partenariat", "utilise_par", "date_utilisation")


@admin.register(Abonnement)
class AbonnementAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "offre", "debut", "fin", "statut")
    list_filter = ("statut",)
