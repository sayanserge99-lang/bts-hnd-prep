"""Offres affichées au public (CDC 3.8, 10.7 : prix en FCFA TTC affichés avant paiement, sans frais cachés)."""

from django.utils import timezone

from catalogue.models import Examen, Session

from .models import Offre


def offres_affichees(utilisateur):
    """Offres actives, du moins cher au plus cher ; un Pass session indique jusqu'à quand il vaut."""
    aujourd_hui = timezone.localdate()
    profil = getattr(utilisateur, "profil", None) if utilisateur.is_authenticated else None
    examens = [profil.examen] if profil else list(Examen.objects.order_by("code"))
    offres = list(Offre.objects.filter(active=True).order_by("prix"))
    for offre in offres:
        offre.fins = []
        if offre.type == Offre.Type.SESSION:
            for examen in examens:
                session = Session.objects.prochaine(examen, aujourd_hui)
                if session:
                    offre.fins.append(session)
    return offres
