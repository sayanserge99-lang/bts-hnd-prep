import hashlib
import hmac
import json
from dataclasses import dataclass

from django.conf import settings


class NotificationInvalide(Exception):
    """Notification illisible ou mal signée : ignorée, jamais prise pour un paiement."""


@dataclass
class Notification:
    reference: str
    reussi: bool
    montant: int
    motif: str = ""


def signer(corps):
    return hmac.new(settings.PAIEMENT_SECRET.encode(), corps, hashlib.sha256).hexdigest()


class Fournisseur:
    """Ce que le site attend d'un agrégateur."""

    code = ""
    nom = ""  # nom commercial affiché à l'étudiant (« Paiement traité par … »)

    def initier(self, paiement, request):
        """Lance le paiement chez l'agrégateur. Renvoie l'adresse où envoyer l'étudiant, ou None s'il confirme
        sur son téléphone (demande de paiement poussée par l'opérateur)."""
        raise NotImplementedError

    def lire_notification(self, request):
        """Notification envoyée par l'agrégateur à /paiement/notification/ → Notification, ou NotificationInvalide."""
        return self.decoder(request.body, request.headers.get("X-Signature", ""))

    def decoder(self, corps, signature):
        if not hmac.compare_digest(signature, signer(corps)):
            raise NotificationInvalide("signature")
        try:
            donnees = json.loads(corps)
            return Notification(
                reference=str(donnees["reference"]), reussi=donnees["statut"] == "reussi",
                montant=int(donnees["montant"]), motif=str(donnees.get("motif", ""))[:200],
            )
        except (ValueError, KeyError, TypeError) as erreur:
            raise NotificationInvalide("format") from erreur

    def consulter(self, paiement):
        """Statut demandé directement à l'agrégateur (si la notification se perd) : Notification ou None."""
        return None
