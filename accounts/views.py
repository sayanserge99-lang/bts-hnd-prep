import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django.views.i18n import set_language

from entrainement import progression
from entrainement.models import Tentative
from sujets.models import Sujet

from . import google
from .forms import ConnexionForm, FinInscriptionGoogleForm, InscriptionForm, ProfilForm, SuppressionForm
from .models import Consentement, Utilisateur


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
    session = progression.prochaine_session(request.user)
    return render(
        request,
        "accounts/profil.html",
        {
            "profil": profil_etude,
            "recents": recents,
            "favoris": favoris,
            # CDC 3.1 : le tableau de bord montre les derniers résultats.
            "resultats": Tentative.objects.filter(utilisateur=request.user, note__isnull=False)
            .select_related("quiz", "examen_blanc")
            .order_by("-fin")[:3],
            "session": session,
            "jours": progression.jours_restants(session),
            "partage": Consentement.partage_actif(request.user),
        },
    )


@login_required
@require_POST
def basculer_partage(request):
    """CDC 10.6 : partage des résultats avec l'établissement, désactivé par défaut et révocable à tout moment."""
    if Consentement.partage_actif(request.user):
        Consentement.objects.filter(
            utilisateur=request.user, objet=Consentement.Objet.PARTAGE_ETABLISSEMENT, date_revocation__isnull=True
        ).update(date_revocation=timezone.now())
        messages.success(request, _("Votre établissement ne voit plus vos résultats."))
    else:
        Consentement.objects.create(
            utilisateur=request.user, objet=Consentement.Objet.PARTAGE_ETABLISSEMENT, version=settings.VERSION_POLITIQUES
        )
        messages.success(request, _("Votre établissement peut maintenant voir vos résultats."))
    return redirect("accounts:profil")


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


def suite_sure(request, adresse):
    """N'accepte qu'une adresse de ce site après la connexion (pas de redirection vers un site tiers)."""
    if adresse and url_has_allowed_host_and_scheme(adresse, {request.get_host()}, require_https=request.is_secure()):
        return adresse
    return reverse("accounts:profil")


def adresse_retour_google(request):
    return request.build_absolute_uri(reverse("accounts:google_retour"))


def google_debut(request):
    if not google.est_active():
        raise Http404
    return redirect(google.preparer(request.session, adresse_retour_google(request), request.GET.get("next", "")))


def google_retour(request):
    if not google.est_active():
        raise Http404
    try:
        email, prenom, nom, suite = google.terminer(request.session, request.GET, adresse_retour_google(request))
    except google.RefusGoogle:
        messages.error(request, _("La connexion avec Google n'a pas abouti. Réessayez, ou connectez-vous avec votre e-mail."))
        return redirect("accounts:connexion")

    utilisateur = Utilisateur.objects.filter(email__iexact=email).first()
    if utilisateur is not None:
        if not utilisateur.is_active:
            messages.error(request, _("Ce compte est désactivé."))
            return redirect("accounts:connexion")
        # L'adresse est vérifiée par Google : c'est bien son titulaire.
        login(request, utilisateur, backend="django.contrib.auth.backends.ModelBackend")
        return avec_langue(redirect(suite_sure(request, suite)), utilisateur)

    # Première connexion : on garde l'identité vérifiée le temps de compléter l'inscription.
    request.session[google.CLE_SESSION + "_inscription"] = {"email": email, "prenom": prenom, "nom": nom}
    return redirect("accounts:google_finir")


def google_finir(request):
    identite = request.session.get(google.CLE_SESSION + "_inscription")
    if not google.est_active() or not identite:
        return redirect("accounts:inscription")
    if Utilisateur.objects.filter(email__iexact=identite["email"]).exists():
        del request.session[google.CLE_SESSION + "_inscription"]
        return redirect("accounts:connexion")
    form = FinInscriptionGoogleForm(
        request.POST or None,
        initial={"first_name": identite["prenom"], "last_name": identite["nom"], "langue": request.LANGUAGE_CODE},
    )
    if form.is_valid():
        utilisateur = form.creer(identite["email"])
        del request.session[google.CLE_SESSION + "_inscription"]
        login(request, utilisateur, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, _("Bienvenue ! Votre compte est créé."))
        return avec_langue(redirect("accounts:profil"), utilisateur)
    return render(request, "accounts/google_finir.html", {"form": form, "email": identite["email"]})


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
