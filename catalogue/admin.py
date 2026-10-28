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
    list_display = ("nom", "examen", "filiere", "ordre", "equivalent")
    list_editable = ("ordre",)
    list_filter = ("examen", "filiere")
    inlines = [SpecialiteMatiereInline]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Seulement les spécialités de l'autre examen.
        if db_field.name == "equivalent":
            objet = request.resolver_match.kwargs.get("object_id")
            examen = Specialite.objects.filter(pk=objet).values_list("examen_id", flat=True).first() if objet else None
            if examen:
                kwargs["queryset"] = Specialite.objects.exclude(examen_id=examen)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        equivalent = obj.equivalent
        obj.equivalent = None  # posé des deux côtés par apparier(), après l'enregistrement
        super().save_model(request, obj, form, change)
        obj.apparier(equivalent)


@admin.register(Matiere)
class MatiereAdmin(TranslationAdmin):
    list_display = ("nom", "examen")
    list_filter = ("examen",)
    search_fields = ("nom_fr", "nom_en")


@admin.register(Chapitre)
class ChapitreAdmin(TranslationAdmin):
    list_display = ("titre", "matiere", "ordre")
    list_filter = ("matiere__examen",)
