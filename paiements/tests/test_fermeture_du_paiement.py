"""CDC 10.4 : le paiement reste fermé tant que la structure ET le NIU ne sont pas renseignés.

La règle est calculée dans config/settings.py à partir des variables d'environnement : on la calcule ici dans un
processus neuf, avec les variables de chaque cas, comme au démarrage du serveur."""

import os
import subprocess
import sys

import pytest
from django.conf import settings


def paiement_actif(**variables):
    environnement = {
        **{cle: valeur for cle, valeur in os.environ.items() if not cle.startswith(("EXPLOITANT_", "PAIEMENT_"))},
        "DJANGO_SETTINGS_MODULE": "config.settings", "DJANGO_DEBUG": "0", "DJANGO_SECRET_KEY": "essai", **variables,
    }
    resultat = subprocess.run(
        [sys.executable, "-c", "import django; django.setup(); from django.conf import settings; print(settings.PAIEMENT_ACTIF)"],
        cwd=settings.BASE_DIR, env=environnement, capture_output=True, text=True, timeout=60,
    )
    assert resultat.returncode == 0, resultat.stderr
    return resultat.stdout.strip() == "True"


@pytest.mark.parametrize("variables, ouvert", [
    ({}, False),
    ({"EXPLOITANT_STRUCTURE": "BTS-HND Prep SARL"}, False),
    ({"EXPLOITANT_NIU": "M012345678901A"}, False),
    ({"EXPLOITANT_STRUCTURE": "BTS-HND Prep SARL", "EXPLOITANT_NIU": "M012345678901A"}, True),
    # L'essai du parcours (agrégateur simulé) n'ouvre rien hors du mode développement.
    ({"PAIEMENT_ESSAI": "1"}, False),
    ({"PAIEMENT_ESSAI": "1", "DJANGO_DEBUG": "1"}, True),
])
def test_le_paiement_s_ouvre_seulement_avec_la_structure_et_le_niu(variables, ouvert):
    assert paiement_actif(**variables) is ouvert
