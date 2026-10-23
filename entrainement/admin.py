from collections import Counter

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.forms.models import BaseInlineFormSet
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from accounts.moderation import LimiteAuxMatieresDuModerateur
from sujets.importation import ImportImpossible

from . import importation

from .models import Choix, CritereBareme, ExamenBlanc, Question, Quiz, ReponseQuestion, Tentative


class ChoixFormSet(BaseInlineFormSet):
    """Une question publiée doit être cohérente (une bonne réponse pour un choix unique, etc.)."""

    def clean(self):
        super().clean()
        question = self.instance
        if not question.publiee:
            return
        choix = [
            (form.cleaned_data.get("texte", ""), form.cleaned_data.get("est_correct", False))
            for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get("DELETE") and form.cleaned_data.get("texte")
        ]
        problemes = question.problemes(choix)
        if problemes:
            raise ValidationError(problemes)


class ChoixInline(admin.TabularInline):
    model = Choix
    formset = ChoixFormSet
    extra = 4


class ImportQuestionsForm(forms.Form):
    tableau = forms.FileField(label=_("Tableau CSV des questions"))
    simulation = forms.BooleanField(
        label=_("Simulation seulement (rien n'est enregistré)"), required=False, initial=True
    )


@admin.register(Question)
class QuestionAdmin(LimiteAuxMatieresDuModerateur, admin.ModelAdmin):
    chemins_matiere = ("chapitre__matiere",)
    list_display = ("__str__", "chapitre", "sujet", "type", "difficulte", "langue", "publiee")
    list_filter = ("publiee", "type", "difficulte", "langue", "chapitre__matiere", "sujet__session__annee")
    search_fields = ("enonce",)
    autocomplete_fields = ("sujet",)
    inlines = [ChoixInline]
    actions = ["publier", "depublier"]

    def get_urls(self):
        propres = [
            path("importer/", self.admin_site.admin_view(self.vue_import), name="entrainement_question_importer"),
            path("importer/modele.csv", self.admin_site.admin_view(self.vue_modele), name="entrainement_question_modele_import"),
        ]
        return propres + super().get_urls()

    def vue_import(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        form = ImportQuestionsForm(request.POST or None, request.FILES or None)
        rapport, simulation = None, True
        if form.is_valid():
            simulation = form.cleaned_data["simulation"]
            tableau = form.cleaned_data["tableau"]
            try:
                if tableau.size > 5 * 1024 * 1024:
                    raise ImportImpossible(_("Le tableau dépasse 5 Mo."))
                rapport = importation.Importateur(request.user).importer(tableau.read(), simulation=simulation)
            except ImportImpossible as erreur:
                form.add_error("tableau", str(erreur))
        contexte = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": _("Importer des questions"),
            "form": form,
            "rapport": rapport,
            "simulation": simulation,
            "totaux": Counter(ligne.statut for ligne in rapport or []),
        }
        return TemplateResponse(request, "admin/entrainement/question/importer.html", contexte)

    def vue_modele(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        reponse = HttpResponse(importation.modele_csv(), content_type="text/csv; charset=utf-8")
        reponse["Content-Disposition"] = 'attachment; filename="questions.csv"'
        return reponse

    @admin.action(description=_("Publier les questions sélectionnées"))
    def publier(self, request, queryset):
        coherentes = [question for question in queryset.prefetch_related("choix") if not question.problemes()]
        Question.objects.filter(pk__in=[question.pk for question in coherentes]).update(publiee=True)
        self.message_user(
            request, ngettext("%d question publiée.", "%d questions publiées.", len(coherentes)) % len(coherentes)
        )
        refusees = queryset.count() - len(coherentes)
        if refusees:
            self.message_user(
                request,
                ngettext(
                    "%d question refusée : ses choix ou sa réponse attendue sont incomplets.",
                    "%d questions refusées : leurs choix ou leur réponse attendue sont incomplets.",
                    refusees,
                )
                % refusees,
                messages.WARNING,
            )

    @admin.action(description=_("Retirer des quiz les questions sélectionnées"))
    def depublier(self, request, queryset):
        nombre = queryset.update(publiee=False)
        self.message_user(request, ngettext("%d question retirée.", "%d questions retirées.", nombre) % nombre)


@admin.register(Quiz)
class QuizAdmin(LimiteAuxMatieresDuModerateur, admin.ModelAdmin):
    list_display = ("titre", "mode", "matiere", "chapitre", "nb_questions")
    filter_horizontal = ("questions",)


class CritereBaremeInline(admin.TabularInline):
    model = CritereBareme
    extra = 3


@admin.register(ExamenBlanc)
class ExamenBlancAdmin(LimiteAuxMatieresDuModerateur, admin.ModelAdmin):
    chemins_matiere = ("sujet__matiere",)
    list_display = ("titre", "sujet", "duree", "points_qcm", "publie")
    list_filter = ("publie",)
    filter_horizontal = ("questions",)
    autocomplete_fields = ("sujet",)
    inlines = [CritereBaremeInline]


class ReponseQuestionInline(admin.TabularInline):
    model = ReponseQuestion
    extra = 0
    readonly_fields = ("question", "reponse", "correcte", "repondu_le")
    can_delete = False


@admin.register(Tentative)
class TentativeAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "quiz", "examen_blanc", "debut", "note")
    inlines = [ReponseQuestionInline]
