from django import template

from sujets.filigrane import lien_temporaire
from sujets.rendu import rendre, rendre_ligne

register = template.Library()


@register.filter
def mise_en_forme(texte):
    """Markdown et formules d'un corrigé, en HTML nettoyé : {{ corrige.contenu|mise_en_forme }}."""
    return rendre(texte)


@register.filter
def mise_en_forme_ligne(texte):
    """Même rendu pour un texte court, sans paragraphe : {{ choix.texte|mise_en_forme_ligne }}."""
    return rendre_ligne(texte)


@register.simple_tag(takes_context=True)
def lien_pdf_corrige(context, corrige):
    """Adresse temporaire du PDF, propre au lecteur : {% lien_pdf_corrige corrige %}."""
    return lien_temporaire(corrige, context["request"].user)
