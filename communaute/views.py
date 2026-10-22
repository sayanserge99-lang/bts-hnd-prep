from django.conf import settings
from django.core.cache import cache
from django.core.mail import mail_admins, send_mail
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils.translation import gettext as _

from sujets.models import Sujet

from .forms import DemandeRetraitForm


def adresse_ip(request):
    # Derrière Nginx, REMOTE_ADDR est celle de Nginx : l'adresse du visiteur est dans X-Real-IP,
    # que Nginx écrase toujours (deploy/nginx.conf). Sans proxy, cet en-tête serait falsifiable.
    if settings.DERRIERE_PROXY:
        return request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR", "")
    return request.META.get("REMOTE_ADDR", "")


def demande_retrait(request):
    identifiant = request.POST.get("sujet") or request.GET.get("sujet") or ""
    sujet = Sujet.objects.publies().filter(pk=identifiant).first() if identifiant.isdigit() else None
    if sujet is None:
        # Sans sujet précis, la page explique comment faire la demande depuis la fiche du sujet.
        return render(request, "communaute/demande_retrait.html", {"form": None})

    form = DemandeRetraitForm(request.POST or None, initial={"sujet": sujet})
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
            mail_admins(f"Demande de retrait : {demande.sujet}", demande.motif, fail_silently=True)
            return redirect("demande_retrait_recue")
    return render(request, "communaute/demande_retrait.html", {"form": form, "sujet": sujet})
