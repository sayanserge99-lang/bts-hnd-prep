from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from accounts.moderation import LimiteAuxMatieresDuModerateur
from sujets.views import envoyer_pdf

from . import contributions
from .forms import RejetForm, ValidationCorrigeForm, ValidationSujetForm
from .models import Contribution, DemandeRetrait, MessageContact, Signalement

# Un signalement ou une demande de retrait vise un sujet ou un corrigé.
CIBLES = ("sujet__matiere", "corrige__sujet__matiere")


@admin.register(Contribution)
class ContributionAdmin(LimiteAuxMatieresDuModerateur, admin.ModelAdmin):
    """File de modération (CDC 3.9) : valider (sujet ou corrigé créé en brouillon) ou rejeter avec motif."""

    # Maquette (écran 7) : document, envoyé par, contrôles en clair, décision.
    list_display = ("document", "envoye_par", "controles", "decision")
    list_display_links = ("document",)
    list_filter = ("statut", "type", "matiere__examen")
    search_fields = ("utilisateur__email", "matiere__nom_fr", "matiere__nom_en", "commentaire")
    readonly_fields = (
        "type", "utilisateur", "matiere", "specialite", "annee", "sujet_vise", "lien_fichier", "texte", "commentaire",
        "certifie_droits", "date_certification", "statut", "motif_rejet", "sujet", "corrige", "jours_offerts",
        "traitee_par", "traitee_le", "cree_le",
    )
    exclude = ("fichier",)

    def has_add_permission(self, request):
        return False  # les contributions arrivent du site

    @admin.display(description=_("contribution"))
    def libelle(self, contribution):
        return contribution.libelle

    @admin.display(description=_("document"), ordering="-cree_le")
    def document(self, contribution):
        return format_html("{}<br><small>{} · {}</small>", contribution.libelle, contribution.get_type_display(),
                           date_format(timezone.localtime(contribution.cree_le), "d/m/Y H:i"))

    @admin.display(description=_("envoyé par"), ordering="utilisateur__email")
    def envoye_par(self, contribution):
        return contributions.nom_affiche(contribution.utilisateur)

    @admin.display(description=_("contrôles"))
    def controles(self, contribution):
        """Maquette (écran 7) : l'état en clair, icône + texte, jamais la couleur seule."""
        if contribution.type != Contribution.Type.SUJET:
            return "—"
        if not contribution.session_terminee:
            return format_html(
                '<strong style="color:#b42318">⛔ {}</strong><br><small>{}</small>',
                _("Session pas encore terminée"), _("Publication impossible, même par un administrateur."),
            )
        doublon = contribution.doublons.select_related("session").first()
        if doublon:
            if doublon.statut == doublon.Statut.PUBLIE:
                lien = reverse("sujets:detail", args=[doublon.pk])
            else:
                lien = reverse("admin:sujets_sujet_change", args=[doublon.pk])
            return format_html(
                '<strong style="color:#7a5a00">⚠ {}</strong><br><a href="{}" target="_blank" rel="noopener">{}</a>',
                _("Doublon possible"), lien, _("Comparer avec le sujet en ligne"),
            )
        return format_html('<strong style="color:#0f6b4f">✓ {}</strong>', _("Session terminée, pas de doublon"))

    @admin.display(description=_("décision"))
    def decision(self, contribution):
        if contribution.statut != Contribution.Statut.EN_ATTENTE:
            return contribution.get_statut_display()
        rejeter = reverse("admin:communaute_contribution_rejeter", args=[contribution.pk])
        if not contribution.session_terminee:
            # Un seul choix possible : aucun bouton « Valider » (CDC 4.2).
            return format_html(
                '<a class="button" style="background:#b42318;color:#fff;white-space:nowrap" href="{}?motif=session_non_terminee">{}</a>',
                rejeter, _("Refuser et supprimer"),
            )
        valider = reverse("admin:communaute_contribution_valider", args=[contribution.pk])
        return format_html('<span style="white-space:nowrap"><a class="button" href="{}">{}</a> '
                           '<a class="button default" href="{}">{}</a></span>',
                           rejeter, _("Refuser"), valider, _("Valider"))

    @admin.display(description=_("fichier"))
    def lien_fichier(self, contribution):
        if not contribution.fichier:
            return "—"
        url = reverse("admin:communaute_contribution_fichier", args=[contribution.pk])
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', url, _("Ouvrir le PDF"))

    def get_urls(self):
        vue = self.admin_site.admin_view
        return [
            path("<int:pk>/fichier/", vue(self.vue_fichier), name="communaute_contribution_fichier"),
            path("<int:pk>/valider/", vue(self.vue_valider), name="communaute_contribution_valider"),
            path("<int:pk>/rejeter/", vue(self.vue_rejeter), name="communaute_contribution_rejeter"),
        ] + super().get_urls()

    def _contribution(self, request, pk, en_attente=True):
        # get_queryset limite le modérateur à ses matières.
        contribution = get_object_or_404(self.get_queryset(request).select_related("matiere__examen", "utilisateur"), pk=pk)
        if en_attente and contribution.statut != Contribution.Statut.EN_ATTENTE:
            raise Http404
        return contribution

    def vue_fichier(self, request, pk):
        if not self.has_view_permission(request):
            raise PermissionDenied
        contribution = self._contribution(request, pk, en_attente=False)
        if not contribution.fichier:
            raise Http404
        return envoyer_pdf(request, contribution.fichier, f"contribution-{contribution.pk}.pdf")

    def _page(self, request, contribution, form, titre, gabarit):
        contexte = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": titre,
            "contribution": contribution,
            "form": form,
            "doublons": contribution.doublons.select_related("session"),
            "controles": self.controles(contribution),
        }
        return TemplateResponse(request, f"admin/communaute/contribution/{gabarit}", contexte)

    def vue_valider(self, request, pk):
        if not self.has_change_permission(request):
            raise PermissionDenied
        contribution = self._contribution(request, pk)
        if not contribution.session_terminee:
            # Même par une requête forgée : une contribution d'une session en cours ne se valide pas.
            self.message_user(request, _("Session pas encore terminée : cette contribution ne peut être que refusée."), messages.ERROR)
            return redirect(reverse("admin:communaute_contribution_rejeter", args=[contribution.pk]) + "?motif=session_non_terminee")
        if contribution.type == Contribution.Type.SUJET:
            form = ValidationSujetForm(request.POST or None, contribution=contribution)
        else:
            form = ValidationCorrigeForm(request.POST or None, contribution=contribution)
        if form.is_valid():
            if contribution.type == Contribution.Type.SUJET:
                sujet = contributions.valider_sujet(contribution, request.user, **form.cleaned_data)
                self.message_user(request, _("Sujet créé en brouillon. Publiez-le quand il est vérifié : la règle de publication s'applique."))
                return redirect("admin:sujets_sujet_change", sujet.pk)
            corrige = contributions.valider_corrige(contribution, request.user, **form.cleaned_data)
            self.message_user(request, _("Corrigé créé en brouillon (« Proposé par la communauté »). Relisez-le puis publiez-le."))
            return redirect("admin:sujets_corrige_change", corrige.pk)
        return self._page(request, contribution, form, _("Valider la contribution"), "valider.html")

    def vue_rejeter(self, request, pk):
        if not self.has_change_permission(request):
            raise PermissionDenied
        contribution = self._contribution(request, pk)
        form = RejetForm(request.POST or None, initial={"motif": request.GET.get("motif")})
        if form.is_valid():
            contributions.rejeter(contribution, request.user, form.texte())
            self.message_user(request, _("Contribution rejetée ; le fichier est supprimé."), messages.WARNING)
            return redirect("admin:communaute_contribution_changelist")
        return self._page(request, contribution, form, _("Refuser la contribution"), "rejeter.html")


