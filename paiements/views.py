import json

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from catalogue.models import Session
from sujets.views import est_requete_htmx

from . import codes, service
from .acces import a_un_abonnement_actif
from .fournisseurs import fournisseur_actif
from .fournisseurs.base import NotificationInvalide, signer
from .models import Offre, Paiement
from .offres import offres_affichees


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


def offres(request):
    """Page « Offres » : comparatif Gratuit / Premium et prix (CDC 7, 3.8)."""
    en_cours = None
    if request.user.is_authenticated and a_un_abonnement_actif(request.user):
        en_cours = request.user.abonnements.filter(fin__gte=timezone.localdate()).order_by("-fin").first()
    return render(
        request,
        "paiements/offres.html",
        {"offres": offres_affichees(request.user), "en_cours": en_cours, "quiz_gratuits": settings.QUIZ_GRATUITS_PAR_JOUR},
    )


class CommandeForm(forms.Form):
    operateur = forms.ChoiceField(choices=Paiement.Operateur.choices, widget=forms.RadioSelect, label=gettext_lazy("Payer avec"))
    telephone = forms.CharField(
        label=gettext_lazy("Numéro de téléphone"), max_length=20,
        help_text=gettext_lazy("Vous recevrez une demande sur ce téléphone : validez-la avec votre code secret."),
        widget=forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel", "placeholder": "6XX XX XX XX"}),
    )
    accepte = forms.BooleanField(label=gettext_lazy("J'ai lu et j'accepte les conditions générales de vente."))

    def clean_telephone(self):
        numero = service.normaliser_telephone(self.cleaned_data["telephone"])
        if numero is None:
            raise forms.ValidationError(_("Numéro de mobile camerounais attendu (9 chiffres, commençant par 6)."))
        return numero


def paiement_ouvert(vue):
    def enveloppe(request, *args, **kwargs):
        if not settings.PAIEMENT_ACTIF:
            raise Http404
        return vue(request, *args, **kwargs)

    enveloppe.__name__ = vue.__name__
    return enveloppe


@paiement_ouvert
@login_required
def commander(request, pk):
    """Récapitulatif (prix TTC, dates) puis paiement Mobile Money (CDC 3.8, 10.7)."""
    offre = get_object_or_404(Offre, pk=pk, active=True)
    if offre.type == Offre.Type.SESSION and not hasattr(request.user, "profil"):
        messages.error(request, _("Complétez d'abord votre profil (examen et spécialité)."))
        return redirect("accounts:modifier_profil")
    try:
        debut, fin = service.periode(request.user, offre)
    except ValidationError as erreur:
        # Pass session sans session à venir : rien à vendre, on le dit avant tout paiement.
        messages.error(request, erreur.messages[0])
        return redirect("offres")
    form = CommandeForm(request.POST or None)
    if form.is_valid():
        paiement, adresse = service.commander(
            request.user, offre, form.cleaned_data["operateur"], form.cleaned_data["telephone"], request
        )
        # Page de l'agrégateur, ou attente de la confirmation sur le téléphone.
        if adresse:
            return redirect(adresse)
        return redirect("paiements:suivi", reference=paiement.reference)
    profil = getattr(request.user, "profil", None)
    session = Session.objects.prochaine(profil.examen, debut) if offre.type == Offre.Type.SESSION and profil else None
    return render(request, "paiements/commander.html", {
        "offre": offre, "debut": debut, "fin": fin, "form": form, "session": session, "agregateur": fournisseur_actif().nom,
    })


def paiement_de(request, reference):
    # Un paiement n'est visible que par celui qui l'a fait.
    return get_object_or_404(Paiement.objects.select_related("offre"), reference=reference, utilisateur=request.user)


@login_required
def suivi(request, reference):
    """Attente de la confirmation : la page se recharge seule (HTMX) jusqu'au résultat."""
    paiement = service.rafraichir(paiement_de(request, reference))
    gabarit = "paiements/_etat.html" if est_requete_htmx(request) else "paiements/suivi.html"
    return render(request, gabarit, {"paiement": paiement})


@login_required
def recu(request, reference):
    """CDC 10.7 : reçu consultable dans le profil, imprimable."""
    paiement = paiement_de(request, reference)
    if paiement.statut != Paiement.Statut.REUSSI:
        raise Http404
    return render(request, "paiements/recu.html", {"paiement": paiement, "abonnement": paiement.abonnement, "exploitant": settings.EXPLOITANT})


@csrf_exempt  # appelé par l'agrégateur, pas par un navigateur : c'est la signature qui fait foi
@require_POST
def notification(request):
    try:
        resultat = fournisseur_actif().lire_notification(request)
    except NotificationInvalide:
        return HttpResponseBadRequest("notification invalide")
    if service.appliquer(resultat) is None:
        return HttpResponse("reference inconnue", status=404)
    return HttpResponse("ok")


@paiement_ouvert
@login_required
def simulateur(request, reference):
    """Développement seulement : tient le rôle du téléphone de l'étudiant et envoie une notification signée,
    exactement comme le ferait l'agrégateur."""
    if not settings.DEBUG or fournisseur_actif().code != "simule":
        raise Http404
    paiement = paiement_de(request, reference)
    if request.method == "POST":
        reussi = request.POST.get("choix") == "valider"
        corps = json.dumps({
            "reference": paiement.reference, "statut": "reussi" if reussi else "echoue",
            "montant": int(request.POST.get("montant") or paiement.montant), "motif": "" if reussi else "Refusé sur le téléphone (simulation)",
        }).encode()
        service.appliquer(fournisseur_actif().decoder(corps, signer(corps)))
        return redirect("paiements:suivi", reference=paiement.reference)
    return render(request, "paiements/simulateur.html", {"paiement": paiement})
