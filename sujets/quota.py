"""Sujets ouverts sans compte : quelques-uns par jour, puis un compte gratuit (CDC : téléchargement limité).

On compte les sujets différents ouverts dans la journée, pas les requêtes : un lecteur PDF demande souvent
le fichier en plusieurs fois, et rouvrir un sujet déjà ouvert ne coûte rien. Le compteur vit dans la session
du visiteur ; une limite par adresse IP, plus large (un campus ou un cybercafé partage souvent une adresse),
empêche de le contourner en effaçant ses cookies. Les inscrits ne sont jamais limités.
"""

from django.conf import settings
from django.utils import timezone

from config.securite import PDF_VISITEURS_PAR_IP, adresse_ip

CLE = "sujets_ouverts_sans_compte"


def _ouverts_aujourd_hui(request):
    jour = timezone.localdate().isoformat()
    ouverts = request.session.get(CLE)
    if not ouverts or ouverts.get("jour") != jour:
        ouverts = {"jour": jour, "ids": []}
    return ouverts


def restants(request):
    """Sujets que le visiteur peut encore ouvrir aujourd'hui ; None pour un inscrit (pas de limite)."""
    if request.user.is_authenticated:
        return None
    return max(settings.PDF_VISITEUR_PAR_JOUR - len(_ouverts_aujourd_hui(request)["ids"]), 0)


def peut_ouvrir(request, sujet_pk):
    """Vrai si le visiteur peut ouvrir ce PDF ; le compte alors s'il ne l'avait pas encore ouvert aujourd'hui."""
    if request.user.is_authenticated:
        return True
    ouverts = _ouverts_aujourd_hui(request)
    if sujet_pk in ouverts["ids"]:
        return True
    ip = adresse_ip(request)
    if len(ouverts["ids"]) >= settings.PDF_VISITEUR_PAR_JOUR or PDF_VISITEURS_PAR_IP.atteinte(ip):
        return False
    PDF_VISITEURS_PAR_IP.compter(ip)
    ouverts["ids"].append(sujet_pk)
    request.session[CLE] = ouverts
    return True
