"""Double authentification de l'équipe : code à 6 chiffres d'une application (TOTP, RFC 6238).

Compatible avec Google Authenticator, Microsoft Authenticator, Aegis… Écrit ici (une trentaine de lignes)
plutôt qu'avec une bibliothèque : l'algorithme est court, et vérifié par les valeurs d'essai de la RFC.
"""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone

PAS = 30  # secondes de validité d'un code
CHIFFRES = 6
TOLERANCE = 1  # un pas avant ou après : horloge du téléphone un peu décalée
NOMBRE_CODES_SECOURS = 10
EMETTEUR = "BTS-HND Prep"
CLE_SESSION = "double_auth_verifiee"


def nouveau_secret():
    """160 bits aléatoires en base32, comme le recommande la RFC 4226."""
    return base64.b32encode(secrets.token_bytes(20)).decode()


def code(secret, pas, chiffres=CHIFFRES, algorithme=hashlib.sha1):
    """Code TOTP du pas donné (RFC 6238, troncature dynamique de la RFC 4226)."""
    cle = base64.b32decode(secret)
    empreinte = hmac.new(cle, struct.pack(">Q", pas), algorithme).digest()
    decalage = empreinte[-1] & 0x0F
    nombre = struct.unpack(">I", empreinte[decalage:decalage + 4])[0] & 0x7FFFFFFF
    return str(nombre % 10**chiffres).zfill(chiffres)


def pas_actuel(maintenant=None):
    return int((maintenant if maintenant is not None else time.time()) // PAS)


def verifier_code(double_auth, saisie, maintenant=None):
    """Vrai si `saisie` est le code du moment ; un code déjà utilisé ne sert pas deux fois (anti-rejeu)."""
    saisie = "".join(caractere for caractere in saisie if caractere.isdigit())
    if len(saisie) != CHIFFRES:
        return False
    courant = pas_actuel(maintenant)
    for pas in range(courant - TOLERANCE, courant + TOLERANCE + 1):
        if pas <= double_auth.dernier_pas:
            continue
        if hmac.compare_digest(code(double_auth.secret, pas), saisie):
            double_auth.dernier_pas = pas
            double_auth.save(update_fields=["dernier_pas"])
            return True
    return False


def nouveaux_codes_secours(double_auth):
    """10 codes à usage unique (téléphone perdu), montrés une seule fois ; seules leurs empreintes sont gardées."""
    codes = [f"{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}" for _ in range(NOMBRE_CODES_SECOURS)]
    double_auth.codes_secours = [make_password(valeur) for valeur in codes]
    double_auth.save(update_fields=["codes_secours"])
    return codes


def utiliser_code_secours(double_auth, saisie):
    saisie = saisie.strip().upper()
    for empreinte in double_auth.codes_secours:
        if check_password(saisie, empreinte):
            double_auth.codes_secours = [autre for autre in double_auth.codes_secours if autre != empreinte]
            double_auth.save(update_fields=["codes_secours"])
            return True
    return False


def adresse_application(double_auth):
    """otpauth://… lu par l'application quand on scanne le QR code."""
    compte = quote(f"{EMETTEUR}:{double_auth.utilisateur.email}")
    return f"otpauth://totp/{compte}?secret={double_auth.secret}&issuer={quote(EMETTEUR)}&digits={CHIFFRES}&period={PAS}"


def qr_code_svg(texte):
    import qrcode
    import qrcode.image.svg

    return qrcode.make(texte, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2).to_string(encoding="unicode")


def marquer_verifiee(request):
    request.session[CLE_SESSION] = request.user.pk


def est_verifiee(request):
    return request.session.get(CLE_SESSION) == request.user.pk


def activer(double_auth):
    double_auth.active_le = timezone.now()
    double_auth.save(update_fields=["active_le"])
