"""Page « Ventes » de l'administrateur : revenus, payeurs fidèles, abonnements à relancer, clients perdus.

Vue interne réservée à l'administrateur (CDC 11.2, avancée avant la bêta à la demande de Serge Alain) : les listes
nominatives restent dans la page, sans export.
"""

from datetime import date, timedelta

from django.db.models import Count, Exists, Max, OuterRef, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from catalogue.statistiques import Indicateur

from .models import Abonnement, CodeReduction, Paiement

MOIS_AFFICHES = 12
MEILLEURS_CLIENTS = 20
JOURS_AVANT_FIN = 7
JOURS_PERDUS = 60


def debut_du_mois(jour, decalage=0):
    """Premier jour du mois de `jour`, décalé de `decalage` mois (négatif : en arrière)."""
    mois = jour.year * 12 + jour.month - 1 + decalage
    return date(mois // 12, mois % 12 + 1, 1)


def tableau_des_ventes(aujourd_hui=None):
    aujourd_hui = aujourd_hui or timezone.localdate()
    reussis = Paiement.objects.filter(statut=Paiement.Statut.REUSSI)
    premier_mois = debut_du_mois(aujourd_hui, -(MOIS_AFFICHES - 1))

    # Revenus mois par mois (les mois sans vente s'affichent à zéro).
    par_mois = {
        ligne["mois"].date() if hasattr(ligne["mois"], "date") else ligne["mois"]: ligne
        for ligne in reussis.filter(confirme_le__date__gte=premier_mois)
        .annotate(mois=TruncMonth("confirme_le"))
        .values("mois")
        .annotate(montant=Sum("montant"), nombre=Count("pk"), remises=Sum("remise"))
    }
    mois = []
    for decalage in range(MOIS_AFFICHES):
        jour = debut_du_mois(premier_mois, decalage)
        ligne = par_mois.get(jour, {})
        mois.append({"mois": jour, "montant": ligne.get("montant") or 0, "nombre": ligne.get("nombre") or 0,
                     "remises": ligne.get("remises") or 0})
    maximum = max((ligne["montant"] for ligne in mois), default=0)
    for ligne in mois:
        ligne["part"] = round(100 * ligne["montant"] / maximum) if maximum else 0

    par_client = reussis.values("utilisateur").annotate(nombre=Count("pk"))
    payeurs = par_client.count()
    fideles = par_client.filter(nombre__gte=2).count()

    # Clients qui ont payé le plus (internes : affichés ici, jamais exportés).
    meilleurs = (
        reussis.values("utilisateur", "utilisateur__email", "utilisateur__first_name", "utilisateur__last_name")
        .annotate(nombre=Count("pk"), total=Sum("montant"), dernier=Max("confirme_le"))
        .order_by("-total", "-nombre")[:MEILLEURS_CLIENTS]
    )
    fins = dict(
        Abonnement.objects.filter(
            utilisateur__in=[ligne["utilisateur"] for ligne in meilleurs], statut=Abonnement.Statut.ACTIF, fin__gte=aujourd_hui
        ).values("utilisateur").annotate(fin=Max("fin")).values_list("utilisateur", "fin")
    )

    # À relancer : abonnement payé qui finit dans la semaine, sans rien derrière (même règle que les rappels).
    suite = Abonnement.objects.filter(utilisateur=OuterRef("utilisateur"), statut=Abonnement.Statut.ACTIF,
                                      debut__gt=OuterRef("fin"))
    a_relancer = (
        Abonnement.objects.filter(paiement__isnull=False, statut=Abonnement.Statut.ACTIF, fin__gte=aujourd_hui,
                                  fin__lte=aujourd_hui + timedelta(days=JOURS_AVANT_FIN))
        .exclude(Exists(suite))
        .select_related("utilisateur", "offre")
        .order_by("fin")
    )

    # Perdus : un abonnement payé fini depuis moins de 60 jours, et plus aucun accès aujourd'hui.
    perdus = (
        Abonnement.objects.filter(paiement__isnull=False, fin__lt=aujourd_hui,
                                  fin__gte=aujourd_hui - timedelta(days=JOURS_PERDUS))
        .exclude(Exists(Abonnement.objects.filter(utilisateur=OuterRef("utilisateur"), fin__gte=aujourd_hui)))
        .values("utilisateur", "utilisateur__email", "utilisateur__first_name", "utilisateur__last_name")
        .annotate(fin=Max("fin"))
        .order_by("-fin")
    )

    ce_mois, mois_precedent = mois[-1]["montant"], mois[-2]["montant"] if len(mois) > 1 else 0
    return {
        "mois": mois,
        "ca_periode": sum(ligne["montant"] for ligne in mois),
        "ca_mois": Indicateur(ce_mois, mois_precedent),
        "payeurs": payeurs,
        "fideles": fideles,
        "renouvellement": round(100 * fideles / payeurs) if payeurs else 0,
        "panier_moyen": round((reussis.aggregate(m=Sum("montant"))["m"] or 0) / reussis.count()) if reussis.exists() else 0,
        "par_offre": reussis.values("offre__nom").annotate(nombre=Count("pk"), montant=Sum("montant")).order_by("-montant"),
        "meilleurs": [{**ligne, "fin_acces": fins.get(ligne["utilisateur"])} for ligne in meilleurs],
        "a_relancer": a_relancer,
        "perdus": perdus,
        "a_regulariser": reussis.exclude(motif_echec="").select_related("utilisateur", "offre"),
        "echoues_30_jours": Paiement.objects.filter(statut=Paiement.Statut.ECHOUE,
                                                    cree_le__date__gte=aujourd_hui - timedelta(days=30)).count(),
        "codes": CodeReduction.objects.annotate(
            nombre=Count("utilisations", filter=Q(utilisations__confirmee_le__isnull=False)),
            montant=Sum("utilisations__paiement__montant", filter=Q(utilisations__paiement__statut=Paiement.Statut.REUSSI)),
            remises=Sum("utilisations__remise", filter=Q(utilisations__confirmee_le__isnull=False)),
        ).filter(nombre__gt=0).order_by("-montant"),
        "jours_avant_fin": JOURS_AVANT_FIN,
        "jours_perdus": JOURS_PERDUS,
        "nombre_mois": MOIS_AFFICHES,
    }
