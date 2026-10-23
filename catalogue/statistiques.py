"""Statistiques du back-office (CDC 3.9) : inscrits, activité, sujets les plus consultés, revenus, conversion."""

from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db.models import Count, F, Q, Sum
from django.utils import timezone

from accounts.models import ProfilEtude, Utilisateur
from communaute.models import Contribution, DemandeRetrait, Signalement
from forum.models import SignalementForum
from entrainement.models import Question, ReponseQuestion, Tentative
from paiements.models import Abonnement, Paiement
from partenaires.models import Etablissement
from sujets.models import ConsultationJour, Corrige, Sujet

PERIODE_JOURS = 30
TOP_SUJETS = 10


@dataclass
class Indicateur:
    valeur: int
    precedente: int | None = None  # même indicateur sur la période d'avant, pour l'évolution

    @property
    def evolution(self):
        if self.precedente is None:
            return None
        return self.valeur - self.precedente


def par_etablissement(etudiants, debut):
    """Inscrits, actifs et réussite par établissement déclaré, pour l'administrateur seulement.

    Ordre alphabétique, jamais un classement : CDC 10.6 (neutralité entre établissements).
    """
    cle = "utilisateur__profil__etablissement"
    inscrits = dict(
        ProfilEtude.objects.filter(utilisateur__in=etudiants).values_list("etablissement").annotate(n=Count("pk"))
    )
    actifs = dict(
        Tentative.objects.filter(fin__date__gte=debut, utilisateur__in=etudiants)
        .values_list(cle).annotate(n=Count("utilisateur", distinct=True))
    )
    reponses = {
        ligne[f"tentative__{cle}"]: ligne
        for ligne in ReponseQuestion.objects.filter(repondu_le__date__gte=debut, tentative__utilisateur__in=etudiants)
        .values(f"tentative__{cle}")
        .annotate(total=Count("pk"), justes=Count("pk", filter=Q(correcte=True)))
    }
    noms = Etablissement.objects.in_bulk([identifiant for identifiant in inscrits if identifiant])
    lignes = []
    for identifiant, nombre in inscrits.items():
        detail = reponses.get(identifiant, {"total": 0, "justes": 0})
        lignes.append({
            "etablissement": noms.get(identifiant),
            "inscrits": nombre,
            "actifs": actifs.get(identifiant, 0),
            "reussite": round(100 * detail["justes"] / detail["total"]) if detail["total"] else None,
        })
    # « Non renseigné » à la fin, le reste par ordre alphabétique.
    return sorted(lignes, key=lambda ligne: (ligne["etablissement"] is None, str(ligne["etablissement"] or "").lower()))


def tableau_de_bord(aujourd_hui=None):
    aujourd_hui = aujourd_hui or timezone.localdate()
    debut = aujourd_hui - timedelta(days=PERIODE_JOURS - 1)
    debut_precedent = debut - timedelta(days=PERIODE_JOURS)
    etudiants = Utilisateur.objects.filter(is_staff=False, is_superuser=False)

    def sur_la_periode(queryset, champ):
        return (
            queryset.filter(**{f"{champ}__date__gte": debut}).count(),
            queryset.filter(**{f"{champ}__date__gte": debut_precedent, f"{champ}__date__lt": debut}).count(),
        )

    nouveaux, nouveaux_avant = sur_la_periode(etudiants, "date_joined")
    quiz_faits, quiz_avant = sur_la_periode(Tentative.objects.filter(quiz__isnull=False, fin__isnull=False), "fin")
    examens_faits, examens_avant = sur_la_periode(
        Tentative.objects.filter(examen_blanc__isnull=False, fin__isnull=False), "fin"
    )
    actifs = (
        Tentative.objects.filter(fin__date__gte=debut, utilisateur__in=etudiants).values("utilisateur").distinct().count()
    )

    consultations = (
        ConsultationJour.objects.filter(jour__gte=debut)
        .values("sujet")
        # Noms distincts des champs : sinon F("fiches") désignerait la somme, pas le champ.
        .annotate(nb_fiches=Sum("fiches"), nb_pdf=Sum("pdf"), total=Sum(F("fiches") + F("pdf")))
        .order_by("-total")[:TOP_SUJETS]
    )
    sujets = Sujet.objects.select_related("session__examen").in_bulk([ligne["sujet"] for ligne in consultations])
    # « sujet » en dernier : il remplace l'identifiant venu de values() par l'objet.
    top = [{**ligne, "sujet": sujets[ligne["sujet"]]} for ligne in consultations]
    maximum = max((ligne["total"] for ligne in top), default=0)
    for ligne in top:
        ligne["part"] = round(100 * ligne["total"] / maximum) if maximum else 0

    total_inscrits = etudiants.count()
    revenus = None
    if settings.PAIEMENT_ACTIF:
        abonnes = (
            Abonnement.objects.filter(statut=Abonnement.Statut.ACTIF, debut__lte=aujourd_hui, fin__gte=aujourd_hui)
            .values("utilisateur")
            .distinct()
            .count()
        )
        revenus = {
            "montant": Paiement.objects.filter(statut=Paiement.Statut.REUSSI, confirme_le__date__gte=debut).aggregate(
                total=Sum("montant")
            )["total"] or 0,
            "abonnes": abonnes,
            # Taux de conversion : part des inscrits qui ont un abonnement en cours.
            "conversion": round(100 * abonnes / total_inscrits, 1) if total_inscrits else 0,
        }

    return {
        "par_etablissement": par_etablissement(etudiants, debut),
        "periode": PERIODE_JOURS,
        "debut": debut,
        "inscrits": total_inscrits,
        "nouveaux": Indicateur(nouveaux, nouveaux_avant),
        "actifs": actifs,
        "quiz": Indicateur(quiz_faits, quiz_avant),
        "examens": Indicateur(examens_faits, examens_avant),
        "par_examen": list(
            ProfilEtude.objects.filter(utilisateur__in=etudiants).values("examen__code").annotate(n=Count("pk")).order_by("examen__code")
        ),
        "contenu": {
            "sujets": Sujet.objects.publies().count(),
            "brouillons": Sujet.objects.filter(statut=Sujet.Statut.BROUILLON).count(),
            "corriges": Corrige.objects.visibles().count(),
            "questions": Question.objects.filter(publiee=True).count(),
        },
        "a_traiter": {
            "retraits": DemandeRetrait.objects.filter(statut=DemandeRetrait.Statut.RECUE).count(),
            "signalements": Signalement.objects.filter(statut=Signalement.Statut.OUVERT).count(),
            "contributions": Contribution.objects.filter(statut=Contribution.Statut.EN_ATTENTE).count(),
            "forum": SignalementForum.objects.filter(traite=False).count(),
        },
        "top": top,
        "revenus": revenus,
    }
