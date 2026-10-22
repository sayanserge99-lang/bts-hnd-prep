"""Traitement d'un PDF de sujet : texte pour la recherche, OCR des scans, compression (CDC 4 et 5)."""

import logging
import subprocess
from pathlib import Path

from pypdf import PdfReader

journal = logging.getLogger(__name__)

# En dessous, on considère que le PDF est un scan sans texte exploitable.
TEXTE_MINIMUM = 50
DELAI_OUTIL = 8 * 60

# Langues Tesseract : un sujet BTS peut contenir de l'anglais (épreuve d'anglais).
LANGUES_OCR = {"fr": "fra+eng", "en": "eng"}


def extraire_texte(chemin):
    """Texte et nombre de pages. Les caractères nuls sont retirés : PostgreSQL les refuse."""
    lecteur = PdfReader(str(chemin))
    pages = [page.extract_text() or "" for page in lecteur.pages]
    return "\n".join(pages).replace("\x00", "").strip(), len(lecteur.pages)


def a_du_texte(texte):
    return len(texte.strip()) >= TEXTE_MINIMUM


def _lancer(commande):
    try:
        subprocess.run(commande, check=True, capture_output=True, timeout=DELAI_OUTIL)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as erreur:
        sortie = getattr(erreur, "stderr", b"") or b""
        journal.warning("Échec de %s : %s %s", commande[0], erreur, sortie.decode(errors="replace")[-500:])
        return False


def ajouter_couche_texte(source, destination, langue_examen):
    """OCR des pages sans texte (un scan ou une photo devient cherchable). Faux en cas d'échec."""
    return _lancer([
        "ocrmypdf", "--mode", "skip", "--output-type", "pdf", "--optimize", "0", "--quiet",
        "-l", LANGUES_OCR[langue_examen], str(source), str(destination),
    ])


def compresser(source, destination):
    """Réduit les images à 150 ppp (lisible à l'écran et à l'impression). Faux en cas d'échec."""
    return _lancer([
        "gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.5", "-dPDFSETTINGS=/ebook",
        "-dNOPAUSE", "-dQUIET", "-dBATCH", f"-sOutputFile={destination}", str(source),
    ])


def traiter(source, dossier, langue_examen):
    """Enchaîne OCR (si nécessaire) et compression dans `dossier`.

    Renvoie (chemin du PDF à garder, texte, nombre de pages). Le chemin vaut `source`
    quand aucune étape n'a produit de meilleur fichier.
    """
    dossier = Path(dossier)
    retenu = Path(source)
    texte, pages = extraire_texte(retenu)

    if not a_du_texte(texte):
        ocr = dossier / "ocr.pdf"
        if ajouter_couche_texte(retenu, ocr, langue_examen):
            retenu = ocr
            texte, pages = extraire_texte(retenu)

    compresse = dossier / "compresse.pdf"
    if compresser(retenu, compresse) and compresse.stat().st_size < retenu.stat().st_size:
        retenu = compresse
        # Ghostscript conserve le texte ; on le relit pour rester exact.
        texte, pages = extraire_texte(retenu)

    return retenu, texte, pages
