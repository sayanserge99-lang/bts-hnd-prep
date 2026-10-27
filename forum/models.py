"""Forum (CDC 3.7) : questions-réponses par matière, modéré.

Modération a posteriori : un message paraît tout de suite ; signalé plusieurs fois, il est masqué en
attendant le modérateur de la matière. Aucun fichier joint : rien ne peut être déposé ici, donc pas de sujet
d'une session en cours (CDC 4.2) ; un texte recopié se signale et se masque comme le reste.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

LONGUEUR_MAX = 5000


class DiscussionQuerySet(models.QuerySet):
    def visibles(self):
        # Une discussion rattachée à un sujet suit la visibilité du sujet (masqué après une demande de retrait…).
        return self.filter(masquee=False).filter(Q(sujet__isnull=True) | Q(sujet__statut="publie"))


class Discussion(models.Model):
    matiere = models.ForeignKey("catalogue.Matiere", on_delete=models.PROTECT, related_name="discussions")
    sujet = models.ForeignKey(
        "sujets.Sujet", on_delete=models.SET_NULL, null=True, blank=True, related_name="discussions",
        help_text=_("Facultatif : le sujet dont parle la question."),
    )
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="discussions")
    titre = models.CharField(_("question"), max_length=200)
    # Facultatif : une question courte se suffit souvent à elle-même.
    texte = models.TextField(_("détails"), max_length=LONGUEUR_MAX, blank=True)
    reponse_acceptee = models.ForeignKey(
        "Reponse", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text=_("Choisie par l'auteur de la question : celle qui l'a aidé."),
    )
    masquee = models.BooleanField(_("masquée"), default=False)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(_("modifiée le"), null=True, blank=True)
    derniere_activite = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = DiscussionQuerySet.as_manager()

    class Meta:
        verbose_name = _("discussion")
        ordering = ["-derniere_activite"]

    def __str__(self):
        return self.titre


class Reponse(models.Model):
    discussion = models.ForeignKey(Discussion, on_delete=models.CASCADE, related_name="reponses")
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reponses_forum")
    texte = models.TextField(_("réponse"), max_length=LONGUEUR_MAX)
    masquee = models.BooleanField(_("masquée"), default=False)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(_("modifiée le"), null=True, blank=True)

    class Meta:
        verbose_name = _("réponse")
        ordering = ["cree_le", "pk"]

    def __str__(self):
        return f"{self.auteur} · {self.discussion}"


class SignalementForum(models.Model):
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="signalements_forum")
    discussion = models.ForeignKey(Discussion, on_delete=models.CASCADE, null=True, blank=True, related_name="signalements")
    reponse = models.ForeignKey(Reponse, on_delete=models.CASCADE, null=True, blank=True, related_name="signalements")
    motif = models.CharField(max_length=300)
    traite = models.BooleanField(_("traité"), default=False)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("signalement du forum")
        verbose_name_plural = _("signalements du forum")
        constraints = [
            models.CheckConstraint(
                condition=(Q(discussion__isnull=False) & Q(reponse__isnull=True))
                | (Q(discussion__isnull=True) & Q(reponse__isnull=False)),
                name="signalement_forum_une_seule_cible",
            ),
            # Un même compte ne compte qu'une fois : trois signalements = trois personnes.
            models.UniqueConstraint(fields=["utilisateur", "discussion"], name="un_signalement_par_discussion"),
            models.UniqueConstraint(fields=["utilisateur", "reponse"], name="un_signalement_par_reponse"),
        ]

    def __str__(self):
        return f"{self.utilisateur} · {self.discussion or self.reponse}"

    @property
    def cible(self):
        return self.discussion or self.reponse
