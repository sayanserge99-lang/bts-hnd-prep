from django.contrib import admin

from .models import Choix, ExamenBlanc, Question, Quiz, Tentative


class ChoixInline(admin.TabularInline):
    model = Choix
    extra = 4


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "chapitre", "type", "difficulte", "langue")
    list_filter = ("type", "difficulte", "langue", "chapitre__matiere")
    inlines = [ChoixInline]


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ("titre", "mode", "matiere", "chapitre", "nb_questions")
    filter_horizontal = ("questions",)


@admin.register(ExamenBlanc)
class ExamenBlancAdmin(admin.ModelAdmin):
    list_display = ("titre", "sujet", "duree")
    filter_horizontal = ("questions",)


@admin.register(Tentative)
class TentativeAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "quiz", "examen_blanc", "debut", "note")
