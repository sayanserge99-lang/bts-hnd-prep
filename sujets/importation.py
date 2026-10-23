"""Import de sujets en lot : un tableau (CSV) et les fichiers (PDF ou photos), dans un ZIP ou un dossier.

Les sujets importés sont toujours en brouillon : la publication passe ensuite par l'action « Publier »,
donc par la règle de publication (CDC 4.2).
"""

import csv
import io
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext as _

from accounts.moderation import est_limite_a_ses_matieres, matieres_de
from catalogue.models import Examen, Matiere, Session
from partenaires.models import Etablissement

from .models import Sujet

NOM_TABLEAU = "sujets.csv"
COLONNES = ["fichier", "examen", "annee", "matiere", "specialites", "titre", "type", "duree", "source", "bareme", "fourni_par"]
COLONNES_OBLIGATOIRES = {"fichier", "examen", "annee", "matiere", "duree", "source"}
EXTENSIONS_IMAGES = {".jpg", ".jpeg", ".png"}
EXEMPLE = {
    "fichier": "BTS-2025-compta.pdf",
    "examen": "BTS",
    "annee": "2025",
    "matiere": "Comptabilité générale",
    "specialites": "CGE,BF",
    "titre": "",
    "type": "ecrite",
    "duree": "240",
    "source": "MINESUP, BTS session 2025",
    "bareme": "",
    "fourni_par": "",
}


class ImportImpossible(Exception):
    """Le lot entier est inutilisable (pas de tableau, ZIP illisible, colonnes manquantes)."""


class Doublon(ValueError):
    """La ligne décrit un sujet déjà présent (en base ou plus haut dans le tableau)."""


@dataclass
class Ligne:
    numero: int
    fichier: str
    statut: str  # "pret", "importe", "erreur", "doublon"
    message: str = ""
    sujet_id: int | None = None


def modele_csv():
    """Tableau vide avec une ligne d'exemple, à ouvrir dans Excel."""
    sortie = io.StringIO()
    ecrivain = csv.DictWriter(sortie, fieldnames=COLONNES, delimiter=";")
    ecrivain.writeheader()
    ecrivain.writerow(EXEMPLE)
    # BOM : Excel reconnaît alors l'UTF-8 et affiche correctement les accents.
    return "﻿" + sortie.getvalue()


def _normaliser(texte):
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return sans_accents.strip().lower()


def _decoder(contenu):
    # Excel en français enregistre souvent en Windows-1252.
    for encodage in ("utf-8-sig", "cp1252"):
        try:
            return contenu.decode(encodage)
        except UnicodeDecodeError:
            continue
    raise ImportImpossible(_("Le tableau n'est ni en UTF-8 ni en Windows-1252."))


def lire_tableau(contenu):
    texte = _decoder(contenu)
    try:
        separateur = csv.Sniffer().sniff(texte.splitlines()[0], delimiters=";,\t").delimiter
    except (csv.Error, IndexError):
        separateur = ";"
    lecteur = csv.DictReader(io.StringIO(texte), delimiter=separateur)
    entetes = {_normaliser(nom): nom for nom in (lecteur.fieldnames or [])}
    manquantes = COLONNES_OBLIGATOIRES - entetes.keys()
    if manquantes:
        raise ImportImpossible(_("Colonnes manquantes dans le tableau : %(colonnes)s.") % {"colonnes": ", ".join(sorted(manquantes))})
    return [
        {colonne: (rangee.get(entetes[colonne]) or "").strip() if colonne in entetes else "" for colonne in COLONNES}
        for rangee in lecteur
    ]


class SourceZip:
    """Fichiers d'un ZIP envoyé depuis l'admin, lus en mémoire (jamais extraits sur le disque)."""

    def __init__(self, fichier):
        try:
            self.archive = zipfile.ZipFile(fichier)
        except zipfile.BadZipFile as erreur:
            raise ImportImpossible(_("Le fichier envoyé n'est pas un ZIP valide.")) from erreur
        total = sum(info.file_size for info in self.archive.infolist())
        if total > settings.IMPORT_TAILLE_MAX_TOTALE:
            raise ImportImpossible(_("Le ZIP décompressé dépasse la taille autorisée."))
        self.noms = [nom for nom in self.archive.namelist() if not nom.endswith("/")]

    def lire(self, nom):
        info = self.archive.getinfo(nom)
        if info.file_size > settings.IMPORT_TAILLE_MAX_FICHIER:
            raise ValueError(_("fichier trop volumineux"))
        return self.archive.read(nom)


