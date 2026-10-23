"""Un modérateur n'agit que sur les matières qui lui sont attribuées (CDC 7)."""

from django.db.models import Q

from catalogue.models import Chapitre, Matiere


def est_administrateur(utilisateur):
    """Superutilisateur ou membre du groupe Administrateur (CDC 7)."""
    if not utilisateur.is_authenticated:
        return False
    return utilisateur.is_superuser or utilisateur.groups.filter(name="Administrateur").exists()


def est_limite_a_ses_matieres(utilisateur):
    """Vrai pour un modérateur ; faux pour un administrateur (groupe ou superutilisateur)."""
    return not est_administrateur(utilisateur)


def matieres_de(utilisateur):
    return Matiere.objects.filter(moderateurs__moderateur=utilisateur)


class LimiteAuxMatieresDuModerateur:
    """À placer avant admin.ModelAdmin : liste, fiches, actions et listes de choix suivent les matières attribuées.

    `chemins_matiere` : comment aller de l'objet à sa matière ; plusieurs chemins se combinent par « ou »
    (un signalement vise un sujet ou un corrigé).
    """

    chemins_matiere = ("matiere",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if not est_limite_a_ses_matieres(request.user):
            return queryset
        siennes = matieres_de(request.user).values("pk")
        condition = Q()
        for chemin in self.chemins_matiere:
            condition |= Q(**{f"{chemin}__in": siennes})
        # Chemins faits de clés étrangères simples : pas de doublons, donc pas de distinct()
        # (qui gênerait update() dans les actions groupées).
        return queryset.filter(condition)

    def _hors_de_ses_matieres(self, request, obj):
        return (
            obj is not None
            and est_limite_a_ses_matieres(request.user)
            and not self.get_queryset(request).filter(pk=obj.pk).exists()
        )

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) and not self._hors_de_ses_matieres(request, obj)

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and not self._hors_de_ses_matieres(request, obj)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and not self._hors_de_ses_matieres(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if est_limite_a_ses_matieres(request.user):
            queryset = _choix_limites(db_field.related_model, request.user)
            if queryset is not None:
                kwargs["queryset"] = queryset
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if est_limite_a_ses_matieres(request.user):
            queryset = _choix_limites(db_field.related_model, request.user)
            if queryset is not None:
                kwargs["queryset"] = queryset
        return super().formfield_for_manytomany(db_field, request, **kwargs)


def _choix_limites(modele, utilisateur):
    """Choix proposés dans un formulaire : uniquement ce qui relève des matières du modérateur."""
    from entrainement.models import Question
    from sujets.models import Corrige, Sujet

    siennes = matieres_de(utilisateur)
    chemins = {Matiere: "pk", Chapitre: "matiere", Sujet: "matiere", Corrige: "sujet__matiere", Question: "chapitre__matiere"}
    chemin = chemins.get(modele)
    if chemin is None:
        return None
    return modele.objects.filter(**{f"{chemin}__in": siennes})
