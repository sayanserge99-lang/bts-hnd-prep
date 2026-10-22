from django import template

from sujets.rendu import rendre

register = template.Library()


@register.filter
def mise_en_forme(texte):
    """Markdown et formules d'un corrigé, en HTML nettoyé : {{ corrige.contenu|mise_en_forme }}."""
    return rendre(texte)
