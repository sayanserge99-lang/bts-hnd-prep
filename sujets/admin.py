from django import forms
from django.contrib import admin, messages
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from accounts.moderation import LimiteAuxMatieresDuModerateur

from .models import Corrige, Favori, Sujet


class SujetAdminForm(forms.ModelForm):
    class Meta:
        model = Sujet
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        matiere = cleaned_data.get("matiere")
        specialites = cleaned_data.get("specialites")
        if matiere and specialites is not None:
            if specialites.exclude(pk__in=matiere.specialites.values("pk")).exists():
                self.add_error("specialites", _("Choisissez uniquement des spécialités rattachées à cette matière."))
        return cleaned_data


@admin.register(Sujet)
class SujetAdmin(LimiteAuxMatieresDuModerateur, admin.ModelAdmin):
    form = SujetAdminForm
    list_display = ("titre", "matiere", "session", "type_epreuve", "statut", "date_publication")
    list_filter = ("statut", "session__examen", "session__annee", "type_epreuve")
    search_fields = ("titre", "texte_extrait")
    filter_horizontal = ("specialites",)
    actions = ["publier", "depublier"]

    @admin.action(description=_("Publier les sujets sélectionnés"))
    def publier(self, request, queryset):
        # Les sujets masqués (demande de retrait) ne sont jamais republiés en groupe.
        a_publier = queryset.filter(statut=Sujet.Statut.BROUILLON)
        autorises = a_publier.publiables()
        refuses = a_publier.count() - autorises.count()
        publies = autorises.update(statut=Sujet.Statut.PUBLIE, date_publication=timezone.now())
        if publies:
            self.message_user(
                request,
                ngettext("%d sujet publié.", "%d sujets publiés.", publies) % publies,
                messages.SUCCESS,
            )
        if refuses:
            self.message_user(
                request,
                ngettext(
                    "%d sujet refusé : sa session n'est pas officiellement terminée.",
                    "%d sujets refusés : leur session n'est pas officiellement terminée.",
                    refuses,
                )
                % refuses,
                messages.WARNING,
            )

    @admin.action(description=_("Dépublier les sujets sélectionnés"))
    def depublier(self, request, queryset):
        nombre = queryset.filter(statut=Sujet.Statut.PUBLIE).update(
            statut=Sujet.Statut.BROUILLON, date_publication=None
        )
        self.message_user(request, ngettext("%d sujet dépublié.", "%d sujets dépubliés.", nombre) % nombre)


@admin.register(Corrige)
class CorrigeAdmin(LimiteAuxMatieresDuModerateur, admin.ModelAdmin):
    chemins_matiere = ("sujet__matiere",)
    list_display = ("sujet", "statut", "publication", "auteur", "titulaire_droits")
    list_filter = ("statut", "publication")


@admin.register(Favori)
class FavoriAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "sujet", "date_ajout")
