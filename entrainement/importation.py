"""Import de questions de QCM en lot depuis un tableau CSV (Excel).

Les questions importées sont toujours en brouillon : le modérateur les publie ensuite avec l'action
« Publier », qui revérifie leur cohérence. Une question rattachée à un sujet reste invisible tant que
ce sujet n'est pas publié (voir filtre_questions_visibles).
"""

import re
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Case, Q, Value, When
from django.utils.translation import gettext as _

from accounts.moderation import est_limite_a_ses_matieres, matieres_de
from catalogue.models import Chapitre, Examen, Matiere
from sujets.importation import Doublon, ImportImpossible, _normaliser, lire_tableau, modele_csv as _modele_csv
from sujets.models import Sujet

from .models import Choix, Question

LETTRES = "abcde"
COLONNES = [
    "examen", "matiere", "chapitre", "type", "enonce",
    *(f"choix_{lettre}" for lettre in LETTRES),
    "bonnes", "reponse_attendue", "explication", "difficulte", "langue", "annee_sujet",
]
COLONNES_OBLIGATOIRES = {"examen", "matiere", "chapitre", "type", "enonce"}
EXEMPLES = [
    {
        "examen": "BTS", "matiere": "Comptabilité générale", "chapitre": "Amortissements", "type": "choix_unique",
        "enonce": "Une machine de 1 200 000 FCFA est amortie sur 5 ans en linéaire. Quelle est l'annuité ?",
        "choix_a": "200 000", "choix_b": "240 000", "choix_c": "300 000", "choix_d": "", "choix_e": "",
        "bonnes": "B", "reponse_attendue": "", "explication": "1 200 000 / 5 = 240 000 FCFA par an.",
        "difficulte": "1", "langue": "fr", "annee_sujet": "2024",
    },
    {
        "examen": "BTS", "matiere": "Comptabilité générale", "chapitre": "Amortissements", "type": "vrai_faux",
        "enonce": "Un terrain s'amortit.", "choix_a": "", "choix_b": "", "choix_c": "", "choix_d": "", "choix_e": "",
        "bonnes": "faux", "reponse_attendue": "", "explication": "Un terrain ne se déprécie pas avec l'usage.",
        "difficulte": "", "langue": "", "annee_sujet": "",
    },
]
TYPES = {
    "choix_unique": Question.Type.CHOIX_UNIQUE, "unique": Question.Type.CHOIX_UNIQUE, "qcm": Question.Type.CHOIX_UNIQUE,
    "choix_multiple": Question.Type.CHOIX_MULTIPLE, "multiple": Question.Type.CHOIX_MULTIPLE,
    "vrai_faux": Question.Type.VRAI_FAUX, "vrai/faux": Question.Type.VRAI_FAUX, "true_false": Question.Type.VRAI_FAUX,
    "reponse_courte": Question.Type.REPONSE_COURTE, "courte": Question.Type.REPONSE_COURTE,
}
DIFFICULTES = {"1": 1, "facile": 1, "easy": 1, "2": 2, "moyenne": 2, "medium": 2, "3": 3, "difficile": 3, "hard": 3}
VRAI, FAUX = {"vrai", "true", "v", "a"}, {"faux", "false", "f", "b"}


@dataclass
class Ligne:
    numero: int
    enonce: str
    statut: str  # "pret", "importe", "erreur", "doublon"
    message: str = ""
    question_id: int | None = None


def modele_csv():
    return _modele_csv(COLONNES, EXEMPLES)


def _cle(chapitre, enonce):
    return chapitre.pk, re.sub(r"\s+", " ", enonce).strip().lower()


