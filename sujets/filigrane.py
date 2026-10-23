"""Protection des corrigés en PDF (CDC 4) : filigrane au nom du lecteur et lien temporaire.

Le filigrane n'empêche pas une copie, mais il dit d'où elle vient : un PDF partagé porte l'e-mail de
l'abonné qui l'a téléchargé. Le lien temporaire empêche de faire circuler l'adresse du PDF elle-même.
"""

import io
import math

from django.core import signing
from django.urls import reverse
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, FloatObject, NameObject

SEL = "sujets.pdf-corrige"
DUREE_LIEN = 15 * 60  # secondes


def lien_temporaire(corrige, utilisateur):
    """Adresse du PDF valable DUREE_LIEN secondes, pour ce lecteur seulement."""
    jeton = signing.TimestampSigner(salt=SEL).sign(f"{corrige.pk}:{utilisateur.pk or 0}")
    return f"{reverse('sujets:pdf_corrige', args=[corrige.pk])}?jeton={jeton}"


def jeton_valide(jeton, corrige, utilisateur):
    try:
        valeur = signing.TimestampSigner(salt=SEL).unsign(jeton or "", max_age=DUREE_LIEN)
    except signing.BadSignature:  # SignatureExpired en hérite
        return False
    return valeur == f"{corrige.pk}:{utilisateur.pk or 0}"


def _texte_pdf(texte):
    """Chaîne PDF littérale : parenthèses et barres obliques échappées, caractères hors latin-1 remplacés."""
    brut = texte.encode("cp1252", errors="replace")
    return brut.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _calque(ecrivain, largeur, hauteur, texte):
    """Page transparente : le texte en diagonale au centre, et en petit en bas de page."""
    page = ecrivain.add_blank_page(width=largeur, height=hauteur)
    police = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
        NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
    })
    transparence = DictionaryObject({
        NameObject("/Type"): NameObject("/ExtGState"),
        NameObject("/ca"): FloatObject(0.18),
        NameObject("/CA"): FloatObject(0.18),
    })
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): police}),
        NameObject("/ExtGState"): DictionaryObject({NameObject("/GS1"): transparence}),
    })
    angle = math.atan2(hauteur, largeur)
    cos, sin = math.cos(angle), math.sin(angle)
    taille = max(min(largeur, hauteur) / 22, 10)
    # Centre approximatif : Helvetica fait environ 0,5 × la taille par caractère.
    demi = len(texte) * taille * 0.25
    x, y = largeur / 2 - demi * cos, hauteur / 2 - demi * sin
    chaine = _texte_pdf(texte)
    flux = DecodedStreamObject()
    flux.set_data(
        b"q /GS1 gs 0.3 g BT /F1 %.1f Tf %.4f %.4f %.4f %.4f %.1f %.1f Tm (%s) Tj ET Q\n"
        % (taille, cos, sin, -sin, cos, x, y, chaine)
        + b"q 0.45 g BT /F1 7 Tf 1 0 0 1 24 12 Tm (%s) Tj ET Q\n" % chaine
    )
    page[NameObject("/Contents")] = ecrivain._add_object(flux)
    return page


def filigraner(contenu, texte):
    """Le PDF `contenu` (octets) avec `texte` sur chaque page ; renvoie des octets."""
    lecteur = PdfReader(io.BytesIO(contenu))
    sortie = PdfWriter()
    calques = PdfWriter()  # pages de filigrane, une par format de page rencontré
    par_format = {}
    for page in lecteur.pages:
        largeur, hauteur = float(page.mediabox.width), float(page.mediabox.height)
        cle = (round(largeur), round(hauteur))
        if cle not in par_format:
            par_format[cle] = _calque(calques, largeur, hauteur, texte)
        # La page est d'abord rattachée au fichier de sortie, puis fusionnée (exigence de pypdf 7).
        sortie.add_page(page).merge_page(par_format[cle])
    tampon = io.BytesIO()
    sortie.write(tampon)
    return tampon.getvalue()

