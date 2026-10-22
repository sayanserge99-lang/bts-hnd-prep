from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from accounts.moderation import LimiteAuxMatieresDuModerateur

from .models import Contribution, DemandeRetrait, Signalement

# Un signalement ou une demande de retrait vise un sujet ou un corrigé.
CIBLES = ("sujet__matiere", "corrige__sujet__matiere")


@admin.register(Contribution)
class ContributionAdmin(LimiteAuxMatieresDuModerateur, admin.ModelAdmin):
    list_display = ("matiere", "annee", "utilisateur", "statut", "cree_le")
    list_filter = ("statut",)


@admin.register(Signalement)
class SignalementAdmin(LimiteAuxMatieresDuModerateur, admin.ModelAdmin):
    chemins_matiere = CIBLES
    list_display = ("__str__", "utilisateur", "statut", "cree_le")
    list_filter = ("statut",)


@admin.register(DemandeRetrait)
class DemandeRetraitAdmin(LimiteAuxMatieresDuModerateur, admin.ModelAdmin):
    chemins_matiere = CIBLES
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
