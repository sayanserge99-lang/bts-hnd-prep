from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from accounts.moderation import LimiteAuxMatieresDuModerateur

from .models import Discussion, Reponse, SignalementForum


class MasquerRetablirMixin:
    actions = ["masquer", "retablir"]

    @admin.action(description=_("Masquer les messages sélectionnés"))
    def masquer(self, request, queryset):
        nombre = queryset.update(masquee=True)
        self.message_user(request, ngettext("%d message masqué.", "%d messages masqués.", nombre) % nombre)

    @admin.action(description=_("Rétablir les messages sélectionnés"))
    def retablir(self, request, queryset):
        nombre = queryset.update(masquee=False)
        # Rétablir après examen : les signalements qui l'avaient masqué sont clos.
        SignalementForum.objects.filter(**{f"{self.cible_signalement}__in": queryset}).update(traite=True)
        self.message_user(request, ngettext("%d message rétabli.", "%d messages rétablis.", nombre) % nombre)


class ReponseInline(admin.TabularInline):
    model = Reponse
    extra = 0
    fields = ("auteur", "texte", "masquee", "cree_le")
    readonly_fields = ("auteur", "cree_le")


@admin.register(Discussion)
class DiscussionAdmin(MasquerRetablirMixin, LimiteAuxMatieresDuModerateur, admin.ModelAdmin):
    cible_signalement = "discussion"
    list_display = ("titre", "matiere", "auteur", "masquee", "derniere_activite")
    list_filter = ("masquee", "matiere__examen", "matiere")
    search_fields = ("titre", "texte", "auteur__email")
    raw_id_fields = ("auteur", "sujet", "reponse_acceptee")
    inlines = [ReponseInline]


@admin.register(Reponse)
class ReponseAdmin(MasquerRetablirMixin, LimiteAuxMatieresDuModerateur, admin.ModelAdmin):
    chemins_matiere = ("discussion__matiere",)
    cible_signalement = "reponse"
    list_display = ("__str__", "auteur", "masquee", "cree_le")
    list_filter = ("masquee",)
    search_fields = ("texte", "auteur__email")
    raw_id_fields = ("discussion", "auteur")


@admin.register(SignalementForum)
class SignalementForumAdmin(LimiteAuxMatieresDuModerateur, admin.ModelAdmin):
    chemins_matiere = ("discussion__matiere", "reponse__discussion__matiere")
    list_display = ("cible", "motif", "utilisateur", "traite", "cree_le")
    list_filter = ("traite",)
    readonly_fields = ("utilisateur", "discussion", "reponse", "motif", "cree_le")
    actions = ["masquer_la_cible", "rejeter"]

    def has_add_permission(self, request):
        return False

    @admin.action(description=_("Masquer le message signalé (signalement fondé)"))
    def masquer_la_cible(self, request, queryset):
        Discussion.objects.filter(signalements__in=queryset).update(masquee=True)
        Reponse.objects.filter(signalements__in=queryset).update(masquee=True)
        nombre = queryset.update(traite=True)
        self.message_user(request, ngettext("%d signalement traité.", "%d signalements traités.", nombre) % nombre)

    @admin.action(description=_("Rejeter le signalement et rétablir le message"))
    def rejeter(self, request, queryset):
        Discussion.objects.filter(signalements__in=queryset).update(masquee=False)
        Reponse.objects.filter(signalements__in=queryset).update(masquee=False)
        nombre = queryset.update(traite=True)
        self.message_user(request, ngettext("%d signalement rejeté.", "%d signalements rejetés.", nombre) % nombre)
