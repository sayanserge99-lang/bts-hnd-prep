from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm, UserCreationForm
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from catalogue.models import Session, Specialite
from partenaires.models import Etablissement

from .models import Consentement, ProfilEtude, Utilisateur


class UtilisateurCreationForm(UserCreationForm):
    class Meta:
        model = Utilisateur
        fields = ("email",)


class UtilisateurChangeForm(UserChangeForm):
    class Meta:
        model = Utilisateur
        fields = "__all__"


def champ_specialite():
    return forms.ModelChoiceField(
        queryset=Specialite.objects.select_related("examen").order_by("examen__code", "ordre", "nom"),
        label=_("Spécialité préparée"),
    )


def champ_etablissement():
    # Facultatif (CDC 10.2 : collecte minimale) ; sert aux statistiques et, plus tard, à l'espace établissement.
    return forms.ModelChoiceField(
        queryset=Etablissement.objects.all(),
        required=False,
        label=_("Mon établissement"),
        empty_label=_("Autre / non listé"),
    )


def regrouper_par_examen(champ):
    """Affiche les spécialités par examen (BTS, HND) ; l'examen visé se déduit de la spécialité.

    Appelé à chaque création du formulaire : la liste reste à jour et rien n'est lu au démarrage.
    """
    groupes = {}
    for specialite in champ.queryset:
        groupes.setdefault(specialite.examen.code, []).append((specialite.pk, specialite.nom))
    champ.choices = [("", "---------"), *groupes.items()]


