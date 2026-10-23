"""Examens blancs (CDC 3.5) : durée réelle, sauvegarde continue, reprise après coupure, auto-évaluation."""

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from paiements.acces import est_premium

from .correction import est_correcte
from .models import ExamenBlanc, Question, ReponseQuestion, Tentative

CHAMP_COPIE = "copie"


def peut_passer_un_examen(utilisateur):
    # CDC 7 : examens blancs réservés au Premium.
    return est_premium(utilisateur)


def examens_proposes(utilisateur):
    examens = ExamenBlanc.objects.visibles().select_related("sujet__session", "sujet__matiere")
    profil = getattr(utilisateur, "profil", None)
    if profil:
        examens = examens.filter(sujet__specialites=profil.specialite)
    return examens.distinct().order_by("-sujet__session__annee", "titre")


def demarrer(utilisateur, examen):
    """Reprend l'épreuve en cours s'il y en a une (coupure, rechargement), sinon en commence une."""
    en_cours = Tentative.objects.filter(utilisateur=utilisateur, examen_blanc=examen, fin__isnull=True).first()
    if en_cours:
        cloturer_si_expiree(en_cours)
        if en_cours.fin is None:
            return en_cours
    debut = timezone.now()
    return Tentative.objects.create(
        utilisateur=utilisateur,
        examen_blanc=examen,
        debut=debut,
        # L'heure de fin vit sur le serveur : le temps continue pendant une coupure, comme le jour de l'examen.
        fin_prevue=debut + timedelta(minutes=examen.duree),
        reponses={"ordre": list(examen.questions.order_by("pk").values_list("pk", flat=True)), "brouillon": {}, CHAMP_COPIE: ""},
    )


def secondes_restantes(tentative):
    return max(0, int((tentative.fin_prevue - timezone.now()).total_seconds()))


def est_expiree(tentative):
    """Au-delà de l'heure de fin et de la marge de transmission, plus rien n'est accepté."""
    return timezone.now() > tentative.fin_prevue + timedelta(seconds=settings.EXAMEN_DELAI_GRACE_SECONDES)


def lire_formulaire(tentative, donnees):
    """Réponses du formulaire d'épreuve : {identifiant de question: choix cochés ou texte}, et la copie."""
    brouillon = {}
    questions = Question.objects.filter(pk__in=tentative.ordre).prefetch_related("choix")
    for question in questions:
        nom = f"q-{question.pk}"
        if question.type == Question.Type.REPONSE_COURTE:
            texte = donnees.get(nom, "").strip()
            if texte:
                brouillon[str(question.pk)] = texte
        else:
            permis = {str(choix.pk) for choix in question.choix.all()}
            cochees = sorted({int(valeur) for valeur in donnees.getlist(nom) if valeur in permis})
            if cochees:
                brouillon[str(question.pk)] = cochees
    return brouillon, donnees.get(CHAMP_COPIE, "")


def enregistrer(tentative, donnees):
    """Sauvegarde continue. Faux si l'épreuve est rendue ou expirée : la réponse arrive trop tard."""
    if tentative.fin is not None or est_expiree(tentative):
        return False
    brouillon, copie = lire_formulaire(tentative, donnees)
    tentative.reponses.update({"brouillon": brouillon, CHAMP_COPIE: copie, "enregistre_le": timezone.now().isoformat()})
    tentative.save(update_fields=["reponses"])
    return True


@transaction.atomic
def rendre(tentative, donnees=None):
    """Remise de la copie : la partie QCM est corrigée tout de suite (CDC 3.5)."""
    if tentative.fin is not None:
        return
    if donnees is not None and not est_expiree(tentative):
        enregistrer(tentative, donnees)
    brouillon = tentative.reponses.get("brouillon", {})
    justes = 0
    for question in Question.objects.filter(pk__in=tentative.ordre).prefetch_related("choix"):
        reponse = brouillon.get(str(question.pk))
        # Une question sans réponse compte comme fausse.
        correcte = reponse is not None and est_correcte(question, reponse)
        justes += correcte
        ReponseQuestion.objects.get_or_create(
            tentative=tentative, question=question, defaults={"reponse": reponse or [], "correcte": correcte}
        )
    total = len(tentative.ordre)
    points_qcm = tentative.examen_blanc.points_qcm
    obtenus = Decimal(justes * points_qcm) / Decimal(total) if total else Decimal(0)
    tentative.reponses.update({"justes_qcm": justes, "points_qcm": str(obtenus.quantize(Decimal("0.01")))})
    tentative.fin = min(timezone.now(), tentative.fin_prevue)
    tentative.save(update_fields=["reponses", "fin"])


def cloturer_si_expiree(tentative):
    """Soumission automatique d'une épreuve abandonnée, avec les dernières réponses enregistrées."""
    if tentative.fin is None and est_expiree(tentative):
        rendre(tentative)


def auto_evaluer(tentative, donnees):
    """Points de la partie rédactionnelle, bornés par le barème ; la note finale est calculée sur 20."""
    examen = tentative.examen_blanc
    points = {}
    for critere in examen.criteres.all():
        try:
            valeur = Decimal(donnees.get(f"critere-{critere.pk}", "0").replace(",", "."))
        except ArithmeticError:
            valeur = Decimal(0)
        points[str(critere.pk)] = str(min(max(valeur, Decimal(0)), Decimal(critere.points)))
    obtenus = Decimal(tentative.reponses.get("points_qcm", "0")) + sum(Decimal(v) for v in points.values())
    total = examen.points_total
    tentative.reponses["auto_evaluation"] = points
    tentative.note = (obtenus * 20 / total).quantize(Decimal("0.01"), ROUND_HALF_UP) if total else None
    tentative.save(update_fields=["reponses", "note"])
