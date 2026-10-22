import re

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector, SearchVectorField
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F, Q, Value
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# Configurations de recherche PostgreSQL par langue d'examen (fr_unaccent : migration 0002).
CONFIG_RECHERCHE = {"fr": "fr_unaccent", "en": "english"}

FICHIER_NON_CHARGE = object()


class PublicationInterdite(ValidationError):
    """Tentative de publier un sujet d'une session qui n'est pas officiellement terminée (CDC 4.2)."""


def _message_interdiction(session):
    return PublicationInterdite(
        _("La session %(session)s se termine officiellement le %(date)s : ses sujets ne peuvent pas être publiés avant."),
        code="session_non_terminee",
        params={"session": session, "date": session.date_fin_officielle},
    )


class SujetQuerySet(models.QuerySet):
    def publies(self):
        return self.filter(statut=Sujet.Statut.PUBLIE)

    def publiables(self, aujourd_hui=None):
        return self.filter(session__date_fin_officielle__lt=aujourd_hui or timezone.localdate())

    def rechercher(self, texte, langue):
        """Sujets contenant tous les mots, triés par pertinence.

        Chaque mot vaut aussi comme début de mot (« amortis » trouve « amortissement »),
        et les accents sont ignorés en français.
        """
        mots = re.findall(r"[^\W_]+", texte)
        if not mots:
            return self.none()
        requete = SearchQuery(
            " & ".join(f"{mot}:*" for mot in mots), config=CONFIG_RECHERCHE[langue], search_type="raw"
        )
        return (
            self.filter(recherche=requete)
            # F() et non "recherche" : un simple nom ferait recalculer le vecteur et perdre les poids.
            .annotate(pertinence=SearchRank(F("recherche"), requete))
            .order_by("-pertinence")
        )

    # Les opérations groupées contournent save() : on y applique la même règle.
    def update(self, **kwargs):
        if kwargs.get("statut") == Sujet.Statut.PUBLIE:
            bloque = self.filter(session__date_fin_officielle__gte=timezone.localdate()).select_related("session").first()
            if bloque:
                raise _message_interdiction(bloque.session)
        return super().update(**kwargs)

    def bulk_update(self, objs, fields, batch_size=None):
        if "statut" in fields:
            for sujet in objs:
                sujet.verifier_publication()
        return super().bulk_update(objs, fields, batch_size=batch_size)

    def bulk_create(self, objs, *args, **kwargs):
        for sujet in objs:
            sujet.verifier_publication()
        return super().bulk_create(objs, *args, **kwargs)


