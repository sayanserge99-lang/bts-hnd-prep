"""Traitement des PDF par Celery : texte, OCR des scans, compression (CDC 4 et 5)."""

import io
import os
import shutil

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from catalogue.management.commands.donnees_demo import pdf_demo
from sujets import tasks, traitement_pdf
from sujets.models import Sujet

OUTILS_PRESENTS = all(shutil.which(outil) for outil in ("tesseract", "gs", "ocrmypdf"))
avec_outils = pytest.mark.skipif(not OUTILS_PRESENTS, reason="Tesseract, Ghostscript ou OCRmyPDF absent (tourne dans Docker et la CI)")


def page_image(lignes, largeur=1240, hauteur=1754, taille=56, fond=None):
    """Page A4 sous forme d'image : un sujet scanné ou photographié, sans texte exploitable."""
    from PIL import Image, ImageDraw, ImageFont

    image = fond or Image.new("RGB", (largeur, hauteur), "white")
    dessin = ImageDraw.Draw(image)
    police = ImageFont.load_default(size=taille)
    for numero, ligne in enumerate(lignes):
        dessin.text((120, 160 + numero * taille * 2), ligne, fill="black", font=police)
    return image


def en_pdf(image, resolution):
    tampon = io.BytesIO()
    image.save(tampon, "PDF", resolution=resolution)
    return tampon.getvalue()


@pytest.fixture
def pdf_texte(tmp_path):
    chemin = tmp_path / "texte.pdf"
    chemin.write_bytes(pdf_demo("Comptabilité générale", 2025))
    return chemin


@pytest.fixture
def pdf_scan(tmp_path):
    chemin = tmp_path / "scan.pdf"
    chemin.write_bytes(en_pdf(page_image(["EXERCICE 2", "AMORTISSEMENT DEGRESSIF", "BILAN COMPTABLE"]), 150))
    return chemin


def test_extraire_le_texte_d_un_pdf(pdf_texte):
    texte, pages = traitement_pdf.extraire_texte(pdf_texte)
    assert "demonstration" in texte
    assert pages == 1


def test_un_scan_n_a_pas_de_texte_avant_l_ocr(pdf_scan):
    texte, _ = traitement_pdf.extraire_texte(pdf_scan)
    assert not traitement_pdf.a_du_texte(texte)


def test_si_les_outils_echouent_on_garde_l_original(pdf_scan, tmp_path, monkeypatch):
    monkeypatch.setattr(traitement_pdf, "_lancer", lambda commande: False)

    retenu, texte, pages = traitement_pdf.traiter(pdf_scan, tmp_path, "fr")

    assert retenu == pdf_scan
    assert pages == 1


@avec_outils
def test_l_ocr_rend_un_scan_cherchable(pdf_scan, tmp_path):
    retenu, texte, pages = traitement_pdf.traiter(pdf_scan, tmp_path, "fr")

    assert retenu != pdf_scan
    assert "AMORTISSEMENT" in texte.upper()
    assert pages == 1


@avec_outils
def test_la_compression_allege_un_scan_lourd(tmp_path):
    from PIL import Image

    # Scan à 300 ppp avec du grain, comme une photocopie : lourd tant qu'il n'est pas réduit.
    fond = Image.effect_noise((2480, 3508), 60).convert("RGB")
    source = tmp_path / "lourd.pdf"
    source.write_bytes(en_pdf(page_image(["SUJET"], 2480, 3508, 120, fond), 300))
    destination = tmp_path / "leger.pdf"

    assert traitement_pdf.compresser(source, destination)
    assert destination.stat().st_size < source.stat().st_size / 2


@pytest.mark.django_db
def test_un_nouveau_pdf_lance_le_traitement_une_seule_fois(
    creer_sujet, session_terminee, monkeypatch, django_capture_on_commit_callbacks
):
    lances = []
    monkeypatch.setattr(tasks.traiter_pdf_du_sujet, "delay", lances.append)

    with django_capture_on_commit_callbacks(execute=True):
        sujet = creer_sujet(session_terminee)
    assert lances == [sujet.pk]

    # Modifier le titre ne relance rien ; remplacer le fichier, si.
    with django_capture_on_commit_callbacks(execute=True):
        sujet.titre = "Nouveau titre"
        sujet.save()
    assert lances == [sujet.pk]

    with django_capture_on_commit_callbacks(execute=True):
        sujet.fichier = SimpleUploadedFile("nouveau.pdf", b"%PDF-1.4", content_type="application/pdf")
        sujet.save()
    assert lances == [sujet.pk, sujet.pk]


@pytest.mark.django_db
def test_la_tache_ignore_un_sujet_supprime():
    tasks.traiter_pdf_du_sujet(987654)


@avec_outils
@pytest.mark.django_db
def test_la_tache_complete_le_sujet_et_l_index_de_recherche(creer_sujet, session_terminee, pdf_scan):
    sujet = creer_sujet(
        session_terminee, titre="Épreuve de 2025",
        fichier=SimpleUploadedFile("scan.pdf", pdf_scan.read_bytes(), content_type="application/pdf"),
    )
    ancien = sujet.fichier.path

    tasks.traiter_pdf_du_sujet(sujet.pk)

    sujet.refresh_from_db()
    assert sujet.nb_pages == 1
    assert "AMORTISSEMENT" in sujet.texte_extrait.upper()
    assert Sujet.objects.rechercher("amortissement", "fr").filter(pk=sujet.pk).exists()
    # Le fichier traité remplace l'original, qui est supprimé.
    assert sujet.fichier.path != ancien
    assert not os.path.exists(ancien)
