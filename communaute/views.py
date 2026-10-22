from django.conf import settings
from django.core.cache import cache
from django.core.mail import mail_admins, send_mail
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils.translation import gettext as _

from sujets.models import Corrige, Sujet

from .forms import DemandeRetraitForm


def adresse_ip(request):
    # Derrière Nginx, REMOTE_ADDR est celle de Nginx : l'adresse du visiteur est dans X-Real-IP,
    # que Nginx écrase toujours (deploy/nginx.conf). Sans proxy, cet en-tête serait falsifiable.
    if settings.DERRIERE_PROXY:
        return request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR", "")
    return request.META.get("REMOTE_ADDR", "")


def document_vise(request):
    """Le sujet ou le corrigé visé par ?sujet= ou ?corrige= (uniquement s'il est visible du public)."""
    for champ, documents in (("sujet", Sujet.objects.publies()), ("corrige", Corrige.objects.visibles())):
        identifiant = request.POST.get(champ) or request.GET.get(champ) or ""
        if identifiant.isdigit():
            document = documents.filter(pk=identifiant).first()
            if document:
                return champ, document
    return None, None


def demande_retrait(request):
    champ, document = document_vise(request)
    if document is None:
        # Sans document précis, la page explique comment faire la demande depuis la fiche du sujet.
        return render(request, "communaute/demande_retrait.html", {"form": None})

    form = DemandeRetraitForm(request.POST or None, initial={champ: document})
    if form.is_valid():
        # Le masquage est immédiat (CDC 10.1) : on limite les demandes pour éviter qu'un tiers masque tout.
        cle = f"demandes-retrait:{adresse_ip(request)}"
        if cache.get(cle, 0) >= settings.DEMANDES_RETRAIT_PAR_JOUR:
            form.add_error(None, _("Trop de demandes envoyées aujourd'hui. Écrivez-nous depuis la page Contact."))
        else:
            demande = form.save()
            cache.set(cle, cache.get(cle, 0) + 1, timeout=24 * 60 * 60)
            send_mail(
                _("Votre demande de retrait a bien été reçue"),
                render_to_string("communaute/email_accuse_retrait.txt", {"demande": demande}),
                None,
                [demande.demandeur_email],
                fail_silently=True,
            )
            mail_admins(f"Demande de retrait : {document}", demande.motif, fail_silently=True)
            return redirect("demande_retrait_recue")
    return render(request, "communaute/demande_retrait.html", {"form": form, "document": document})
