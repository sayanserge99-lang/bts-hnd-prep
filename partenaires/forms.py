from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from catalogue.models import Matiere

from .models import EpreuveInterne

TAILLE_MAX = 20 * 1024 * 1024  # même limite que Nginx (deploy/nginx.conf)


class EpreuveInterneForm(forms.ModelForm):
    class Meta:
        model = EpreuveInterne
        fields = ("titre", "matiere", "type", "annee_academique", "fichier", "publiee")
        help_texts = {"publiee": _("Visible par vos étudiants validés (convention de partenariat active requise).")}

    def __init__(self, *args, convention_active, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["matiere"].queryset = Matiere.objects.select_related("examen").order_by("examen__code", "nom")
        self.convention_active = convention_active

    def clean_fichier(self):
        fichier = self.cleaned_data["fichier"]
        if fichier.size > TAILLE_MAX:
            raise ValidationError(_("Le fichier dépasse 20 Mo."))
        debut = fichier.read(5)
        fichier.seek(0)
        if debut != b"%PDF-":
            raise ValidationError(_("Le fichier doit être un PDF."))
        return fichier

    def clean_publiee(self):
        # Les épreuves appartiennent à l'établissement : sans convention signée, on ne les diffuse pas (CDC 10.6).
        if self.cleaned_data["publiee"] and not self.convention_active:
            raise ValidationError(_("Publication impossible sans convention de partenariat active."))
        return self.cleaned_data["publiee"]
