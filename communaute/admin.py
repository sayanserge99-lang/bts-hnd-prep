from django.contrib import admin

from .models import Contribution, DemandeRetrait, Signalement


@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):
    list_display = ("matiere", "annee", "utilisateur", "statut", "cree_le")
    list_filter = ("statut",)


@admin.register(Signalement)
class SignalementAdmin(admin.ModelAdmin):
    list_display = ("__str__", "utilisateur", "statut", "cree_le")
    list_filter = ("statut",)


@admin.register(DemandeRetrait)
class DemandeRetraitAdmin(admin.ModelAdmin):
    list_display = ("__str__", "demandeur_nom", "demandeur_email", "statut", "cree_le")
    list_filter = ("statut",)
