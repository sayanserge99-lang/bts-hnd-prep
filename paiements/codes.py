"""Codes d'accès prépayés (CDC 3.9) : vendus aux IPES partenaires, activés par leurs étudiants.

Un code activé crée un abonnement (Premium) ; il ne sert qu'une fois, et seulement tant que la convention
de l'établissement est active.
"""

import csv
import io
import secrets
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import Abonnement, CodeAcces

# Sans 0/O ni 1/I : un code se recopie souvent à la main depuis une feuille imprimée.
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
LONGUEUR = 12  # 32^12 ≈ 10^18 : impossible à deviner, d'autant que les essais sont limités
ESSAIS_PAR_HEURE = 10


class CodeRefuse(Exception):
    """Message à montrer à l'étudiant."""


def nouveau_code():
    brut = "".join(secrets.choice(ALPHABET) for _ in range(LONGUEUR))
    return "-".join(brut[i:i + 4] for i in range(0, LONGUEUR, 4))


def normaliser(saisie):
    """« abcd efgh-ijkl » → « ABCD-EFGH-IJKL » ; O et I tapés à la place de 0 et 1 n'existent pas."""
    brut = "".join(caractere for caractere in saisie.upper() if caractere.isalnum())
    return "-".join(brut[i:i + 4] for i in range(0, len(brut), 4))


@transaction.atomic
def generer(partenariat, offre, nombre):
    if not partenariat.est_actif():
        raise ValidationError(_("Un établissement sans convention active ne peut pas recevoir de codes."))
    codes = []
    while len(codes) < nombre:
        try:
            with transaction.atomic():
                codes.append(CodeAcces.objects.create(code=nouveau_code(), offre=offre, partenariat=partenariat))
        except IntegrityError:
            continue  # collision, presque impossible : on retire un code
    return codes


def en_csv(codes):
    sortie = io.StringIO()
    ecrivain = csv.writer(sortie, delimiter=";")
    ecrivain.writerow([_("code"), _("offre"), _("établissement"), _("utilisé le")])
    for code in codes:
        utilise = timezone.localtime(code.date_utilisation).strftime("%d/%m/%Y") if code.date_utilisation else ""
        ecrivain.writerow([code.code, code.offre.nom, code.partenariat.etablissement.nom, utilise])
    return "﻿" + sortie.getvalue()  # BOM : Excel lit alors les accents


def activer(utilisateur, saisie):
    """Active le code pour cet utilisateur et renvoie l'abonnement créé ; lève CodeRefuse sinon."""
    cle = f"essais-code:{utilisateur.pk}"
    if cache.get(cle, 0) >= ESSAIS_PAR_HEURE:
        raise CodeRefuse(_("Trop d'essais. Réessayez dans une heure, ou demandez de l'aide à votre établissement."))
    try:
        return _activer(utilisateur, normaliser(saisie))
    except CodeRefuse:
        cache.set(cle, cache.get(cle, 0) + 1, timeout=60 * 60)
        raise


@transaction.atomic
def _activer(utilisateur, code_saisi):
    # select_for_update : deux étudiants qui tapent le même code en même temps ne l'obtiennent pas tous les deux.
    code = (
        CodeAcces.objects.select_for_update()
        .select_related("offre", "partenariat__etablissement")
        .filter(code=code_saisi)
        .first()
    )
    if code is None:
        raise CodeRefuse(_("Ce code n'existe pas. Vérifiez-le (les lettres O et I n'y figurent jamais)."))
    if code.utilise_par_id:
        raise CodeRefuse(_("Ce code a déjà été utilisé."))
    if not code.partenariat.est_actif():
        raise CodeRefuse(_("Ce code n'est plus valable : la convention de votre établissement a pris fin."))

    profil = getattr(utilisateur, "profil", None)
    if profil is None and code.offre.type == code.offre.Type.SESSION:
        raise CodeRefuse(_("Complétez d'abord votre profil (examen et spécialité)."))
    debut = Abonnement.prochain_jour_libre(utilisateur)
    try:
        fin = code.offre.calculer_fin(profil.examen if profil else None, debut)
    except ValidationError as erreur:
        raise CodeRefuse(erreur.messages[0]) from erreur

    code.utilise_par = utilisateur
    code.date_utilisation = timezone.now()
    code.save(update_fields=["utilise_par", "date_utilisation"])
    abonnement = Abonnement.objects.create(utilisateur=utilisateur, offre=code.offre, debut=debut, fin=fin, code_acces=code)

    # Le code vient de l'établissement : il vaut confirmation, sauf si l'étudiant en a déclaré un autre.
    etablissement = code.partenariat.etablissement
    if profil and profil.etablissement_id in (None, etablissement.pk):
        if profil.etablissement_id is None:
            profil.etablissement = etablissement
            profil.save()  # save() remet la confirmation à zéro quand l'établissement change : on confirme après
        type(profil).objects.filter(pk=profil.pk).update(etablissement_valide_le=timezone.now(), etablissement_valide_par=None)
    return abonnement
