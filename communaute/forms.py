from django import forms
from django.utils.translation import gettext_lazy as _

from sujets.models import Sujet

from .models import DemandeRetrait


class DemandeRetraitForm(forms.ModelForm):
    """CDC 10.1 : tout ayant droit peut demander un retrait, sans compte."""

    sujet = forms.ModelChoiceField(queryset=Sujet.objects.publies(), widget=forms.HiddenInput)

    class Meta:
        model = DemandeRetrait
        fields = ("sujet", "demandeur_nom", "demandeur_email", "motif", "certifie_titulaire")
        labels = {"motif": _("Motif de la demande")}
        help_texts = {"motif": _("Précisez vos droits sur ce document (auteur, éditeur, établissement…).")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Le contenu est masqué dès réception : la certification est obligatoire.
        self.fields["certifie_titulaire"].required = True
