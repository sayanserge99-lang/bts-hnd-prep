"""Correction immédiate des questions (CDC 3.4)."""

import re
import unicodedata

from .models import Question


def normaliser(texte):
    """Compare des réponses tapées au téléphone : casse, accents, espaces et virgule décimale ignorés."""
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    compact = re.sub(r"\s+", "", sans_accents.lower())
    return compact.replace(",", ".")


def est_correcte(question, reponse):
    """`reponse` : liste d'identifiants de choix (QCM, vrai/faux) ou texte (réponse courte)."""
    if question.type == Question.Type.REPONSE_COURTE:
        acceptees = {normaliser(attendue) for attendue in question.reponse_attendue.split("|") if attendue.strip()}
        return normaliser(str(reponse)) in acceptees
    cochees = {int(identifiant) for identifiant in reponse}
    bonnes = set(question.choix.filter(est_correct=True).values_list("pk", flat=True))
    # Choix multiple : il faut cocher toutes les bonnes réponses, et elles seules.
    return cochees == bonnes
