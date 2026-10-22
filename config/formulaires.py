from django.forms.renderers import TemplatesSetting


class Rendu(TemplatesSetting):
    """Un seul gabarit pour tous les champs : libellé, champ, aide et erreurs, au style du site."""

    field_template_name = "forms/champ.html"