class Sujet(models.Model):
    class Statut(models.TextChoices):
        BROUILLON = "brouillon", _("Brouillon")
        PUBLIE = "publie", _("Publié")
        MASQUE = "masque", _("Masqué (demande de retrait en cours)")

    class TypeEpreuve(models.TextChoices):
        ECRITE = "ecrite", _("Écrite")
        PRATIQUE = "pratique", _("Pratique")

    titre = models.CharField(max_length=200)
    session = models.ForeignKey("catalogue.Session", on_delete=models.PROTECT, related_name="sujets")
    matiere = models.ForeignKey("catalogue.Matiere", on_delete=models.PROTECT, related_name="sujets")
    specialites = models.ManyToManyField(
        "catalogue.Specialite",
        related_name="sujets",
        help_text=_("Uniquement des spécialités auxquelles la matière est rattachée."),
    )
    type_epreuve = models.CharField(_("type d'épreuve"), max_length=10, choices=TypeEpreuve.choices)
    duree = models.PositiveSmallIntegerField(_("durée (minutes)"))
    bareme = models.TextField(_("barème"), blank=True)
    fichier = models.FileField(_("fichier PDF"), upload_to="sujets/%Y/")
    nb_pages = models.PositiveSmallIntegerField(_("nombre de pages"), null=True, blank=True)
    texte_extrait = models.TextField(blank=True, help_text=_("Rempli par la tâche d'extraction, sert à la recherche."))
    recherche = SearchVectorField(null=True, editable=False)
    source = models.CharField(max_length=200, help_text=_("Exemple : MINESUP, BTS session 2025."))
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.BROUILLON)
    date_publication = models.DateTimeField(null=True, blank=True, editable=False)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    objects = SujetQuerySet.as_manager()

    class Meta:
        verbose_name = _("sujet")
        ordering = ["-session__annee", "titre"]
        indexes = [GinIndex(fields=["recherche"], name="sujet_recherche_gin")]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Valeur brute, pour ne pas déclencher de requête quand le champ n'est pas chargé (.only(), .defer()).
        valeur = self.__dict__.get("fichier", FICHIER_NON_CHARGE)
        self._fichier_initial = getattr(valeur, "name", valeur)

    def __str__(self):
        return f"{self.titre} — {self.session}"

    def peut_etre_publie(self, aujourd_hui=None):
        return self.session.est_terminee(aujourd_hui)

    def verifier_publication(self):
        if self.statut == self.Statut.PUBLIE and not self.peut_etre_publie():
            raise _message_interdiction(self.session)

    def clean(self):
        if self.session_id and self.matiere_id and self.session.examen_id != self.matiere.examen_id:
            raise ValidationError({"matiere": _("La matière n'appartient pas à l'examen de la session.")})
        if self.session_id:
            try:
                self.verifier_publication()
            except PublicationInterdite as erreur:
                raise ValidationError({"statut": erreur}) from erreur

    def save(self, *args, **kwargs):
        # Aucun rôle, superutilisateur compris, ne peut passer outre.
        self.verifier_publication()
        if self.statut == self.Statut.PUBLIE and self.date_publication is None:
            self.date_publication = timezone.now()
        elif self.statut == self.Statut.BROUILLON:
            self.date_publication = None
        super().save(*args, **kwargs)
        self.mettre_a_jour_recherche()
        if self._fichier_initial is not FICHIER_NON_CHARGE and self.fichier.name != self._fichier_initial:
            self._fichier_initial = self.fichier.name
            # Après validation en base : la tâche doit trouver le sujet et son fichier.
            transaction.on_commit(lambda: _traiter_pdf(self.pk))

    def mettre_a_jour_recherche(self):
        # Les opérations groupées ne passent pas ici : relancer `manage.py reindexer_recherche`.
        config = CONFIG_RECHERCHE[self.session.examen.langue]
        noms_matiere = " ".join(filter(None, [self.matiere.nom_fr, self.matiere.nom_en]))
        vecteur = (
            SearchVector(Value(noms_matiere), weight="A", config=config)
            + SearchVector("titre", weight="A", config=config)
            + SearchVector("texte_extrait", weight="C", config=config)
        )
        Sujet.objects.filter(pk=self.pk).update(recherche=vecteur)

    def coefficient_pour(self, specialite):
        lien = self.matiere.specialitematiere_set.filter(specialite=specialite).first()
        return lien.coefficient if lien else None


def _traiter_pdf(sujet_id):
    from .tasks import traiter_pdf_du_sujet  # import tardif : tasks importe ce module

    traiter_pdf_du_sujet.delay(sujet_id)


class CorrigeQuerySet(models.QuerySet):
    def visibles(self):
        """Corrigés lisibles par le public : publiés, rédigés, et rattachés à un sujet publié.

        Un corrigé dévoile le contenu du sujet : il suit donc la visibilité du sujet.
        """
        return self.filter(
            publication=Corrige.Publication.PUBLIE,
            statut__in=[Corrige.Statut.VERIFIE, Corrige.Statut.COMMUNAUTE],
            sujet__statut=Sujet.Statut.PUBLIE,
        ).order_by(
            # Le corrigé vérifié par un enseignant passe en premier (CDC 10.7).
            models.Case(models.When(statut=Corrige.Statut.VERIFIE, then=0), default=1),
            "-modifie_le",
        )

    def update(self, **kwargs):
        if kwargs.get("publication") == Corrige.Publication.PUBLIE:
            bloque = (
                self.filter(sujet__session__date_fin_officielle__gte=timezone.localdate())
                .select_related("sujet__session")
                .first()
            )
            if bloque:
                raise _message_interdiction(bloque.sujet.session)
        return super().update(**kwargs)


