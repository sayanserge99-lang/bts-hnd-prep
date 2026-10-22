from django.contrib import admin
from modeltranslation.admin import TranslationAdmin

from .models import Chapitre, Examen, Matiere, Session, Specialite, SpecialiteMatiere


@admin.register(Examen)
class ExamenAdmin(TranslationAdmin):
    list_display = ("code", "nom", "langue")


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ("examen", "annee", "date_debut", "date_fin_officielle")
    list_filter = ("examen",)


class SpecialiteMatiereInline(admin.TabularInline):
    model = SpecialiteMatiere
    extra = 1


@admin.register(Specialite)
class SpecialiteAdmin(TranslationAdmin):
    list_display = ("nom", "examen", "filiere")
    list_filter = ("examen", "filiere")
    inlines = [SpecialiteMatiereInline]


@admin.register(Matiere)
class MatiereAdmin(TranslationAdmin):
    list_display = ("nom", "examen")
    list_filter = ("examen",)
    search_fields = ("nom_fr", "nom_en")


@admin.register(Chapitre)
class ChapitreAdmin(TranslationAdmin):
    list_display = ("titre", "matiere", "ordre")
    list_filter = ("matiere__examen",)
