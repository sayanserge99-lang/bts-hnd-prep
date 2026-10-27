"""Suivi des erreurs avec Sentry : être prévenu quand une page plante chez un étudiant.

Inactif sans SENTRY_DSN (développement, tests). Respect de la loi n° 2024/017 : aucune donnée personnelle
n'est envoyée — ni e-mail, ni cookies, ni contenu des formulaires, ni adresse IP.
"""

import os

# Champs retirés de tout événement envoyé, quel que soit l'endroit où ils apparaissent.
SENSIBLES = {"cookie", "cookies", "authorization", "x-signature", "password", "mot_de_passe", "csrfmiddlewaretoken",
             "sessionid", "csrftoken", "secret", "jeton", "code", "telephone", "email"}


def _nettoyer(valeur):
    if isinstance(valeur, dict):
        return {cle: "[retiré]" if str(cle).lower() in SENSIBLES else _nettoyer(contenu) for cle, contenu in valeur.items()}
    if isinstance(valeur, list):
        return [_nettoyer(element) for element in valeur]
    return valeur


def avant_envoi(evenement, indice):
    requete = evenement.get("request") or {}
    requete.pop("cookies", None)
    requete.pop("data", None)  # contenu des formulaires
    if "headers" in requete:
        requete["headers"] = _nettoyer(requete["headers"])
    if "query_string" in requete:
        requete["query_string"] = "[retiré]"  # ?jeton=… des liens temporaires, ?next=…
    evenement["user"] = {}  # ni e-mail, ni identifiant, ni adresse IP
    return _nettoyer(evenement)


def options(dsn):
    """Réglages de Sentry, partagés avec les tests (qui vérifient ce qui serait envoyé)."""
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    return {
        "dsn": dsn,
        "integrations": [DjangoIntegration(), CeleryIntegration()],
        "environment": os.environ.get("SENTRY_ENVIRONNEMENT", "production"),
        # Données personnelles : par défaut, Sentry n'en joint pas ; avant_envoi retire le reste, et
        # config/tests/test_suivi_erreurs.py vérifie ce qui partirait réellement.
        # Les variables locales du code qui plante contiennent la requête (adresse avec ?jeton=…), l'utilisateur,
        # parfois le formulaire : jamais envoyées. La pile d'appels (fichier, ligne) suffit à corriger.
        "include_local_variables": False,
        "before_send": avant_envoi,
        # Petite part des pages mesurée (lenteurs) : assez pour voir une page lente, léger pour le quota gratuit.
        "traces_sample_rate": float(os.environ.get("SENTRY_TRACES", "0.05")),
    }


def demarrer():
    dsn = os.environ.get("SENTRY_DSN", "")
    if not dsn:
        return False
    import sentry_sdk

    sentry_sdk.init(**options(dsn))
    return True
