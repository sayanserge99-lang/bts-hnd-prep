import shutil
import tempfile
from pathlib import Path

from celery import shared_task
from django.core.files import File

from . import traitement_pdf
from .models import Sujet


@shared_task
def traiter_pdf_du_sujet(sujet_id):
    """Après l'ajout d'un PDF : OCR si c'est un scan, compression, texte et pages, index de recherche."""
    sujet = Sujet.objects.select_related("session__examen", "matiere").filter(pk=sujet_id).first()
    if sujet is None or not sujet.fichier:
        return

    ancien_nom = sujet.fichier.name
    with tempfile.TemporaryDirectory() as dossier:
        source = Path(dossier) / "source.pdf"
        with sujet.fichier.open("rb") as entree, source.open("wb") as sortie:
            shutil.copyfileobj(entree, sortie)

        retenu, texte, pages = traitement_pdf.traiter(source, dossier, sujet.session.examen.langue)

        champs = {"texte_extrait": texte, "nb_pages": pages}
        if retenu != source:
            # Nouveau fichier plus léger (ou devenu cherchable) : il remplace l'original.
            with retenu.open("rb") as fichier:
                champs["fichier"] = sujet.fichier.storage.save(ancien_nom, File(fichier))

    # update() et non save() : save() relancerait cette tâche.
    Sujet.objects.filter(pk=sujet_id).update(**champs)
    if "fichier" in champs and champs["fichier"] != ancien_nom:
        sujet.fichier.storage.delete(ancien_nom)

    sujet.refresh_from_db()
    sujet.mettre_a_jour_recherche()
