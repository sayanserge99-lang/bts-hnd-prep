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
# Code (bloc entre ``` ou ~~~, ou `en ligne`) : recopié tel quel, sans formule ni espace fine, car un script shell
# ou PHP contient des $ (« echo $HOME ») et se recopie caractère pour caractère.
CODE = re.compile(r"^(?P<cloture>`{3,}|~{3,})[^\n]*\n.*?^(?P=cloture)[ \t]*$|(?P<accents>`+)(?!`).+?(?<!`)(?P=accents)(?!`)",
                  re.DOTALL | re.MULTILINE)
# Repère sans caractère spécial Markdown, remplacé par la formule avant le nettoyage.
REPERE = re.compile(r"FORMULEMATH(\d+)FIN")
# Espace des milliers (« 12 000 000 ») : remplacée par une espace fine insécable, pour qu'un montant
# ne soit jamais coupé en bout de ligne sur un téléphone.
MILLIERS = re.compile(r"(?<=\d) (?=\d{3}(?!\d))")
ESPACE_FINE_INSECABLE = " "

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


# Messages du forum : pas d'images (pistage, contenus choquants), liens marqués comme venant des utilisateurs.
BALISES_MESSAGE = BALISES - {"img"}


def rendre_message(texte):
    """Rendu d'un message de forum : comme un corrigé (formules comprises), plus restrictif."""
    return rendre(texte, balises=BALISES_MESSAGE, rel_liens="nofollow ugc noopener noreferrer")


def rendre(texte, balises=BALISES, rel_liens="noopener noreferrer"):
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

    def hors_code(morceau):
        # Les formules sont mises de côté d'abord : LaTeX gère ses propres espaces.
        return MILLIERS.sub(ESPACE_FINE_INSECABLE, FORMULE.sub(mettre_de_cote, morceau))

    morceaux, debut = [], 0
    for code in CODE.finditer(texte):
        morceaux += [hors_code(texte[debut:code.start()]), code.group()]
        debut = code.end()
    texte = "".join(morceaux + [hors_code(texte[debut:])])
    html = markdown.markdown(texte, extensions=["tables", "fenced_code", "sane_lists"])
    return mark_safe(nh3.clean(REPERE.sub(remettre, html), tags=balises, attributes=ATTRIBUTS, link_rel=rel_liens))


def rendre_ligne(texte):
    """Pour un texte court (choix de QCM) : même rendu, sans le paragraphe qui l'entoure."""
    html = str(rendre(texte)).strip()
    if html.startswith("<p>") and html.endswith("</p>") and html.count("<p>") == 1:
        html = html[3:-4]
    return mark_safe(html)
