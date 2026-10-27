"""Suivi des erreurs (Sentry) : inactif sans adresse, et rien de personnel dans ce qui est envoyé."""

import pytest
import sentry_sdk
from django.http import HttpResponse
from django.urls import path
from sentry_sdk.transport import Transport

from accounts.models import Utilisateur
from config import suivi_erreurs

pytestmark = pytest.mark.django_db


def plante(request):
    raise RuntimeError("erreur volontaire")


def bien(request):
    return HttpResponse("ok")


urlpatterns = [path("plante/", plante), path("bien/", bien)]


class Capture(Transport):
    """Garde les événements au lieu de les envoyer à sentry.io."""

    def __init__(self, options=None):
        super().__init__(options)
        self.evenements = []

    def capture_envelope(self, enveloppe):
        evenement = enveloppe.get_event()
        if evenement:
            self.evenements.append(evenement)


@pytest.fixture
def sentry_capture(settings):
    settings.ROOT_URLCONF = __name__
    transport = Capture()
    # Exactement les réglages de production, avec un transport qui garde les événements au lieu de les envoyer.
    sentry_sdk.init(**{**suivi_erreurs.options("https://cle@exemple.invalid/1"), "transport": transport, "traces_sample_rate": 0})
    yield transport
    sentry_sdk.get_client().close()
    sentry_sdk.init()  # plus rien d'actif pour les autres tests


def test_inactif_sans_adresse(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    assert suivi_erreurs.demarrer() is False


def test_une_page_qui_plante_est_signalee_sans_donnee_personnelle(client, sentry_capture):
    awa = Utilisateur.objects.create_user(email="awa@example.com", password="Revision-2027")
    client.force_login(awa)
    client.raise_request_exception = False
    client.cookies["sessionid_temoin"] = "valeur-secrete"

    reponse = client.post("/plante/?jeton=abc123", {"telephone": "677123456", "motif": "texte de l'étudiant"},
                          HTTP_AUTHORIZATION="Bearer secret-xyz", REMOTE_ADDR="198.51.100.4")
    sentry_sdk.flush()

    assert reponse.status_code == 500
    assert len(sentry_capture.evenements) == 1
    envoye = repr(sentry_capture.evenements[0])
    assert "erreur volontaire" in envoye  # l'erreur elle-même est bien là
    for secret in ("awa@example.com", "valeur-secrete", "abc123", "677123456", "texte de l'étudiant", "secret-xyz", "198.51.100.4"):
        assert secret not in envoye, secret
    assert sentry_capture.evenements[0]["user"] == {}


def test_rien_n_est_envoye_quand_tout_va_bien(client, sentry_capture):
    assert client.get("/bien/").status_code == 200
    sentry_sdk.flush()
    assert sentry_capture.evenements == []
