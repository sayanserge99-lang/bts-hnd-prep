"""Recherche plein texte dans les sujets (CDC 3.2 : mot-clé dans le texte)."""

import io
from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command

from catalogue.models import Examen, Matiere, Session, Specialite, SpecialiteMatiere
from sujets.models import Sujet

pytestmark = pytest.mark.django_db


def titres(resultats):
    return [sujet.titre for sujet in resultats]


@pytest.fixture
def sujet_amortissement(creer_sujet, session_terminee):
    return creer_sujet(
        session_terminee,
        titre="Comptabilité générale",
        texte_extrait="Exercice 2 : calculez l'amortissement dégressif de la machine.",
    )


def test_trouve_un_mot_du_texte_extrait(sujet_amortissement):
    assert titres(Sujet.objects.rechercher("amortissement", "fr")) == ["Comptabilité générale"]


def test_ignore_les_accents(sujet_amortissement):
    assert Sujet.objects.rechercher("degressif", "fr").exists()
    assert Sujet.objects.rechercher("DÉGRESSIF", "fr").exists()


def test_trouve_un_debut_de_mot(sujet_amortissement):
    assert Sujet.objects.rechercher("amortis", "fr").exists()


def test_trouve_par_le_nom_de_la_matiere(creer_sujet, session_terminee):
    creer_sujet(session_terminee, titre="Épreuve de la session 2025")
    assert Sujet.objects.rechercher("comptabilite generale", "fr").exists()


def test_tous_les_mots_sont_exiges(sujet_amortissement):
    assert not Sujet.objects.rechercher("amortissement marketing", "fr").exists()


def test_le_titre_compte_plus_que_le_texte(creer_sujet, session_terminee, sujet_amortissement):
    creer_sujet(session_terminee, titre="Amortissement des immobilisations")

    assert titres(Sujet.objects.rechercher("amortissement", "fr"))[0] == "Amortissement des immobilisations"


def test_les_caracteres_speciaux_ne_cassent_pas_la_requete(sujet_amortissement):
    assert not Sujet.objects.rechercher("& | ! :* ( ' _", "fr").exists()
    assert Sujet.objects.rechercher("amortissement !", "fr").exists()


def test_l_index_suit_les_modifications(sujet_amortissement):
    sujet_amortissement.texte_extrait = "Analyse du bilan fonctionnel."
    sujet_amortissement.save()

    assert not Sujet.objects.rechercher("amortissement", "fr").exists()
    assert Sujet.objects.rechercher("bilan", "fr").exists()


def test_recherche_en_anglais_pour_le_hnd():
    hnd = Examen.objects.create(code=Examen.Code.HND, nom="Higher National Diploma", langue="en")
    session = Session.objects.create(
        examen=hnd, annee=2025, date_debut=date(2025, 5, 5), date_fin_officielle=date(2025, 6, 20)
    )
    accountancy = Specialite.objects.create(examen=hnd, code="ACC", nom="Accountancy", filiere="commerciale")
    matiere = Matiere.objects.create(examen=hnd, nom="Financial Accounting")
    SpecialiteMatiere.objects.create(specialite=accountancy, matiere=matiere, coefficient=4)
    Sujet.objects.create(
        titre="Financial Accounting",
        session=session,
        matiere=matiere,
        type_epreuve=Sujet.TypeEpreuve.ECRITE,
        duree=180,
        fichier=SimpleUploadedFile("paper.pdf", b"%PDF-1.4", content_type="application/pdf"),
        source="MINESUP, HND session 2025",
        texte_extrait="Question 3: compute the depreciation charges for the year.",
    )

    # « depreciating » et « depreciation » ont la même racine en anglais.
    assert Sujet.objects.rechercher("depreciating", "en").exists()


def test_la_commande_de_reindexation_rattrape_les_operations_groupees(sujet_amortissement):
    Sujet.objects.filter(pk=sujet_amortissement.pk).update(texte_extrait="Seuil de rentabilité.", recherche=None)
    assert not Sujet.objects.rechercher("rentabilite", "fr").exists()

    call_command("reindexer_recherche", stdout=io.StringIO())

    assert Sujet.objects.rechercher("rentabilite", "fr").exists()
