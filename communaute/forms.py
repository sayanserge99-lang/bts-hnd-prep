from django import forms
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from catalogue.models import Matiere, Session, Specialite
from sujets.models import Corrige, Sujet

from . import contributions
from .models import Contribution, DemandeRetrait, MessageContact


class PlusieursFichiers(forms.ClearableFileInput):
    allow_multiple_selected = True


class ChampPlusieursFichiers(forms.FileField):
    """Un PDF ou plusieurs photos (une par page)."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", PlusieursFichiers(attrs={"accept": "application/pdf,image/jpeg,image/png"}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        if isinstance(data, (list, tuple)):
            return [super(ChampPlusieursFichiers, self).clean(fichier, initial) for fichier in data if fichier]
        return [super().clean(data, initial)] if data else []


class DemandeRetraitForm(forms.ModelForm):
    """CDC 10.1 : tout ayant droit peut demander un retrait, sans compte."""

    sujet = forms.ModelChoiceField(queryset=Sujet.objects.publies(), widget=forms.HiddenInput, required=False)
    corrige = forms.ModelChoiceField(queryset=Corrige.objects.visibles(), widget=forms.HiddenInput, required=False)

    class Meta:
        model = DemandeRetrait
        fields = ("sujet", "corrige", "demandeur_nom", "demandeur_email", "motif", "certifie_titulaire")
        labels = {"motif": _("Motif de la demande")}
        help_texts = {"motif": _("Précisez vos droits sur ce document (auteur, éditeur, établissement…).")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Le contenu est masqué dès réception : la certification est obligatoire.
        self.fields["certifie_titulaire"].required = True

    def clean(self):
        donnees = super().clean()
        if bool(donnees.get("sujet")) == bool(donnees.get("corrige")):
            raise ValidationError(_("La demande doit viser un seul document."))
        return donnees


class EnvoiMixin:
    """Contrôles communs : document en PDF (photos assemblées), droits certifiés, limite quotidienne."""

    def __init__(self, *args, utilisateur=None, **kwargs):
        self.utilisateur = utilisateur
        super().__init__(*args, **kwargs)
        self.fields["certifie_droits"].required = True
        self.pdf = None

    def clean(self):
        donnees = super().clean()
        if self.utilisateur and contributions.envois_aujourd_hui(self.utilisateur) >= settings.CONTRIBUTIONS_PAR_JOUR:
            raise ValidationError(_("Vous avez déjà beaucoup envoyé aujourd'hui. Merci ! Revenez demain pour la suite."))
        fichiers = donnees.get("fichiers") or []
        if fichiers:
            try:
                self.pdf = contributions.en_pdf(fichiers)
            except ValueError as erreur:
                self.add_error("fichiers", str(erreur))
        return donnees


class EnvoiSujetForm(EnvoiMixin, forms.ModelForm):
    """CDC 3.7 : photo ou PDF + session, spécialité, matière."""

    # Maquette : grande zone « Photographier ou choisir un fichier » ; sur téléphone, image/* propose l'appareil photo.
    fichiers = ChampPlusieursFichiers(
        label=_("Le sujet"), help_text=_("Un PDF, ou une photo par page (JPG ou PNG, 10 au plus), dans l'ordre."),
        widget=PlusieursFichiers(attrs={"accept": "image/*,application/pdf"}),
    )
    envoyer_quand_meme = forms.BooleanField(
        label=_("Je l'envoie quand même (meilleure qualité, pages manquantes dans celui du site…)"), required=False,
    )

    class Meta:
        model = Contribution
        fields = ("specialite", "matiere", "annee", "fichiers", "commentaire", "certifie_droits", "envoyer_quand_meme")
        labels = {"specialite": _("Spécialité"), "matiere": _("Matière")}
        help_texts = {"commentaire": _("Épreuve pratique, pages manquantes, provenance…")}
        widgets = {"commentaire": forms.Textarea(attrs={"rows": 3})}

    marquer_facultatifs = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fichiers"].widget.template_name = "forms/zone_fichiers.html"
        self.fields["specialite"].required = True
        self.fields["specialite"].queryset = Specialite.objects.select_related("examen").order_by("examen__code", "ordre", "nom")
        self.fields["matiere"].queryset = Matiere.objects.select_related("examen").order_by("examen__code", "nom")
        # Règle absolue (CDC 4.2) : seules les sessions terminées sont proposées ; clean() revérifie côté serveur.
        terminees = Session.objects.filter(date_fin_officielle__lt=timezone.localdate()).select_related("examen")
        groupes = {}
        for session in terminees.order_by("examen__code", "-annee"):
            groupes.setdefault(session.examen.code, []).append((session.annee, str(session.annee)))
        self.fields["annee"] = forms.TypedChoiceField(
            label=_("Session"), coerce=int, choices=[("", _("Choisir la session")), *groupes.items()],
            # Une année absente de la liste (session en cours, valeur forgée) : on dit la règle, pas « choix invalide ».
            error_messages={"invalid_choice": _(
                "La session %(value)s n'est pas terminée (ou n'existe pas) : nous n'acceptons aucun sujet d'une session en cours."
            )},
        )
        self.fields["certifie_droits"].label = _(
            "Je certifie avoir le droit de partager ce document, et qu'il s'agit d'un sujet d'une session terminée."
        )
        self.order_fields(["fichiers", "specialite", "annee", "matiere", "commentaire", "certifie_droits", "envoyer_quand_meme"])
        self.doublons = Sujet.objects.none()
        # La case n'apparaît que si le sujet existe déjà (voir clean).
        self.fields["envoyer_quand_meme"].widget = forms.HiddenInput()

    def clean(self):
        donnees = super().clean()
        specialite, matiere, annee = donnees.get("specialite"), donnees.get("matiere"), donnees.get("annee")
        if specialite and matiere and not matiere.specialites.filter(pk=specialite.pk).exists():
            self.add_error("matiere", _("Cette matière n'est pas au programme de la spécialité choisie."))
        if specialite and annee and not Session.objects.filter(
            examen=specialite.examen, annee=annee, date_fin_officielle__lt=timezone.localdate()
        ).exists():
            # La liste ne propose que des sessions terminées ; une valeur forgée ou d'un autre examen est refusée ici.
            self.add_error("annee", _("Choisissez une session terminée du %(examen)s.") % {"examen": specialite.examen.code})
        if matiere and annee:
            # Règle absolue (CDC 4.2) : un sujet d'une session en cours n'est même pas accepté en contribution.
            if contributions.session_non_terminee(matiere, annee):
                raise ValidationError(_(
                    "La session %(annee)s n'est pas terminée : nous n'acceptons aucun sujet d'une session en cours."
                ) % {"annee": annee})
            self.doublons = Sujet.objects.filter(matiere=matiere, session__annee=annee)
            if self.doublons.exists() and not donnees.get("envoyer_quand_meme"):
                self.fields["envoyer_quand_meme"].widget = forms.CheckboxInput()
                self.add_error("envoyer_quand_meme", _(
                    "Nous avons déjà ce sujet (%(matiere)s %(annee)s). Cochez la case si le vôtre apporte quelque chose."
                ) % {"matiere": matiere.nom, "annee": annee})
        return donnees

    def save(self, commit=True):
        contribution = super().save(commit=False)
        contribution.type = Contribution.Type.SUJET
        contribution.utilisateur = self.utilisateur
        contribution.fichier.save("sujet.pdf", ContentFile(self.pdf), save=False)
        contribution.save()
        return contribution


class PropositionCorrigeForm(EnvoiMixin, forms.ModelForm):
    """Corrigé proposé pour un sujet publié : rédigé ici, ou en PDF / photos."""

    fichiers = ChampPlusieursFichiers(
        label=_("Ou le corrigé en document"), required=False,
        help_text=_("Un PDF, ou une photo par page (JPG ou PNG, 10 au plus)."),
    )

    class Meta:
        model = Contribution
        fields = ("texte", "fichiers", "commentaire", "certifie_droits")
        help_texts = {"texte": Corrige.AIDE_REDACTION}
        widgets = {"texte": forms.Textarea(attrs={"rows": 12})}

    def __init__(self, *args, sujet=None, **kwargs):
        self.sujet = sujet
        super().__init__(*args, **kwargs)

    def clean(self):
        donnees = super().clean()
        if not donnees.get("texte", "").strip() and not donnees.get("fichiers"):
            raise ValidationError(_("Rédigez le corrigé ou joignez-le en document."))
        return donnees

    def save(self, commit=True):
        contribution = super().save(commit=False)
        contribution.type = Contribution.Type.CORRIGE
        contribution.utilisateur = self.utilisateur
        contribution.sujet_vise = self.sujet
        contribution.matiere = self.sujet.matiere
        if self.pdf:
            contribution.fichier.save("corrige.pdf", ContentFile(self.pdf), save=False)
        contribution.save()
        return contribution


# --- Modération (admin) ------------------------------------------------------------------------------

class ValidationSujetForm(forms.Form):
    session = forms.ModelChoiceField(queryset=Session.objects.none(), label=_("Session"))
    titre = forms.CharField(max_length=200)
    type_epreuve = forms.ChoiceField(choices=Sujet.TypeEpreuve.choices, label=_("Type d'épreuve"))
    duree = forms.IntegerField(min_value=1, label=_("Durée (minutes)"))
    source = forms.CharField(max_length=200, help_text=_("Exemple : MINESUP, BTS session 2025."))
    specialites = forms.ModelMultipleChoiceField(queryset=Specialite.objects.none(), widget=forms.CheckboxSelectMultiple)
    bareme = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False, label=_("Barème"))

    def __init__(self, *args, contribution, **kwargs):
        matiere = contribution.matiere
        examen = matiere.examen
        session = Session.objects.filter(examen=examen, annee=contribution.annee).first()
        kwargs.setdefault("initial", {
            "session": session, "titre": matiere.nom, "type_epreuve": Sujet.TypeEpreuve.ECRITE,
            "source": f"MINESUP, {examen.code} session {contribution.annee}",
            "specialites": [contribution.specialite] if contribution.specialite else list(matiere.specialites.all()),
        })
        super().__init__(*args, **kwargs)
        self.fields["session"].queryset = Session.objects.filter(examen=examen).order_by("-annee")
        self.fields["specialites"].queryset = matiere.specialites.all()

    def clean_session(self):
        session = self.cleaned_data["session"]
        if session.date_fin_officielle >= timezone.localdate():
            raise ValidationError(_(
                "Session en cours : un tel sujet est suspect (CDC 4.2). Rejetez la contribution au lieu de la valider."
            ))
        return session


class ValidationCorrigeForm(forms.Form):
    auteur = forms.CharField(max_length=200)
    titulaire_droits = forms.CharField(max_length=200, label=_("Titulaire des droits"))
    partie_gratuite = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 8}), required=False, label=_("Début du corrigé (visible par tous)"),
    )
    contenu = forms.CharField(widget=forms.Textarea(attrs={"rows": 12}), required=False, label=_("Suite du corrigé"))

    def __init__(self, *args, contribution, **kwargs):
        nom = contributions.nom_affiche(contribution.utilisateur)
        kwargs.setdefault("initial", {"auteur": nom, "titulaire_droits": nom, "partie_gratuite": contribution.texte})
        self.contribution = contribution
        super().__init__(*args, **kwargs)

    def clean(self):
        donnees = super().clean()
        if not (donnees.get("partie_gratuite") or donnees.get("contenu") or self.contribution.fichier):
            raise ValidationError(_("Le corrigé est vide."))
        return donnees


class RejetForm(forms.Form):
    motif = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}), label=_("Motif du rejet"),
        help_text=_("Envoyé au contributeur. Le fichier est supprimé."),
    )


class ContactForm(forms.ModelForm):
    # Piège à robots : champ invisible pour les personnes, que beaucoup de robots remplissent quand même.
    site_web = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = MessageContact
        fields = ("nom", "email", "objet", "message")
        labels = {"nom": _("Votre nom"), "email": _("Votre e-mail"), "objet": _("Objet"), "message": _("Votre message")}
        help_texts = {"email": _("Pour vous répondre ; il n'est jamais affiché ni transmis.")}
        widgets = {"message": forms.Textarea(attrs={"rows": 6})}

    def clean_message(self):
        message = self.cleaned_data["message"].strip()
        if len(message) < 10:
            raise ValidationError(_("Écrivez quelques mots de plus (10 caractères au moins)."))
        return message
