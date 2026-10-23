"""Suivi de progression (CDC 3.6) : taux de réussite, points faibles, compte à rebours."""

from dataclasses import dataclass

from django.db.models import Count, Q
from django.utils import timezone

from catalogue.models import Chapitre, Matiere, Session
from paiements.acces import est_premium

from .models import ReponseQuestion

# En dessous, un chapitre n'a pas assez de réponses pour être jugé (une seule erreur ne fait pas un point faible).
REPONSES_MINIMUM = 3
NOMBRE_POINTS_FAIBLES = 3


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


def _taux(utilisateur, champ, objets):
    lignes = (
        ReponseQuestion.objects.filter(tentative__utilisateur=utilisateur)
        .values(champ)
        .annotate(total=Count("pk"), justes=Count("pk", filter=Q(correcte=True)))
    )
    # Les noms viennent des objets eux-mêmes : ainsi, ils suivent la langue de l'interface.
    par_identifiant = objets.in_bulk([ligne[champ] for ligne in lignes])
    return [Taux(par_identifiant[ligne[champ]], ligne["total"], ligne["justes"]) for ligne in lignes]


def taux_par_matiere(utilisateur):
    taux = _taux(utilisateur, "question__chapitre__matiere", Matiere.objects.all())
    return sorted(taux, key=lambda t: str(t.objet.nom))


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
