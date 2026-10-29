"""« Vouliez-vous dire … ? » : quand une recherche ne trouve rien, chaque mot inconnu est remplacé par le mot le plus
proche du vocabulaire des contenus visibles (sujets publiés, forum). Sans extension PostgreSQL ni table : le
vocabulaire est relu depuis la base et gardé en cache. L'appelant ne montre la suggestion que si elle trouve
vraiment des résultats visibles (rien ne se devine d'un sujet non publié).
"""

import difflib
import re
import unicodedata
from collections import Counter

from django.core.cache import cache

MOT = re.compile(r"[^\W_]+")  # comme requete_plein_texte
# En dessous (« TVA », « bilan » mal tapé en « bila »…), trop de mots voisins pour deviner sans se tromper.
LONGUEUR_MIN = 4
PROXIMITE = 0.75
# Les nouveaux sujets ne se publient pas toutes les minutes ; le forum, si : son vocabulaire vit moins longtemps.
DUREE_SUJETS = 60 * 60
DUREE_FORUM = 10 * 60


def cle(mot):
    """Minuscules sans accents : « Dégressif » et « degressif » sont le même mot."""
    decompose = unicodedata.normalize("NFKD", mot.casefold())
    return "".join(c for c in decompose if not unicodedata.combining(c))


def construire(textes):
    """{clé: forme la plus fréquente} des mots d'au moins LONGUEUR_MIN lettres."""
    formes = Counter(mot.lower() for texte in textes for mot in MOT.findall(texte or "")
                     if len(mot) >= LONGUEUR_MIN and mot.isalpha())
    vocabulaire = {}
    for forme, _ in formes.most_common():
        vocabulaire.setdefault(cle(forme), forme)
    return vocabulaire


def vocabulaire(nom, textes, duree):
    """Vocabulaire mis en cache sous `nom` ; `textes()` n'est appelée que s'il n'y est pas."""
    resultat = cache.get(nom)
    if resultat is None:
        resultat = construire(textes())
        cache.set(nom, resultat, duree)
    return resultat


def suggestion(texte, vocab):
    """Le texte avec ses mots inconnus corrigés, ou None si aucun ne change.

    Un mot qui commence un mot connu n'est pas corrigé : la recherche le prend déjà comme début de mot.
    """
    cles = list(vocab)
    mots, corrige = [], False
    for mot in MOT.findall(texte):
        k = cle(mot)
        if len(k) < LONGUEUR_MIN or not mot.isalpha() or any(c.startswith(k) for c in cles):
            mots.append(mot)
            continue
        voisins = [c for c in cles if abs(len(c) - len(k)) <= 2]
        proche = difflib.get_close_matches(k, voisins, n=1, cutoff=PROXIMITE)
        if proche:
            mots.append(vocab[proche[0]])
            corrige = True
        else:
            mots.append(mot)
    return " ".join(mots) if corrige else None
