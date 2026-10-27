"""Contributions (CDC 3.7) : envoi, contrôles, validation ou rejet par le modérateur, récompense.

Un sujet contribué devient un sujet en brouillon : sa publication passe ensuite par l'action « Publier »,
donc par la règle de publication (CDC 4.2). Un sujet d'une session en cours est refusé dès l'envoi.
"""

from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext as _

from catalogue.models import Session
from paiements.models import Abonnement
from sujets.models import Corrige, Sujet

from .models import Contribution

EXTENSIONS_IMAGES = {".jpg", ".jpeg", ".png"}


def en_pdf(fichiers):
    """Un PDF tel quel, ou des photos (une par page, dans l'ordre d'envoi) assemblées en un seul PDF.

    Lève ValueError avec un message pour l'utilisateur.
    """
    if not fichiers:
        raise ValueError(_("Ajoutez le document (PDF ou photos)."))
    for fichier in fichiers:
        if fichier.size > settings.CONTRIBUTION_TAILLE_MAX_FICHIER:
            raise ValueError(_("« %(nom)s » dépasse 10 Mo.") % {"nom": fichier.name})
    if len(fichiers) == 1 and Path(fichiers[0].name).suffix.lower() == ".pdf":
        contenu = fichiers[0].read()
        if not contenu.startswith(b"%PDF"):
            raise ValueError(_("Le fichier doit être un PDF."))
        return contenu
    if len(fichiers) > settings.CONTRIBUTION_PHOTOS_MAX:
        raise ValueError(_("%(n)s photos au plus.") % {"n": settings.CONTRIBUTION_PHOTOS_MAX})
    if not all(Path(fichier.name).suffix.lower() in EXTENSIONS_IMAGES for fichier in fichiers):
        raise ValueError(_("Envoyez un seul PDF, ou des photos JPG ou PNG (une par page)."))
    import img2pdf  # installé avec OCRmyPDF

    try:
        return img2pdf.convert([fichier.read() for fichier in fichiers])
    except (img2pdf.ImageOpenError, ValueError) as erreur:
        raise ValueError(_("Photo illisible : %(erreur)s") % {"erreur": erreur}) from erreur


def session_non_terminee(matiere, annee):
    """La session de cette année n'est pas finie (ou pas encore créée et l'année n'est pas passée) : suspect."""
    session = Session.objects.filter(examen=matiere.examen, annee=annee).first()
    if session:
        return session.date_fin_officielle >= timezone.localdate()
    return annee >= timezone.localdate().year


def envois_aujourd_hui(utilisateur):
    return Contribution.objects.filter(utilisateur=utilisateur, cree_le__date=timezone.localdate()).count()


def nom_affiche(utilisateur):
    return utilisateur.get_full_name() or utilisateur.email.split("@")[0]


@transaction.atomic
def valider_sujet(contribution, moderateur, *, session, titre, type_epreuve, duree, source, specialites, bareme=""):
    """Crée le sujet en brouillon avec le PDF de la contribution, puis offre les jours au contributeur."""
    # Règle absolue (CDC 4.2) : l'année déclarée compte, pas seulement la session choisie dans le formulaire
    # (sinon un sujet de 2027 pourrait être classé « 2025 » et publié avant la fin de sa session).
    if session_non_terminee(contribution.matiere, contribution.annee):
        raise ValidationError(_("Session pas encore terminée : cette contribution ne peut être que refusée."))
    sujet = Sujet(
        titre=titre, session=session, matiere=contribution.matiere, type_epreuve=type_epreuve, duree=duree,
        source=source, bareme=bareme, statut=Sujet.Statut.BROUILLON,
    )
    with contribution.fichier.open("rb") as source_pdf:
        sujet.fichier.save(f"contribution-{contribution.pk}.pdf", ContentFile(source_pdf.read()), save=False)
    sujet.save()
    sujet.specialites.set(specialites)

    jours = settings.JOURS_OFFERTS_PAR_SUJET
    if jours:
        Abonnement.offrir_jours(contribution.utilisateur, jours, contribution)
    _clore(contribution, moderateur, Contribution.Statut.VALIDEE, sujet=sujet, jours_offerts=jours)
    return sujet


@transaction.atomic
def valider_corrige(contribution, moderateur, *, auteur, titulaire_droits, partie_gratuite, contenu):
    """Crée le corrigé « proposé par la communauté », en brouillon : le modérateur le relit puis le publie."""
    corrige = Corrige(
        sujet=contribution.sujet_vise, statut=Corrige.Statut.COMMUNAUTE, publication=Corrige.Publication.BROUILLON,
        auteur=auteur, titulaire_droits=titulaire_droits, partie_gratuite=partie_gratuite, contenu=contenu,
    )
    if contribution.fichier:
        with contribution.fichier.open("rb") as source_pdf:
            corrige.fichier.save(f"contribution-{contribution.pk}.pdf", ContentFile(source_pdf.read()), save=False)
    corrige.save()
    _clore(contribution, moderateur, Contribution.Statut.VALIDEE, corrige=corrige)
    return corrige


def rejeter(contribution, moderateur, motif):
    """Rejet motivé ; le fichier est supprimé (CDC 4.2 : une contribution suspecte est rejetée et supprimée)."""
    if contribution.fichier:
        contribution.fichier.delete(save=False)
    _clore(contribution, moderateur, Contribution.Statut.REJETEE, motif_rejet=motif, fichier="")


def _clore(contribution, moderateur, statut, **champs):
    for champ, valeur in champs.items():
        setattr(contribution, champ, valeur)
    contribution.statut = statut
    contribution.traitee_par = moderateur
    contribution.traitee_le = timezone.now()
    contribution.save()
    transaction.on_commit(lambda: notifier(contribution))


def notifier(contribution):
    send_mail(
        _("Votre contribution a été validée") if contribution.statut == Contribution.Statut.VALIDEE
        else _("Votre contribution n'a pas été retenue"),
        render_to_string("communaute/email_decision_contribution.txt", {"contribution": contribution}),
        None,
        [contribution.utilisateur.email],
        fail_silently=True,
    )
