"""Connexion avec Google (CDC 3.1, V2) : OpenID Connect, flux « code d'autorisation » avec PKCE.

Inactive tant que GOOGLE_CLIENT_ID et GOOGLE_CLIENT_SECRET ne sont pas renseignés.
"""

import base64
import hashlib
import json
import secrets
import time
import urllib.parse
import urllib.request

from django.conf import settings

AUTORISATION = "https://accounts.google.com/o/oauth2/v2/auth"
JETON = "https://oauth2.googleapis.com/token"
EMETTEURS = {"https://accounts.google.com", "accounts.google.com"}
CLE_SESSION = "connexion_google"


class RefusGoogle(Exception):
    """Réponse de Google absente, falsifiée ou inutilisable : on ne connecte personne."""


def est_active():
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)


def _base64url(octets):
    return base64.urlsafe_b64encode(octets).rstrip(b"=").decode()


def preparer(session, adresse_retour, suite):
    """Adresse Google vers laquelle envoyer l'étudiant ; les secrets du tour restent dans sa session."""
    etat, nonce, verificateur = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    session[CLE_SESSION] = {"etat": etat, "nonce": nonce, "verificateur": verificateur, "suite": suite}
    parametres = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": adresse_retour,
        "response_type": "code",
        "scope": "openid email profile",
        "state": etat,
        "nonce": nonce,
        # PKCE : un code intercepté ne sert à rien sans le vérificateur, resté sur le serveur.
        "code_challenge": _base64url(hashlib.sha256(verificateur.encode()).digest()),
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    return f"{AUTORISATION}?{urllib.parse.urlencode(parametres)}"


def demander_jeton(code, verificateur, adresse_retour):
    """Échange le code contre l'identité, directement auprès de Google (connexion HTTPS)."""
    corps = urllib.parse.urlencode({
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": adresse_retour,
        "grant_type": "authorization_code",
        "code_verifier": verificateur,
    }).encode()
    requete = urllib.request.Request(JETON, data=corps, method="POST")
    try:
        with urllib.request.urlopen(requete, timeout=10) as reponse:
            return json.load(reponse)
    except (OSError, ValueError) as erreur:
        raise RefusGoogle("échange du code impossible") from erreur


def lire_identite(jeton_id):
    """Contenu du jeton d'identité.

    Sa signature n'est pas vérifiée : il vient d'être reçu de Google lui-même, par HTTPS, en échange
    du code et du secret client (OpenID Connect Core, 3.1.3.7). On vérifie en revanche son contenu.
    """
    try:
        contenu = jeton_id.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(contenu + "=" * (-len(contenu) % 4)))
    except (AttributeError, IndexError, ValueError) as erreur:
        raise RefusGoogle("jeton d'identité illisible") from erreur


def terminer(session, parametres, adresse_retour):
    """Retour de Google : renvoie (e-mail, prénom, nom, adresse de suite) ou lève RefusGoogle."""
    tour = session.pop(CLE_SESSION, None)
    if not tour or not parametres.get("state") or not secrets.compare_digest(parametres["state"], tour["etat"]):
        raise RefusGoogle("état absent ou différent (lien rejoué ou falsifié)")
    if parametres.get("error") or not parametres.get("code"):
        raise RefusGoogle("connexion annulée chez Google")

    identite = lire_identite(demander_jeton(parametres["code"], tour["verificateur"], adresse_retour).get("id_token"))
    if identite.get("iss") not in EMETTEURS:
        raise RefusGoogle("émetteur inconnu")
    if identite.get("aud") != settings.GOOGLE_CLIENT_ID:
        raise RefusGoogle("jeton destiné à un autre site")
    if not isinstance(identite.get("exp"), int | float) or identite["exp"] < time.time():
        raise RefusGoogle("jeton expiré")
    if not secrets.compare_digest(str(identite.get("nonce", "")), tour["nonce"]):
        raise RefusGoogle("nonce différent")
    # Sans e-mail vérifié par Google, on pourrait se faire passer pour le titulaire d'une adresse.
    if not identite.get("email") or identite.get("email_verified") is not True:
        raise RefusGoogle("e-mail non vérifié par Google")
    return identite["email"].lower(), identite.get("given_name", ""), identite.get("family_name", ""), tour["suite"]
