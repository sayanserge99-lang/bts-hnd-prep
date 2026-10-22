from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

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
    list_display = ("__str__", "demandeur_nom", "demandeur_email", "certifie_titulaire", "statut", "cree_le")
    list_filter = ("statut",)
    readonly_fields = ("traitee_le",)
    actions = ["accepter", "refuser"]

    @admin.action(description=_("Accepter : supprimer le document"))
    def accepter(self, request, queryset):
        demandes = queryset.filter(statut=DemandeRetrait.Statut.RECUE)
        for demande in demandes:
            demande.accepter()
        self.message_user(
            request, ngettext("%d demande acceptée.", "%d demandes acceptées.", len(demandes)) % len(demandes)
        )

    @admin.action(description=_("Refuser : republier le contenu"))
    def refuser(self, request, queryset):
        demandes = queryset.filter(statut=DemandeRetrait.Statut.RECUE)
        for demande in demandes:
            demande.refuser()
        self.message_user(
            request,
            ngettext("%d demande refusée.", "%d demandes refusées.", len(demandes)) % len(demandes),
            messages.SUCCESS,
        )