class InscriptionForm(UserCreationForm):
    specialite = champ_specialite()
    etablissement = champ_etablissement()
    # CDC 10.2 : case non précochée, consentement enregistré avec sa version.
    accepte_conditions = forms.BooleanField(
        label=_("J'accepte les conditions générales et la politique de confidentialité."),
        required=True,
    )

    class Meta:
        model = Utilisateur
        fields = ("first_name", "last_name", "email", "langue")
        labels = {"first_name": _("Prénom"), "last_name": _("Nom")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for champ in ("first_name", "last_name"):
            self.fields[champ].required = True
        regrouper_par_examen(self.fields["specialite"])

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if Utilisateur.objects.filter(email__iexact=email).exists():
            raise ValidationError(_("Un compte existe déjà avec cette adresse e-mail."))
        return email

    @transaction.atomic
    def save(self, commit=True):
        utilisateur = super().save(commit=True)
        preparer_etudiant(utilisateur, self.cleaned_data["specialite"], self.cleaned_data["etablissement"])
        return utilisateur


def preparer_etudiant(utilisateur, specialite, etablissement=None):
    """Rôle Étudiant, profil d'étude et consentements (CDC 10.2), quelle que soit la façon de s'inscrire."""
    utilisateur.groups.add(Group.objects.get(name="Étudiant"))
    ProfilEtude.objects.create(
        utilisateur=utilisateur, examen=specialite.examen, specialite=specialite, etablissement=etablissement
    )
    for objet in (Consentement.Objet.CGU, Consentement.Objet.CONFIDENTIALITE):
        Consentement.objects.create(utilisateur=utilisateur, objet=objet, version=settings.VERSION_POLITIQUES)


class FinInscriptionGoogleForm(forms.Form):
    """Première connexion avec Google : ce que Google ne donne pas, et le consentement (jamais présumé)."""

    first_name = forms.CharField(label=_("Prénom"), max_length=150)
    last_name = forms.CharField(label=_("Nom"), max_length=150)
    langue = forms.ChoiceField(label=_("Langue"), choices=Utilisateur._meta.get_field("langue").choices)
    specialite = champ_specialite()
    etablissement = champ_etablissement()
    accepte_conditions = forms.BooleanField(
        label=_("J'accepte les conditions générales et la politique de confidentialité."), required=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        regrouper_par_examen(self.fields["specialite"])

    @transaction.atomic
    def creer(self, email):
        donnees = self.cleaned_data
        utilisateur = Utilisateur(
            email=email, first_name=donnees["first_name"], last_name=donnees["last_name"], langue=donnees["langue"]
        )
        # Pas de mot de passe : ce compte se connecte avec Google.
        utilisateur.set_unusable_password()
        utilisateur.save()
        preparer_etudiant(utilisateur, donnees["specialite"], donnees["etablissement"])
        return utilisateur


class ConnexionForm(AuthenticationForm):
    username = forms.EmailField(
        label=_("Adresse e-mail"), widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"})
    )

    error_messages = {
        **AuthenticationForm.error_messages,
        "bloque": _("Trop de tentatives. Réessayez dans 15 minutes ou réinitialisez votre mot de passe."),
    }

    def clean(self):
        email = (self.cleaned_data.get("username") or "").lower()
        self.cleaned_data["username"] = email
        cle = f"connexion-echecs:{email}"
        if cache.get(cle, 0) >= settings.CONNEXION_ESSAIS_MAX:
            raise ValidationError(self.error_messages["bloque"], code="bloque")
        try:
            donnees = super().clean()
        except ValidationError:
            cache.set(cle, cache.get(cle, 0) + 1, timeout=settings.CONNEXION_BLOCAGE_SECONDES)
            raise
        cache.delete(cle)
        return donnees


class ProfilForm(forms.ModelForm):
    """Identité et profil d'étude, sur un même formulaire."""

    specialite = champ_specialite()
    etablissement = champ_etablissement()
    session_prevue = forms.ModelChoiceField(
        queryset=Session.objects.none(), required=False, label=_("Session prévue")
    )

    class Meta:
        model = Utilisateur
        fields = ("first_name", "last_name", "langue")
        labels = {"first_name": _("Prénom"), "last_name": _("Nom")}

    def __init__(self, *args, profil, **kwargs):
        self.profil = profil
        super().__init__(*args, **kwargs)
        regrouper_par_examen(self.fields["specialite"])
        self.fields["specialite"].initial = profil.specialite_id
        self.fields["etablissement"].initial = profil.etablissement_id
        self.fields["session_prevue"].initial = profil.session_prevue_id
        self.fields["session_prevue"].queryset = (
            Session.objects.filter(date_fin_officielle__gte=timezone.localdate()).select_related("examen").order_by("annee")
        )

    def clean(self):
        donnees = super().clean()
        specialite, session = donnees.get("specialite"), donnees.get("session_prevue")
        if specialite and session and session.examen_id != specialite.examen_id:
            self.add_error("session_prevue", _("Cette session n'appartient pas à l'examen de votre spécialité."))
        return donnees

    @transaction.atomic
    def save(self, commit=True):
        utilisateur = super().save()
        specialite = self.cleaned_data["specialite"]
        self.profil.examen = specialite.examen
        self.profil.specialite = specialite
        self.profil.session_prevue = self.cleaned_data["session_prevue"]
        self.profil.etablissement = self.cleaned_data["etablissement"]
        self.profil.save()
        return utilisateur


class SuppressionForm(forms.Form):
    mot_de_passe = forms.CharField(label=_("Mot de passe"), widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))

    def __init__(self, *args, utilisateur, **kwargs):
        self.utilisateur = utilisateur
        super().__init__(*args, **kwargs)
        if not utilisateur.has_usable_password():
            # Compte créé avec Google, sans mot de passe : on confirme en retapant l'adresse e-mail.
            self.fields["mot_de_passe"] = forms.CharField(
                label=_("Pour confirmer, tapez votre adresse e-mail"),
                widget=forms.EmailInput(attrs={"autocomplete": "off"}),
            )

    def clean_mot_de_passe(self):
        valeur = self.cleaned_data["mot_de_passe"]
        if not self.utilisateur.has_usable_password():
            if valeur.strip().lower() != self.utilisateur.email.lower():
                raise ValidationError(_("Ce n'est pas l'adresse e-mail de ce compte."))
            return valeur
        if not self.utilisateur.check_password(valeur):
            raise ValidationError(_("Mot de passe incorrect."))
        return valeur
