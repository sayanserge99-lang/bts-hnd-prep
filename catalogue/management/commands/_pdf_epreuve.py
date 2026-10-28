"""PDF texte d'une épreuve provisoire (A4, plusieurs pages, accents), sans dépendance.

Polices standard Helvetica et Helvetica-Bold en WinAnsiEncoding : les caractères français s'affichent et
pypdf les relit à l'extraction du texte (recherche plein texte)."""

import re
import textwrap

LARGEUR, HAUTEUR, MARGE = 595, 842, 56
TAILLE, INTERLIGNE, COLONNES = 11, 15, 92
COLONNES_GRAS = 82  # le gras est plus large
INSECABLE = " "


def insecable(ligne):
    """Espaces insécables dans les nombres (« 2 000 000 ») et devant « : ; ? ! % » : jamais coupés en fin de ligne."""
    ligne = re.sub(r"(?<=\d) (?=\d{3}\b)", INSECABLE, ligne)
    return re.sub(r" (?=[:;?!%])", INSECABLE, ligne)


def _echapper(ligne):
    octets = ligne.encode("cp1252", "replace")
    return octets.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _lignes(entete, texte):
    """[(police, taille, ligne)] : en-tête en gras, titres « # » en gras, le reste découpé à la largeur de page."""
    # Bandeau en gras sous le titre : durée, puis la mention « épreuve provisoire » (jamais prise pour un vrai sujet).
    lignes = [("F2", 13, entete[0])]
    lignes += [("F2", TAILLE, morceau) for ligne in entete[1:] for morceau in textwrap.wrap(insecable(ligne), COLONNES_GRAS)]
    lignes.append(("F1", TAILLE, ""))
    for brute in texte.strip().splitlines():
        if brute.startswith("# "):
            lignes += [("F1", TAILLE, ""), ("F2", 12, brute[2:])]
        else:
            retrait = "   " if brute[:2].rstrip(".").isdigit() or brute.startswith("- ") else ""
            morceaux = textwrap.wrap(insecable(brute), COLONNES, subsequent_indent=retrait) or [""]
            lignes += [("F1", TAILLE, morceau) for morceau in morceaux]
    return lignes


def pdf_epreuve(entete, texte):
    """Renvoie (octets du PDF, nombre de pages, texte brut pour la recherche)."""
    lignes = _lignes(entete, texte)
    par_page = (HAUTEUR - 2 * MARGE) // INTERLIGNE
    pages = [lignes[i:i + par_page] for i in range(0, len(lignes), par_page)]
    flux = []
    for numero, page in enumerate(pages, start=1):
        contenu = bytearray(b"BT ")
        y = HAUTEUR - MARGE
        for police, taille, ligne in page:
            contenu += f"/{police} {taille} Tf 1 0 0 1 {MARGE} {y} Tm (".encode() + _echapper(ligne) + b") Tj "
            y -= INTERLIGNE
        pied = f"{entete[0]} - page {numero}/{len(pages)}"
        contenu += f"/F1 8 Tf 1 0 0 1 {MARGE} 30 Tm (".encode() + _echapper(pied) + b") Tj ET"
        flux.append(bytes(contenu))

    nb = len(pages)
    # Objets : 1 catalogue, 2 pages, 3 Helvetica, 4 Helvetica-Bold, puis (page, contenu) pour chaque page.
    objets = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [" + b" ".join(f"{5 + 2 * i} 0 R".encode() for i in range(nb)) + b"] /Count " + str(nb).encode() + b" >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    ]
    for i, contenu in enumerate(flux):
        objets.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {LARGEUR} {HAUTEUR}] /Contents {6 + 2 * i} 0 R "
            "/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> >>".encode()
        )
        objets.append(b"<< /Length " + str(len(contenu)).encode() + b" >>\nstream\n" + contenu + b"\nendstream")

    sortie = bytearray(b"%PDF-1.4\n")
    positions = []
    for numero, objet in enumerate(objets, start=1):
        positions.append(len(sortie))
        sortie += f"{numero} 0 obj\n".encode() + objet + b"\nendobj\n"
    debut_xref = len(sortie)
    sortie += f"xref\n0 {len(objets) + 1}\n0000000000 65535 f \n".encode()
    for position in positions:
        sortie += f"{position:010d} 00000 n \n".encode()
    sortie += f"trailer\n<< /Size {len(objets) + 1} /Root 1 0 R >>\nstartxref\n{debut_xref}\n%%EOF\n".encode()
    texte_brut = "\n".join(ligne for _, _, ligne in lignes).replace(INSECABLE, " ")
    return bytes(sortie), nb, texte_brut