class Corrige(models.Model):
    class Statut(models.TextChoices):
        EN_PREPARATION = "en_preparation", _("En préparation")
        COMMUNAUTE = "communaute", _("Proposé par la communauté")
        VERIFIE = "verifie", _("Vérifié par un enseignant")

    class Publication(models.TextChoices):
        BROUILLON = "brouillon", _("Brouillon")
        PUBLIE = "publie", _("Publié")
        MASQUE = "masque", _("Masqué (demande de retrait en cours)")

    class RegimePropriete(models.TextChoices):
        PLATEFORME = "plateforme", _("Plateforme")
        ENSEIGNANT = "enseignant", _("Enseignant")
        PARTAGE = "partage", _("Partagé")

    AIDE_REDACTION = _(
        "Markdown : **gras**, listes, tableaux (| a | b |), code entre ```. "
        "Formules : $x^2$ dans le texte, $$\\frac{a}{b}$$ sur sa propre ligne."
    )

    sujet = models.ForeignKey(Sujet, on_delete=models.CASCADE, related_name="corriges")
    partie_gratuite = models.TextField(
        _("début du corrigé"), blank=True,
        help_text=_("Visible par tous (par exemple l'exercice 1). ") + AIDE_REDACTION,
    )
    contenu = models.TextField(
        _("suite du corrigé"), blank=True,
        help_text=_("Réservée aux abonnés une fois le paiement ouvert (CDC 3.3) ; visible par tous d'ici là."),
    )
    fichier = models.FileField(_("fichier PDF"), upload_to="corriges/%Y/", blank=True)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.EN_PREPARATION)
    publication = models.CharField(max_length=10, choices=Publication.choices, default=Publication.BROUILLON)
    auteur = models.CharField(max_length=200)
    titulaire_droits = models.CharField(_("titulaire des droits"), max_length=200)
    regime_propriete = models.CharField(
        _("régime de propriété"), max_length=12, choices=RegimePropriete.choices, blank=True
    )
    partenariat = models.ForeignKey(
        "partenaires.Partenariat", on_delete=models.PROTECT, null=True, blank=True, related_name="corriges"
    )
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    objects = CorrigeQuerySet.as_manager()

    class Meta:
        verbose_name = _("corrigé")
        constraints = [
            models.CheckConstraint(
                condition=~Q(partie_gratuite="") | ~Q(contenu="") | ~Q(fichier=""), name="corrige_contenu_ou_fichier"
            ),
            # CDC 10.1 : un corrigé sans titulaire des droits ne peut pas exister.
            models.CheckConstraint(condition=~Q(titulaire_droits=""), name="corrige_titulaire_obligatoire"),
            # CDC 10.6 : régime de propriété obligatoire pour un corrigé issu d'un partenariat.
            models.CheckConstraint(
                condition=Q(partenariat__isnull=True) | ~Q(regime_propriete=""),
                name="corrige_partenariat_avec_regime",
            ),
        ]

    def __str__(self):
        return f"Corrigé · {self.sujet}"

    def verifier_publication(self):
        # Même règle que le sujet : un corrigé publié pendant la session dévoilerait l'épreuve.
        if self.publication == self.Publication.PUBLIE and not self.sujet.peut_etre_publie():
            raise _message_interdiction(self.sujet.session)

    def clean(self):
        if self.sujet_id:
            try:
                self.verifier_publication()
            except PublicationInterdite as erreur:
                raise ValidationError({"publication": erreur}) from erreur

    def save(self, *args, **kwargs):
        self.verifier_publication()
        super().save(*args, **kwargs)


class Favori(models.Model):
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favoris")
    sujet = models.ForeignKey(Sujet, on_delete=models.CASCADE, related_name="favoris")
    date_ajout = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("favori")
        constraints = [
            models.UniqueConstraint(fields=["utilisateur", "sujet"], name="favori_unique"),
        ]

    def __str__(self):
        return f"{self.utilisateur} ★ {self.sujet}"
