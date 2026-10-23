"""Protections communes : limites anti-abus et en-têtes de sécurité.

Les limites comptent dans le cache Redis (partagé entre les processus Gunicorn) ; une limite atteinte
bloque pendant `duree` secondes à partir de la première tentative comptée.
"""

from django.conf import settings
from django.core.cache import cache


def adresse_ip(request):
    # Derrière Nginx, REMOTE_ADDR est celle de Nginx : l'adresse du visiteur est dans X-Real-IP,
    # que Nginx écrase toujours (deploy/nginx.conf). Sans proxy, cet en-tête serait falsifiable.
    if settings.DERRIERE_PROXY:
        return request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR", "")
    return request.META.get("REMOTE_ADDR", "")


class Limite:
    """Au plus `maximum` événements par `duree` secondes pour une même clé (compte, adresse IP…)."""

    def __init__(self, nom, maximum, duree):
        self.nom, self.maximum, self.duree = nom, maximum, duree

    def _cle(self, valeur):
        return f"limite:{self.nom}:{valeur}"

    def atteinte(self, valeur):
        return cache.get(self._cle(valeur), 0) >= self.maximum

    def compter(self, valeur):
        cle = self._cle(valeur)
        # add() ne remet pas le compteur à zéro s'il existe : la durée court depuis le premier événement.
        cache.add(cle, 0, timeout=self.duree)
        try:
            cache.incr(cle)
        except ValueError:  # expiré entre les deux appels
            cache.set(cle, 1, timeout=self.duree)

    def effacer(self, valeur):
        cache.delete(self._cle(valeur))


# Connexion : 5 échecs par compte (réglage existant) et 20 par adresse IP, qui arrête aussi l'essai d'un même
# mot de passe sur des milliers de comptes. Une école entière derrière une seule adresse reste sous 20.
CONNEXION_PAR_IP = Limite("connexion-ip", 20, 15 * 60)
INSCRIPTIONS_PAR_IP = Limite("inscription-ip", 5, 60 * 60)
REINITIALISATIONS_PAR_IP = Limite("reinitialisation-ip", 5, 60 * 60)
REINITIALISATIONS_PAR_EMAIL = Limite("reinitialisation-email", 3, 60 * 60)
SIGNALEMENTS_CORRIGE_PAR_COMPTE = Limite("signalement-corrige", 10, 24 * 60 * 60)


class EnTetesDeSecurite:
    """Content-Security-Policy et Permissions-Policy sur toutes les réponses.

    Scripts : uniquement ceux du site (aucun script en ligne) — un texte piégé ne peut donc rien exécuter,
    même s'il passait le nettoyage du HTML. Styles en ligne tolérés (largeurs des barres de progression) :
    sans danger pour exécuter du code.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        formulaires = " ".join(["'self'", *settings.CSP_FORM_ACTION_EN_PLUS])
        self.csp = "; ".join([
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data:",
            "font-src 'self'",
            "connect-src 'self'",
            "object-src 'none'",
            "base-uri 'self'",
            f"form-action {formulaires}",
            "frame-ancestors 'none'",
        ])

    def __call__(self, request):
        reponse = self.get_response(request)
        reponse.setdefault("Content-Security-Policy", self.csp)
        reponse.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()")
        return reponse
