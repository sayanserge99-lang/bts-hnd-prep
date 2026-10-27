"""JavaScript de l'examen blanc (static/js/examen.js) essayé dans jsdom sur la vraie page d'épreuve.

Une question à la fois, grille, marques, touche Entrée, confirmation ; et à 0:00 : copie fermée, réponses
figées envoyées tout de suite, rien de modifié ensuite. Sauté si Node ou jsdom manquent (npm ci --prefix tests_js).
"""

import shutil
import subprocess
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

from accounts.models import ProfilEtude, Utilisateur
from catalogue.models import Chapitre
from entrainement.models import Choix, ExamenBlanc, Question, Tentative
from sujets.models import Sujet

pytestmark = pytest.mark.django_db

DOSSIER = Path(settings.BASE_DIR) / "tests_js"
NODE = shutil.which("node")


@pytest.fixture
def page_d_epreuve(client, creer_sujet, session_terminee, comptabilite, compta_generale, tmp_path):
    if not NODE or not (DOSSIER / "node_modules" / "jsdom").exists():
        pytest.skip("Node ou jsdom absent : npm ci --prefix tests_js")
    sujet = creer_sujet(session_terminee, statut=Sujet.Statut.PUBLIE)
    chapitre = Chapitre.objects.create(matiere=compta_generale, titre="Amortissements", ordre=1)
    questions = []
    for numero in range(3):
        question = Question.objects.create(chapitre=chapitre, type="choix_unique", enonce=f"Question {numero}", langue="fr", publiee=True)
        Choix.objects.create(question=question, texte="Bonne", est_correct=True)
        Choix.objects.create(question=question, texte="Mauvaise", est_correct=False)
        questions.append(question)
    examen = ExamenBlanc.objects.create(titre="Examen blanc", sujet=sujet, duree=240, points_qcm=6, publie=True)
    examen.questions.set(questions)
    etudiant = Utilisateur.objects.create_user(email="awa@example.com", password="Revision-2027")
    ProfilEtude.objects.create(utilisateur=etudiant, examen=comptabilite.examen, specialite=comptabilite)
    client.force_login(etudiant)
    client.post(reverse("entrainement:demarrer_examen", args=[examen.pk]))
    tentative = Tentative.objects.get()
    # Deux réponses déjà enregistrées, la troisième pas encore.
    client.post(reverse("entrainement:enregistrer", args=[tentative.pk]), {
        f"q-{questions[0].pk}": questions[0].choix.first().pk, f"q-{questions[1].pk}": questions[1].choix.first().pk,
    })
    page = tmp_path / "epreuve.html"
    page.write_text(client.get(reverse("entrainement:epreuve", args=[tentative.pk])).content.decode(), encoding="utf-8")
    return page


@pytest.mark.parametrize("essai", ["examen-navigation.js", "examen-verrou.js"])
def test_le_javascript_de_l_examen(page_d_epreuve, essai):
    script = Path(settings.BASE_DIR) / "static" / "js" / "examen.js"
    resultat = subprocess.run([NODE, essai, str(page_d_epreuve), str(script)], cwd=DOSSIER, capture_output=True, text=True, timeout=60)
    assert resultat.returncode == 0, resultat.stdout + resultat.stderr
    assert "OK" in resultat.stdout
