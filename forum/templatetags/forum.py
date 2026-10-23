from django import template

from sujets.rendu import rendre_message

register = template.Library()


@register.filter
def message(texte):
    """Markdown et formules, sans images, liens en nofollow (texte écrit par un inscrit)."""
    return rendre_message(texte)