class SourceDossier:
    """Fichiers d'un dossier du serveur (commande importer_sujets)."""

    def __init__(self, dossier):
        self.racine = Path(dossier)
        self.noms = [str(chemin.relative_to(self.racine)).replace("\\", "/") for chemin in self.racine.rglob("*") if chemin.is_file()]

    def lire(self, nom):
        return (self.racine / nom).read_bytes()


def _trouver(source, nom):
    """Le tableau peut donner un chemin complet ou seulement le nom du fichier."""
    if nom in source.noms:
        return nom
    candidats = [chemin for chemin in source.noms if chemin.rsplit("/", 1)[-1].lower() == nom.lower()]
    if len(candidats) == 1:
        return candidats[0]
    if len(candidats) > 1:
        raise ValueError(_("plusieurs fichiers portent ce nom dans le lot"))
    raise ValueError(_("fichier absent du lot"))


def _en_pdf(source, noms):
    """Un PDF tel quel, ou des photos (une par page, dans l'ordre du tableau) assemblées en un PDF."""
    if len(noms) == 1 and noms[0].lower().endswith(".pdf"):
        contenu = source.lire(_trouver(source, noms[0]))
        if not contenu.startswith(b"%PDF"):
            raise ValueError(_("ce fichier n'est pas un PDF"))
        return contenu
    import img2pdf  # installé avec OCRmyPDF

    if not all(Path(nom).suffix.lower() in EXTENSIONS_IMAGES for nom in noms):
        raise ValueError(_("plusieurs fichiers : uniquement des photos JPG ou PNG"))
    try:
        return img2pdf.convert([source.lire(_trouver(source, nom)) for nom in noms])
    except (img2pdf.ImageOpenError, ValueError) as erreur:
        raise ValueError(_("photo illisible : %(erreur)s") % {"erreur": erreur}) from erreur


