"""Rendu des corrigés (CDC 3.3) : Markdown, tableaux, code et formules mathématiques.

Les formules ($...$ en ligne, $$...$$ en bloc) deviennent du MathML, affiché nativement par les
navigateurs : aucun JavaScript à télécharger (CDC 4, connexion lente). Le HTML est toujours
nettoyé, car les corrigés de la communauté (V3) seront écrits par n'importe quel inscrit.
"""

import re

import markdown
import nh3
from django.utils.html import escape
from django.utils.safestring import mark_safe
from latex2mathml.converter import convert as latex_vers_mathml

# $$ bloc $$ ou $ en ligne $ (sans espace juste après le premier $ ni juste avant le dernier,
# pour ne pas prendre « 5 $ et 10 $ » pour une formule).
FORMULE = re.compile(r"\$\$(.+?)\$\$|\$([^\s$](?:[^$\n]*?[^\s$])?)\$", re.DOTALL)
# Repère sans caractère spécial Markdown, remplacé par la formule avant le nettoyage.
REPERE = re.compile(r"FORMULEMATH(\d+)FIN")

# Attention : latex2mathml recopie tel quel le contenu de \text{...}, balises comprises.
# Tout le HTML final (formules incluses) passe donc par nh3, avec les seules balises MathML utiles.
BALISES_MATHML = {
    "math", "mrow", "mi", "mo", "mn", "ms", "msup", "msub", "msubsup", "mfrac", "msqrt", "mroot", "mtext",
    "mspace", "mover", "munder", "munderover", "mtable", "mtr", "mtd", "mstyle", "mpadded", "mphantom",
    "menclose", "semantics", "annotation",
}
ATTRIBUTS_MATHML = {
    "math": {"display", "xmlns"},
    "mi": {"mathvariant"},
    "mo": {"stretchy", "fence", "separator", "lspace", "rspace", "form"},
    "mstyle": {"displaystyle", "scriptlevel", "mathvariant"},
    "mfrac": {"linethickness"},
    "mover": {"accent"},
    "munder": {"accentunder"},
    "mspace": {"width"},
    "mtable": {"columnalign", "rowspacing", "columnspacing"},
    "mtd": {"columnalign"},
    "menclose": {"notation"},
}
BALISES = nh3.ALLOWED_TAGS | BALISES_MATHML
ATTRIBUTS = {**nh3.ALLOWED_ATTRIBUTES, **ATTRIBUTS_MATHML}


def rendre(texte):
    if not texte:
        return ""
    formules = []

    def mettre_de_cote(correspondance):
        en_bloc = correspondance.group(1) is not None
        formules.append(((correspondance.group(1) if en_bloc else correspondance.group(2)).strip(), en_bloc))
        return f"FORMULEMATH{len(formules) - 1}FIN"

    def remettre(correspondance):
        latex, en_bloc = formules[int(correspondance.group(1))]
        try:
            return latex_vers_mathml(latex, display="block" if en_bloc else "inline")
        except Exception:
            # Une formule mal écrite s'affiche telle quelle au lieu de faire planter la page.
            return f"<code>{escape(latex)}</code>"

    html = markdown.markdown(FORMULE.sub(mettre_de_cote, texte), extensions=["tables", "fenced_code", "sane_lists"])
    return mark_safe(nh3.clean(REPERE.sub(remettre, html), tags=BALISES, attributes=ATTRIBUTS))


def rendre_ligne(texte):
    """Pour un texte court (choix de QCM) : même rendu, sans le paragraphe qui l'entoure."""
    html = str(rendre(texte)).strip()
    if html.startswith("<p>") and html.endswith("</p>") and html.count("<p>") == 1:
        html = html[3:-4]
    return mark_safe(html)
