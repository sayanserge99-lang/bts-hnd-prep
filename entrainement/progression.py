"""Suivi de progression (CDC 3.6) : taux de réussite, points faibles, compte à rebours."""

from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from catalogue.models import Chapitre, Matiere, Session
from paiements.acces import est_premium

from .models import ReponseQuestion, Tentative

# En dessous, un chapitre n'a pas assez de réponses pour être jugé (une seule erreur ne fait pas un point faible).
REPONSES_MINIMUM = 3
NOMBRE_POINTS_FAIBLES = 3
# Tableau de bord (maquette) : la maîtrise par matière porte sur les 30 derniers jours, et une matière sous 50 %
# est signalée en ambre (à travailler en priorité).
JOURS_MAITRISE = 30
SEUIL_PRIORITE = 50


@dataclass
class Taux:
    objet: object  # Matiere ou Chapitre
    total: int
    justes: int

    @property
    def pourcentage(self):
        return round(100 * self.justes / self.total) if self.total else 0


def voit_les_statistiques_completes(utilisateur):
    # CDC 7 : statistiques basiques en gratuit, complètes en Premium.
    return est_premium(utilisateur)


def _taux(utilisateur, champ, objets, depuis=None):
    reponses = ReponseQuestion.objects.filter(tentative__utilisateur=utilisateur)
    if depuis:
        reponses = reponses.filter(repondu_le__gte=depuis)
    lignes = (
        reponses.values(champ)
        .annotate(total=Count("pk"), justes=Count("pk", filter=Q(correcte=True)))
    )
    # Les noms viennent des objets eux-mêmes : ainsi, ils suivent la langue de l'interface.
    par_identifiant = objets.in_bulk([ligne[champ] for ligne in lignes])
    return [Taux(par_identifiant[ligne[champ]], ligne["total"], ligne["justes"]) for ligne in lignes]


def taux_par_matiere(utilisateur, jours=None):
    """Taux par matière ; avec `jours`, seulement les réponses de ces derniers jours."""
    depuis = timezone.now() - timedelta(days=jours) if jours else None
    taux = _taux(utilisateur, "question__chapitre__matiere", Matiere.objects.all(), depuis)
    return sorted(taux, key=lambda t: str(t.objet.nom))


def bilan_par_chapitre(reponses):
    """Résultat d'une tentative chapitre par chapitre (écran de résultat), dans l'ordre du programme."""
    par_chapitre = {}
    for reponse in reponses:
        chapitre = reponse.question.chapitre
        taux = par_chapitre.setdefault(chapitre.pk, Taux(chapitre, 0, 0))
        taux.total += 1
        taux.justes += reponse.correcte
    return sorted(par_chapitre.values(), key=lambda t: (t.objet.ordre, str(t.objet.titre)))


def chapitre_a_revoir(taux_chapitres):
    """Le chapitre le moins réussi, s'il reste des erreurs ; à taux égal, celui qui a le plus de questions."""
    candidats = [t for t in taux_chapitres if t.justes < t.total]
    return min(candidats, key=lambda t: (t.pourcentage, -t.total)) if candidats else None


def bilan(utilisateur):
    """Bonnes réponses sur toutes les questions répondues : (pourcentage, nombre de réponses)."""
    compte = ReponseQuestion.objects.filter(tentative__utilisateur=utilisateur).aggregate(
        total=Count("pk"), justes=Count("pk", filter=Q(correcte=True))
    )
    return Taux(None, compte["total"], compte["justes"])


def serie_en_cours(utilisateur):
    """Jours d'affilée avec au moins un quiz ou examen terminé. Encore rien aujourd'hui : la série court
    depuis hier (elle ne se casse qu'après une journée entière sans entraînement)."""
    jours = {
        timezone.localtime(fin).date()
        for fin in Tentative.objects.filter(utilisateur=utilisateur, fin__isnull=False).values_list("fin", flat=True)
    }
    jour = timezone.localdate()
    if jour not in jours:
        jour -= timedelta(days=1)
    serie = 0
    while jour in jours:
        serie += 1
        jour -= timedelta(days=1)
    return serie


def jour_relatif(moment):
    """« Aujourd'hui », « Hier », « Il y a 3 jours », puis la date."""
    ecart = (timezone.localdate() - timezone.localtime(moment).date()).days
    if ecart <= 0:
        return _("Aujourd'hui")
    if ecart == 1:
        return _("Hier")
    if ecart < 7:
        return ngettext("Il y a %(n)s jour", "Il y a %(n)s jours", ecart) % {"n": ecart}
    return timezone.localtime(moment).strftime("%d/%m/%Y")


def taux_par_chapitre(utilisateur):
    taux = _taux(utilisateur, "question__chapitre", Chapitre.objects.select_related("matiere"))
    return sorted(taux, key=lambda t: (str(t.objet.matiere.nom), t.objet.ordre))


def points_faibles(utilisateur, taux_chapitres=None):
    """Les chapitres les moins maîtrisés ; à taux égal, celui qui a le plus de réponses (le plus sûr) d'abord."""
    candidats = [t for t in (taux_chapitres or taux_par_chapitre(utilisateur)) if t.total >= REPONSES_MINIMUM]
    candidats.sort(key=lambda t: (t.pourcentage, -t.total))
    return [t for t in candidats if t.pourcentage < 100][:NOMBRE_POINTS_FAIBLES]


def prochaine_session(utilisateur):
    """La session prévue dans le profil si elle est à venir, sinon la prochaine session de l'examen visé."""
    profil = getattr(utilisateur, "profil", None)
    if profil is None:
        return None
    aujourd_hui = timezone.localdate()
    if profil.session_prevue and profil.session_prevue.date_debut >= aujourd_hui:
        return profil.session_prevue
    return Session.objects.filter(examen=profil.examen, date_debut__gte=aujourd_hui).order_by("date_debut").first()


def jours_restants(session):
    return (session.date_debut - timezone.localdate()).days if session else None