class Importateur:
    def __init__(self, utilisateur=None):
        self.utilisateur = utilisateur
        self.limite = utilisateur is not None and est_limite_a_ses_matieres(utilisateur)
        self.examens = {examen.code: examen for examen in Examen.objects.all()}

    def _choix(self, rangee, type_question, langue):
        """Liste de (texte, est_correct) d'après les colonnes choix_a… et bonnes."""
        bonnes = _normaliser(rangee["bonnes"])
        if type_question == Question.Type.REPONSE_COURTE:
            return []
        if type_question == Question.Type.VRAI_FAUX:
            if bonnes not in VRAI | FAUX:
                raise ValueError(_("colonne bonnes : « vrai » ou « faux » pour une question vrai/faux"))
            textes = ("Vrai", "Faux") if langue == "fr" else ("True", "False")
            return [(textes[0], bonnes in VRAI), (textes[1], bonnes in FAUX)]
        lettres = [lettre for lettre in LETTRES if rangee[f"choix_{lettre}"]]
        cochees = {lettre.strip() for lettre in re.split(r"[,;|\s]+", bonnes) if lettre.strip()}
        inconnues = cochees - set(lettres)
        if inconnues:
            raise ValueError(_("colonne bonnes : « %(lettres)s » ne correspond à aucun choix rempli") % {"lettres": ", ".join(sorted(inconnues)).upper()})
        return [(rangee[f"choix_{lettre}"], lettre in cochees) for lettre in lettres]

    def analyser(self, rangee, deja_vues):
        """Vérifie une ligne ; renvoie (valeurs de la question, choix) ou lève ValueError avec le motif."""
        examen = self.examens.get(rangee["examen"].upper())
        if examen is None:
            raise ValueError(_("examen inconnu « %(examen)s » (BTS ou HND)") % {"examen": rangee["examen"]})
        matiere = Matiere.objects.filter(Q(nom_fr__iexact=rangee["matiere"]) | Q(nom_en__iexact=rangee["matiere"]), examen=examen).first()
        if matiere is None:
            raise ValueError(_("matière inconnue « %(matiere)s » pour le %(examen)s") % {"matiere": rangee["matiere"], "examen": examen.code})
        if self.limite and not matieres_de(self.utilisateur).filter(pk=matiere.pk).exists():
            raise ValueError(_("cette matière ne vous est pas attribuée"))
        chapitre = Chapitre.objects.filter(matiere=matiere, titre__iexact=rangee["chapitre"]).first()
        if chapitre is None:
            raise ValueError(_("chapitre inconnu « %(chapitre)s » : ajoutez-le d'abord à la matière dans l'admin") % {"chapitre": rangee["chapitre"]})

        type_question = TYPES.get(_normaliser(rangee["type"]))
        if type_question is None:
            raise ValueError(_("type invalide « %(type)s » (choix_unique, choix_multiple, vrai_faux ou reponse_courte)") % {"type": rangee["type"]})
        if not rangee["enonce"]:
            raise ValueError(_("énoncé vide"))
        difficulte = DIFFICULTES.get(_normaliser(rangee["difficulte"]) or "2")
        if difficulte is None:
            raise ValueError(_("difficulté invalide « %(difficulte)s » (1, 2 ou 3)") % {"difficulte": rangee["difficulte"]})
        langue = rangee["langue"].lower() or ("fr" if examen.code == "BTS" else "en")
        if langue not in ("fr", "en"):
            raise ValueError(_("langue invalide « %(langue)s » (fr ou en)") % {"langue": rangee["langue"]})

        sujet = None
        if rangee["annee_sujet"]:
            if not rangee["annee_sujet"].isdigit():
                raise ValueError(_("année invalide « %(annee)s »") % {"annee": rangee["annee_sujet"]})
            # Écrit et pratique la même année : la question va à l'épreuve écrite.
            sujet = (
                Sujet.objects.filter(session__examen=examen, session__annee=int(rangee["annee_sujet"]), matiere=matiere)
                .order_by(Case(When(type_epreuve=Sujet.TypeEpreuve.ECRITE, then=Value(0)), default=Value(1)))
                .first()
            )
            if sujet is None:
                raise ValueError(_("aucun sujet %(examen)s %(annee)s de cette matière : importez d'abord le sujet") % {"examen": examen.code, "annee": rangee["annee_sujet"]})

        choix = self._choix(rangee, type_question, langue)
        question = Question(
            chapitre=chapitre, sujet=sujet, enonce=rangee["enonce"], type=type_question,
            reponse_attendue=rangee["reponse_attendue"] if type_question == Question.Type.REPONSE_COURTE else "",
            explication=rangee["explication"], difficulte=difficulte, langue=langue,
        )
        # Les mêmes contrôles qu'à la publication : une question incohérente est refusée dès l'import.
        problemes = question.problemes(choix)
        if problemes:
            raise ValueError(" ".join(str(probleme) for probleme in problemes))

        cle = _cle(chapitre, rangee["enonce"])
        if cle in deja_vues or any(_cle(chapitre, enonce) == cle for enonce in chapitre.questions.values_list("enonce", flat=True)):
            raise Doublon(_("cette question existe déjà dans ce chapitre"))
        deja_vues.add(cle)
        return question, choix

    def importer(self, contenu_tableau, simulation=True):
        rangees = lire_tableau(contenu_tableau, COLONNES, COLONNES_OBLIGATOIRES)
        if not rangees:
            raise ImportImpossible(_("Le tableau ne contient aucune ligne."))
        rapport, deja_vues = [], set()
        # Ligne 1 = en-têtes : la première ligne de données est la ligne 2, comme dans Excel.
        for numero, rangee in enumerate(rangees, start=2):
            ligne = Ligne(numero, rangee["enonce"][:80], "pret")
            try:
                question, choix = self.analyser(rangee, deja_vues)
            except Doublon as doublon:
                ligne.statut, ligne.message = "doublon", str(doublon)
            except ValueError as erreur:
                ligne.statut, ligne.message = "erreur", str(erreur)
            else:
                if not simulation:
                    ligne.question_id = self._creer(question, choix)
                    ligne.statut = "importe"
            rapport.append(ligne)
        return rapport

    @transaction.atomic
    def _creer(self, question, choix):
        question.publiee = False  # toujours en brouillon : publiée ensuite par le modérateur
        question.save()
        Choix.objects.bulk_create(Choix(question=question, texte=texte, est_correct=correct) for texte, correct in choix)
        return question.pk