class Importateur:
    def __init__(self, utilisateur=None):
        self.utilisateur = utilisateur
        self.limite = utilisateur is not None and est_limite_a_ses_matieres(utilisateur)
        self.examens = {examen.code: examen for examen in Examen.objects.all()}

    def analyser(self, rangee, deja_vus):
        """Vérifie une ligne ; renvoie les valeurs du futur sujet ou lève ValueError avec le motif."""
        examen = self.examens.get(rangee["examen"].upper())
        if examen is None:
            raise ValueError(_("examen inconnu « %(examen)s » (BTS ou HND)") % {"examen": rangee["examen"]})
        if not rangee["annee"].isdigit():
            raise ValueError(_("année invalide « %(annee)s »") % {"annee": rangee["annee"]})
        session = Session.objects.filter(examen=examen, annee=int(rangee["annee"])).first()
        if session is None:
            raise ValueError(
                _("session %(examen)s %(annee)s absente : créez-la d'abord avec sa date de fin officielle")
                % {"examen": examen.code, "annee": rangee["annee"]}
            )
        matiere = Matiere.objects.filter(Q(nom_fr__iexact=rangee["matiere"]) | Q(nom_en__iexact=rangee["matiere"]), examen=examen).first()
        if matiere is None:
            raise ValueError(_("matière inconnue « %(matiere)s » pour le %(examen)s") % {"matiere": rangee["matiere"], "examen": examen.code})
        if self.limite and not matieres_de(self.utilisateur).filter(pk=matiere.pk).exists():
            raise ValueError(_("cette matière ne vous est pas attribuée"))

        possibles = {specialite.code.upper(): specialite for specialite in matiere.specialites.all()}
        codes = [code.strip().upper() for code in rangee["specialites"].split(",") if code.strip()]
        inconnus = [code for code in codes if code not in possibles]
        if inconnus:
            raise ValueError(_("spécialité(s) non rattachée(s) à cette matière : %(codes)s") % {"codes": ", ".join(inconnus)})
        specialites = [possibles[code] for code in codes] or list(possibles.values())

        type_epreuve = rangee["type"].lower() or Sujet.TypeEpreuve.ECRITE
        if type_epreuve not in Sujet.TypeEpreuve.values:
            raise ValueError(_("type d'épreuve invalide « %(type)s » (ecrite ou pratique)") % {"type": rangee["type"]})
        if not rangee["duree"].isdigit() or int(rangee["duree"]) == 0:
            raise ValueError(_("durée invalide « %(duree)s » (en minutes)") % {"duree": rangee["duree"]})
        if not rangee["source"]:
            raise ValueError(_("source obligatoire (CDC 10.1)"))
        fourni_par = None
        if rangee["fourni_par"]:
            fourni_par = Etablissement.objects.filter(nom__iexact=rangee["fourni_par"]).first()
            if fourni_par is None:
                raise ValueError(_("établissement inconnu « %(nom)s » : ajoutez-le d'abord dans l'admin") % {"nom": rangee["fourni_par"]})

        # CDC 3.7 : même session, même matière, même type d'épreuve = doublon probable.
        cle = (session.pk, matiere.pk, type_epreuve)
        if cle in deja_vus or Sujet.objects.filter(session=session, matiere=matiere, type_epreuve=type_epreuve).exists():
            raise Doublon(_("un sujet existe déjà pour cette session, cette matière et ce type d'épreuve"))
        deja_vus.add(cle)

        return {
            "titre": rangee["titre"] or matiere.nom,
            "session": session,
            "matiere": matiere,
            "specialites": specialites,
            "type_epreuve": type_epreuve,
            "duree": int(rangee["duree"]),
            "source": rangee["source"],
            "bareme": rangee["bareme"],
            "fourni_par": fourni_par,
        }

    def importer(self, source, contenu_tableau, simulation=True):
        rangees = lire_tableau(contenu_tableau)
        if not rangees:
            raise ImportImpossible(_("Le tableau ne contient aucune ligne."))
        rapport, deja_vus = [], set()
        # Ligne 1 = en-têtes : la première ligne de données est la ligne 2, comme dans Excel.
        for numero, rangee in enumerate(rangees, start=2):
            noms = [nom.strip() for nom in rangee["fichier"].split("|") if nom.strip()]
            ligne = Ligne(numero, rangee["fichier"], "pret")
            try:
                if not noms:
                    raise ValueError(_("colonne « fichier » vide"))
                valeurs = self.analyser(rangee, deja_vus)
                pdf = _en_pdf(source, noms)
            except Doublon as doublon:
                ligne.statut, ligne.message = "doublon", str(doublon)
            except ValueError as erreur:
                ligne.statut, ligne.message = "erreur", str(erreur)
            else:
                if not simulation:
                    ligne.sujet_id = self._creer(valeurs, pdf, noms[0])
                    ligne.statut = "importe"
            rapport.append(ligne)
        return rapport

    @transaction.atomic
    def _creer(self, valeurs, pdf, nom):
        specialites = valeurs.pop("specialites")
        # Toujours en brouillon : la publication reste une décision (et un contrôle) à part.
        sujet = Sujet(statut=Sujet.Statut.BROUILLON, **valeurs)
        sujet.fichier.save(f"{Path(nom).stem}.pdf", ContentFile(pdf), save=False)
        sujet.save()
        sujet.specialites.set(specialites)
        return sujet.pk


def tableau_du_zip(source):
    noms = [nom for nom in source.noms if nom.rsplit("/", 1)[-1].lower() == NOM_TABLEAU]
    if len(noms) != 1:
        raise ImportImpossible(_("Le ZIP doit contenir un (et un seul) fichier %(nom)s.") % {"nom": NOM_TABLEAU})
    try:
        return source.lire(noms[0])
    except ValueError as erreur:
        raise ImportImpossible(f"{NOM_TABLEAU} : {erreur}") from erreur
