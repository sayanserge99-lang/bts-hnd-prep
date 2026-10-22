from modeltranslation.translator import TranslationOptions, register

from .models import Chapitre, Examen, Matiere, Specialite


# Crée les colonnes nom_fr / nom_en (et titre_fr / titre_en) exigées par le CDC.
@register(Examen)
class ExamenTranslation(TranslationOptions):
    fields = ("nom",)


@register(Specialite)
class SpecialiteTranslation(TranslationOptions):
    fields = ("nom",)


@register(Matiere)
class MatiereTranslation(TranslationOptions):
    fields = ("nom",)


@register(Chapitre)
class ChapitreTranslation(TranslationOptions):
    fields = ("titre",)
