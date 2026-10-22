from datetime import date, timedelta

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from catalogue.models import Examen, Matiere, Session, Specialite, SpecialiteMatiere
from sujets.models import Sujet


@pytest.fixture(autouse=True)
def media_temporaire(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture(autouse=True)
def cache_isole(settings):
    # Cache en mémoire propre à chaque test : pas de Redis partagé avec le serveur de développement,
    # et aucun échec de connexion qui passe d'un test à l'autre.
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    cache.clear()


@pytest.fixture
def bts(db):
    return Examen.objects.create(code=Examen.Code.BTS, nom="Brevet de Technicien Supérieur", langue="fr")


@pytest.fixture
def session_terminee(bts):
    return Session.objects.create(
        examen=bts, annee=2025, date_debut=date(2025, 4, 14), date_fin_officielle=date(2025, 6, 27)
    )


@pytest.fixture
def session_en_cours(bts):
    aujourd_hui = timezone.localdate()
    return Session.objects.create(
        examen=bts,
        annee=aujourd_hui.year + 1,
        date_debut=aujourd_hui - timedelta(days=5),
        date_fin_officielle=aujourd_hui + timedelta(days=30),
    )


@pytest.fixture
def comptabilite(bts):
    return Specialite.objects.create(
        examen=bts, code="CGE", nom="Comptabilité et gestion des entreprises", filiere="commerciale"
    )


@pytest.fixture
def marketing(bts):
    return Specialite.objects.create(examen=bts, code="MCV", nom="Marketing, commerce, vente", filiere="commerciale")


@pytest.fixture
def compta_generale(bts, comptabilite):
    matiere = Matiere.objects.create(examen=bts, nom="Comptabilité générale")
    SpecialiteMatiere.objects.create(specialite=comptabilite, matiere=matiere, coefficient=4)
    return matiere


@pytest.fixture
def creer_sujet(compta_generale):
    def _creer(session, **champs):
        valeurs = {
            "titre": "Comptabilité générale",
            "session": session,
            "matiere": compta_generale,
            "type_epreuve": Sujet.TypeEpreuve.ECRITE,
            "duree": 240,
            "fichier": SimpleUploadedFile("sujet.pdf", b"%PDF-1.4", content_type="application/pdf"),
            "source": f"MINESUP, BTS session {session.annee}",
        }
        valeurs.update(champs)
        return Sujet.objects.create(**valeurs)

    return _creer
