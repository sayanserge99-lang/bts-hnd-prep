"""Pages de la double authentification de l'équipe : mise en place (QR code) et saisie du code."""

from functools import wraps
from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from config.securite import DOUBLE_AUTH_ESSAIS

from . import double_auth
from .models import DoubleAuthentification


class CodeForm(forms.Form):
    code = forms.CharField(
        label=gettext_lazy("Code à 6 chiffres"), max_length=20,
        help_text=gettext_lazy("Affiché par l'application d'authentification de votre téléphone."),
        widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "one-time-code", "autofocus": True}),
    )


def equipe_requise(vue):
    @login_required
    @wraps(vue)
    def enveloppe(request, *args, **kwargs):
        if not request.user.is_staff:
            raise Http404
        return vue(request, *args, **kwargs)

    return enveloppe


def suite(request):
    """Où aller une fois vérifié : la page demandée (sur ce site seulement), sinon l'administration."""
    cible = request.POST.get("next") or request.GET.get("next") or ""
    if url_has_allowed_host_and_scheme(cible, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return cible
    return reverse("admin:index")


def vers(nom, request):
    return f"{reverse(nom)}?{urlencode({'next': suite(request)})}"


@equipe_requise
def configurer(request):
    """Première fois : scanner le QR code, confirmer avec un code, noter les codes de secours."""
    appareil = DoubleAuthentification.objects.filter(utilisateur=request.user).first()
    if appareil and appareil.active:
        return redirect(vers("accounts:double_auth", request))
    if appareil is None:
        # Gardé en attente : recharger la page ne change pas le QR code déjà scanné.
        appareil = DoubleAuthentification.objects.create(utilisateur=request.user, secret=double_auth.nouveau_secret())
    form = CodeForm(request.POST or None)
    if form.is_valid():
        if double_auth.verifier_code(appareil, form.cleaned_data["code"]):
            double_auth.activer(appareil)
            codes = double_auth.nouveaux_codes_secours(appareil)
            double_auth.marquer_verifiee(request)
            return render(request, "accounts/double_auth_codes.html", {"codes": codes, "suite": suite(request)})
        form.add_error("code", _("Code incorrect. Vérifiez l'heure de votre téléphone, puis réessayez."))
    return render(request, "accounts/double_auth_configurer.html", {
        "form": form,
        # SVG produit ici : aucune donnée saisie par un utilisateur dans le balisage.
        "qr": mark_safe(double_auth.qr_code_svg(double_auth.adresse_application(appareil))),
        "secret": " ".join(appareil.secret[i:i + 4] for i in range(0, len(appareil.secret), 4)),
        "suite": suite(request),
    })


@equipe_requise
def verifier(request):
    """À chaque session : le code du téléphone, ou un code de secours."""
    appareil = DoubleAuthentification.objects.filter(utilisateur=request.user, active_le__isnull=False).first()
    if appareil is None:
        return redirect(vers("accounts:double_auth_configurer", request))
    form = CodeForm(request.POST or None)
    if form.is_valid():
        saisie = form.cleaned_data["code"]
        if DOUBLE_AUTH_ESSAIS.atteinte(request.user.pk):
            form.add_error("code", _("Trop d'essais. Réessayez dans 15 minutes."))
        elif double_auth.verifier_code(appareil, saisie) or double_auth.utiliser_code_secours(appareil, saisie):
            DOUBLE_AUTH_ESSAIS.effacer(request.user.pk)
            double_auth.marquer_verifiee(request)
            if len(saisie.strip()) > double_auth.CHIFFRES:  # c'était un code de secours
                messages.warning(request, _(
                    "Code de secours utilisé : il vous en reste %(n)s. Téléphone perdu ? Demandez à un "
                    "administrateur de réinitialiser votre double authentification."
                ) % {"n": len(appareil.codes_secours)})
            return redirect(suite(request))
        else:
            DOUBLE_AUTH_ESSAIS.compter(request.user.pk)
            form.add_error("code", _("Code incorrect."))
    return render(request, "accounts/double_auth_verifier.html", {"form": form, "suite": suite(request)})
