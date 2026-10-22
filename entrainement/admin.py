from django.contrib import admin

from accounts.moderation import LimiteAuxMatieresDuModerateur

from .models import Choix, ExamenBlanc, Question, Quiz, Tentative


class ChoixInline(admin.TabularInline):
    model = Choix
    extra = 4


@admin.register(Question)
class QuestionAdmin(LimiteAuxMatieresDuModerateur, admin.ModelAdmin):
    chemins_matiere = ("chapitre__matiere",)
    list_display = ("__str__", "chapitre", "type", "difficulte", "langue")
    list_filter = ("type", "difficulte", "langue", "chapitre__matiere")
    inlines = [ChoixInline]


@admin.register(Quiz)
class QuizAdmin(LimiteAuxMatieresDuModerateur, admin.ModelAdmin):
    list_display = ("titre", "mode", "matiere", "chapitre", "nb_questions")
    filter_horizontal = ("questions",)


@admin.register(ExamenBlanc)
class ExamenBlancAdmin(LimiteAuxMatieresDuModerateur, admin.ModelAdmin):
    chemins_matiere = ("sujet__matiere",)
    list_display = ("titre", "sujet", "duree")
    filter_horizontal = ("questions",)


@admin.register(Tentative)
class TentativeAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "quiz", "examen_blanc", "debut", "note")
