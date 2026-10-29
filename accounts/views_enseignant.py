"""CDC 11.1 : l'enseignant gère lui-même sa carte (affichage, photo, consentement) ; la photo n'est servie qu'avec
son consentement."""

import io
import uuid
from urllib.parse import quote

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _, gettext_lazy
from django.views.decorators.http import require_POST
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import Consentement, ProfilEnseignant

PHOTO_MAX_OCTETS = 2 * 1024 * 1024
PHOTO_COTE = 256  # carré, en pixels : assez pour la carte, léger en 3G


def preparer_photo(fichier):
    """Photo recadrée en carré et réenregistrée en JPEG : les métadonnées (position GPS du téléphone, appareil…)
    ne sont jamais recopiées."""
    try:
        image = Image.open(fichier)
        image.load()
    except (UnidentifiedImageError, OSError) as erreur:
        raise forms.ValidationError(_("Ce fichier n'est pas une image (JPEG, PNG ou WebP).")) from erreur
    image = ImageOps.fit(ImageOps.exif_transpose(image).convert("RGB"), (PHOTO_COTE, PHOTO_COTE))
    tampon = io.BytesIO()
    image.save(tampon, "JPEG", quality=85)
    # Nom imprévisible : la photo ne se devine pas à partir du compte.
    return ContentFile(tampon.getvalue(), name=f"{uuid.uuid4().hex}.jpg")


class ProfilEnseignantForm(forms.ModelForm):
    consentement = forms.BooleanField(
        required=False,
        label=gettext_lazy("Afficher ma carte sous les corrigés que j'ai vérifiés"),
        help_text=gettext_lazy(
            "Nom ou initiales, établissement, matières enseignées, nombre de corrigés vérifiés et photo si vous en "
            "ajoutez une. Vous pouvez la retirer à tout moment."
        ),
    )
    nouvelle_photo = forms.ImageField(
        required=False, label=gettext_lazy("Photo (facultative)"),
        widget=forms.FileInput(attrs={
            "accept": "image/jpeg,image/png,image/webp",
            "class": "mt-1 block w-full text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-vert-clair file:px-4 "
                     "file:py-2 file:font-semibold file:text-vert",
        }),
        help_text=gettext_lazy("2 Mo au plus. Elle est recadrée en carré ; sa localisation et ses autres données cachées sont supprimées."),
    )
    supprimer_photo = forms.BooleanField(required=False, label=gettext_lazy("Supprimer ma photo"))

    class Meta:
        model = ProfilEnseignant
        fields = ["affichage"]
        widgets = {"affichage": forms.RadioSelect}

    def clean_nouvelle_photo(self):
        photo = self.cleaned_data.get("nouvelle_photo")
        if photo and photo.size > PHOTO_MAX_OCTETS:
            raise forms.ValidationError(_("La photo dépasse 2 Mo."))
        return photo and preparer_photo(photo)

    def save(self, commit=True):
        profil = super().save(commit=False)
        nouvelle = self.cleaned_data.get("nouvelle_photo")
        if (nouvelle or self.cleaned_data.get("supprimer_photo")) and profil.photo:
            profil.photo.delete(save=False)
        if nouvelle:
            profil.photo.save(nouvelle.name, nouvelle, save=False)
        profil.save()
        utilisateur, objet = profil.utilisateur, Consentement.Objet.PROFIL_ENSEIGNANT
        if self.cleaned_data["consentement"] and not profil.visible:
            Consentement.objects.create(utilisateur=utilisateur, objet=objet, version=settings.VERSION_POLITIQUES)
        elif not self.cleaned_data["consentement"]:
            Consentement.revoquer(utilisateur, objet)
        return profil


def profil_de(request):
    profil = getattr(request.user, "profil_enseignant", None)
    if profil is None:
        raise Http404
    return profil


@login_required
def profil_enseignant(request):
    profil = profil_de(request)
    form = ProfilEnseignantForm(
        request.POST or None, request.FILES or None, instance=profil, initial={"consentement": profil.visible}
    )
    if form.is_valid():
        form.save()
        messages.success(request, _("Votre carte d'enseignant est enregistrée."))
        return redirect("accounts:profil_enseignant")
    nombre = profil.utilisateur.corriges_verifies.visibles().count()
    return render(request, "accounts/profil_enseignant.html",
                  {"form": form, "profil": profil, "nombre": nombre, "matieres": profil.matieres.order_by("nom")})


@login_required
@require_POST
def retirer_profil_enseignant(request):
    """Tout retirer d'un coup : consentement révoqué et photo effacée."""
    profil = profil_de(request)
    Consentement.revoquer(request.user, Consentement.Objet.PROFIL_ENSEIGNANT)
    if profil.photo:
        profil.photo.delete(save=True)
    messages.success(request, _("Votre carte est retirée : les corrigés affichent seulement « Vérifié par un enseignant »."))
    return redirect("accounts:profil_enseignant")


def photo_enseignant(request, pk):
    profil = get_object_or_404(ProfilEnseignant.objects.select_related("utilisateur"), pk=pk)
    # Sans consentement, la photo n'existe pas pour les autres (l'enseignant la voit sur sa propre page).
    if not profil.photo or not (profil.visible or profil.utilisateur_id == request.user.pk):
        raise Http404
    if settings.FICHIERS_PAR_NGINX:
        reponse = HttpResponse(content_type="image/jpeg")
        reponse["X-Accel-Redirect"] = "/fichiers-proteges/" + quote(profil.photo.name)
    else:
        reponse = FileResponse(profil.photo.open("rb"), content_type="image/jpeg")
    # Pas de cache : un retrait du consentement s'applique tout de suite.
    reponse["Cache-Control"] = "no-store"
    return reponse