@admin.register(Signalement)
class SignalementAdmin(LimiteAuxMatieresDuModerateur, admin.ModelAdmin):
    # Une question de quiz est rattachée à la matière de son chapitre : le modérateur de la matière la voit.
    chemins_matiere = (*CIBLES, "question__chapitre__matiere")
    list_display = ("__str__", "cible", "motif_court", "utilisateur", "statut", "cree_le")
    list_filter = ("statut", ("question", admin.EmptyFieldListFilter))
    list_select_related = ("question__chapitre", "sujet", "corrige__sujet", "utilisateur")
    readonly_fields = ("utilisateur", "sujet", "corrige", "question", "lien_cible", "motif", "cree_le")

    @admin.display(description=_("cible"))
    def cible(self, signalement):
        if signalement.question_id:
            return _("Question (%(chapitre)s)") % {"chapitre": signalement.question.chapitre.titre}
        return _("Corrigé") if signalement.corrige_id else _("Sujet")

    @admin.display(description=_("motif"))
    def motif_court(self, signalement):
        return signalement.motif[:80]

    @admin.display(description=_("ouvrir"))
    def lien_cible(self, signalement):
        if signalement.question_id:
            url = reverse("admin:entrainement_question_change", args=[signalement.question_id])
        elif signalement.corrige_id:
            url = reverse("admin:sujets_corrige_change", args=[signalement.corrige_id])
        else:
            url = reverse("admin:sujets_sujet_change", args=[signalement.sujet_id])
        return format_html('<a href="{}">{}</a>', url, _("Ouvrir dans l'administration"))


@admin.register(DemandeRetrait)
class DemandeRetraitAdmin(LimiteAuxMatieresDuModerateur, admin.ModelAdmin):
    chemins_matiere = CIBLES
    list_display = ("__str__", "demandeur_nom", "demandeur_email", "certifie_titulaire", "statut", "cree_le")
    list_filter = ("statut",)
    readonly_fields = ("traitee_le",)
    actions = ["accepter", "refuser"]

    @admin.action(description=_("Accepter : supprimer le document"))
    def accepter(self, request, queryset):
        demandes = queryset.filter(statut=DemandeRetrait.Statut.RECUE)
        for demande in demandes:
            demande.accepter()
        self.message_user(
            request, ngettext("%d demande acceptée.", "%d demandes acceptées.", len(demandes)) % len(demandes)
        )

    @admin.action(description=_("Refuser : republier le contenu"))
    def refuser(self, request, queryset):
        demandes = queryset.filter(statut=DemandeRetrait.Statut.RECUE)
        for demande in demandes:
            demande.refuser()
        self.message_user(
            request,
            ngettext("%d demande refusée.", "%d demandes refusées.", len(demandes)) % len(demandes),
            messages.SUCCESS,
        )


@admin.register(MessageContact)
class MessageContactAdmin(admin.ModelAdmin):
    list_display = ("__str__", "email", "traite", "cree_le")
    list_filter = ("traite", "objet")
    search_fields = ("nom", "email", "message")
    readonly_fields = ("nom", "email", "objet", "message", "utilisateur", "cree_le")
    actions = ["marquer_traites"]

    def has_add_permission(self, request):
        return False

    @admin.action(description=_("Marquer comme traités"))
    def marquer_traites(self, request, queryset):
        nombre = queryset.update(traite=True)
        self.message_user(request, ngettext("%d message traité.", "%d messages traités.", nombre) % nombre)
