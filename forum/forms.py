from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Discussion, Reponse

AIDE = _("Formules entre $ … $ comme dans les corrigés. Pas d'images ni de fichiers.")


class DiscussionForm(forms.ModelForm):
    class Meta:
        model = Discussion
        fields = ("titre", "texte")
        labels = {"titre": _("Votre question"), "texte": _("Détails (facultatif)")}
        help_texts = {
            "titre": _("Une phrase : par exemple « Comment calculer l'annuité d'un amortissement dégressif ? »"),
            "texte": AIDE,
        }
        widgets = {"texte": forms.Textarea(attrs={"rows": 8})}


class ReponseForm(forms.ModelForm):
    class Meta:
        model = Reponse
        fields = ("texte",)
        labels = {"texte": _("Votre réponse")}
        help_texts = {"texte": AIDE}
        widgets = {"texte": forms.Textarea(attrs={"rows": 6})}


class SignalementForm(forms.Form):
    motif = forms.CharField(max_length=300, min_length=5, label=_("Pourquoi signalez-vous ce message ?"))
