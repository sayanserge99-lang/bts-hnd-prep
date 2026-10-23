from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from . import codes


class ActivationForm(forms.Form):
    code = forms.CharField(
        label=gettext_lazy("Code d'accès"), max_length=30,
        help_text=gettext_lazy("Remis par votre établissement, par exemple ABCD-EFGH-JKLM."),
        widget=forms.TextInput(attrs={"autocomplete": "off", "autocapitalize": "characters", "spellcheck": "false"}),
    )


@login_required
def activer_code(request):
    """CDC 3.9 : l'étudiant active le code prépayé reçu de son établissement."""
    form = ActivationForm(request.POST or None)
    if form.is_valid():
        try:
            abonnement = codes.activer(request.user, form.cleaned_data["code"])
        except codes.CodeRefuse as refus:
            form.add_error("code", str(refus))
        else:
            messages.success(
                request,
                _("Code activé : %(offre)s, jusqu'au %(fin)s.") % {"offre": abonnement.offre.nom, "fin": abonnement.fin.strftime("%d/%m/%Y")},
            )
            return redirect("accounts:profil")
    return render(request, "paiements/activer_code.html", {"form": form})
