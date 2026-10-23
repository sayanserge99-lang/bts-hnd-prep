from django import template

register = template.Library()


@register.filter
def fcfa(montant):
    """5000 → « 5 000 FCFA », espace fine insécable : un prix n'est jamais coupé en bout de ligne."""
    return f"{int(montant):,}".replace(",", " ") + " FCFA"
