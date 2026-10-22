import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django.views.i18n import set_language

from sujets.models import Sujet

from .forms import ConnexionForm, InscriptionForm, ProfilForm, SuppressionForm


def avec_langue(reponse, utilisateur):
    """Applique la langue choisie par l'utilisateur à l'interface."""
    reponse.set_cookie(settings.LANGUAGE_COOKIE_NAME, utilisateur.langue)
    return reponse


def inscription(request):
    if request.user.is_authenticated:
        return redirect("accounts:profil")
    form = InscriptionForm(request.POST or None, initial={"langue": request.LANGUAGE_CODE})
    if form.is_valid():
        utilisateur = form.save()
        login(request, utilisateur, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, _("Bienvenue ! Votre compte est créé."))
        return avec_langue(redirect("accounts:profil"), utilisateur)
    return render(request, "accounts/inscription.html", {"form": form})


class Connexion(auth_views.LoginView):
    form_class = ConnexionForm
    template_name = "accounts/connexion.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        return avec_langue(super().form_valid(form), form.get_user())


@login_required
def profil(request):
    profil_etude = getattr(request.user, "profil", None)
    recents = Sujet.objects.none()
    if profil_etude:
        recents = (
            Sujet.objects.publies()
            .filter(specialites=profil_etude.specialite)
            .select_related("session", "matiere")
            .order_by("-date_publication")[:5]
        )
    favoris = request.user.favoris.filter(sujet__statut=Sujet.Statut.PUBLIE).select_related("sujet__session", "sujet__matiere")
    return render(request, "accounts/profil.html", {"profil": profil_etude, "recents": recents, "favoris": favoris})


@login_required
def modifier_profil(request):
    profil_etude = getattr(request.user, "profil", None)
    if profil_etude is None:
        messages.info(request, _("Ce compte n'a pas de profil d'étude."))
        return redirect("accounts:profil")
    form = ProfilForm(request.POST or None, instance=request.user, profil=profil_etude)
    if form.is_valid():
        utilisateur = form.save()
        messages.success(request, _("Profil enregistré."))
        return avec_langue(redirect("accounts:profil"), utilisateur)
    return render(request, "accounts/modifier_profil.html", {"form": form})


@login_required
def exporter(request):
    """CDC 10.2 : l'utilisateur récupère toutes ses données."""
    utilisateur = request.user
    profil_etude = getattr(utilisateur, "profil", None)
    donnees = {
        "compte": {
            "email": utilisateur.email,
            "prenom": utilisateur.first_name,
            "nom": utilisateur.last_name,
            "telephone": utilisateur.telephone,
            "langue": utilisateur.langue,
            "date_inscription": utilisateur.date_joined.isoformat(),
        },
        "profil_etude": profil_etude and {
            "examen": profil_etude.examen.code,
            "specialite": str(profil_etude.specialite),
            "etablissement": str(profil_etude.etablissement or ""),
            "session_prevue": str(profil_etude.session_prevue or ""),
        },
        "consentements": [
            {"objet": c.objet, "version": c.version, "date": c.date.isoformat(),
             "revocation": c.date_revocation and c.date_revocation.isoformat()}
            for c in utilisateur.consentements.all()
        ],
        "favoris": [{"sujet": str(f.sujet), "date_ajout": f.date_ajout.isoformat()} for f in utilisateur.favoris.select_related("sujet__session")],
    }
    reponse = HttpResponse(json.dumps(donnees, ensure_ascii=False, indent=2), content_type="application/json; charset=utf-8")
    reponse["Content-Disposition"] = f'attachment; filename="mes-donnees-{timezone.localdate():%Y-%m-%d}.json"'
    return reponse


@login_required
def supprimer(request):
    """CDC 10.2 : suppression du compte depuis le profil, après confirmation du mot de passe."""
    form = SuppressionForm(request.POST or None, utilisateur=request.user)
    if form.is_valid():
        utilisateur = request.user
        try:
            utilisateur.delete()
        except ProtectedError:
            # Les paiements sont conservés (preuve d'achat) : on ne peut pas supprimer ce compte seul.
            messages.error(request, _("Ce compte est lié à des paiements : contactez-nous pour le supprimer."))
            return redirect("accounts:profil")
        logout(request)
        messages.success(request, _("Votre compte et vos données ont été supprimés."))
        return redirect("accueil")
    return render(request, "accounts/supprimer.html", {"form": form})


@require_POST
def changer_langue(request):
    """Bascule FR/EN de Django ; pour un utilisateur connecté, la langue choisie est aussi enregistrée."""
    reponse = set_language(request)
    langue = request.POST.get("language")
    if request.user.is_authenticated and langue in dict(settings.LANGUAGES):
        request.user.langue = langue
        request.user.save(update_fields=["langue"])
    return reponse


@require_POST
def deconnexion(request):
    logout(request)
    return redirect(settings.LOGOUT_REDIRECT_URL)


class MotDePasseOublie(auth_views.PasswordResetView):
    template_name = "accounts/mot_de_passe_oublie.html"
    email_template_name = "accounts/email_reinitialisation.txt"
    subject_template_name = "accounts/email_reinitialisation_sujet.txt"
    success_url = reverse_lazy("accounts:mot_de_passe_envoye")


class NouveauMotDePasse(auth_views.PasswordResetConfirmView):
    template_name = "accounts/nouveau_mot_de_passe.html"
    success_url = reverse_lazy("accounts:connexion")

    def form_valid(self, form):
        messages.success(self.request, _("Mot de passe modifié. Vous pouvez vous connecter."))
        return super().form_valid(form)
