"""Import de sujets en lot : tableau CSV + PDF ou photos, dans un ZIP (admin) ou un dossier (commande)."""

import io
import zipfile

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from pypdf import PdfReader

from accounts.models import AffectationModerateur, Utilisateur
from catalogue.management.commands.donnees_demo import pdf_demo
from catalogue.models import Matiere, SpecialiteMatiere
from sujets.importation import Importateur, ImportImpossible, SourceDossier, SourceZip, modele_csv, tableau_du_zip
from sujets.models import Sujet

pytestmark = pytest.mark.django_db

ENTETE = "fichier;examen;annee;matiere;specialites;titre;type;duree;source;bareme"
PDF = pdf_demo("Comptabilité générale", 2025)


def png():
    from PIL import Image

    tampon = io.BytesIO()
    Image.new("RGB", (600, 850), "white").save(tampon, "PNG")
    return tampon.getvalue()


def lot(lignes, fichiers=None, encodage="utf-8", entete=ENTETE):
    """ZIP en mémoire : sujets.csv + fichiers."""
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as archive:
        archive.writestr("sujets.csv", "\n".join([entete, *lignes]).encode(encodage))
        for nom, contenu in (fichiers or {"compta.pdf": PDF}).items():
            archive.writestr(nom, contenu)
    tampon.seek(0)
    return tampon


def importer(tampon, simulation=False, utilisateur=None):
    source = SourceZip(tampon)
    return Importateur(utilisateur).importer(source, tableau_du_zip(source), simulation=simulation)


LIGNE = "compta.pdf;BTS;2025;Comptabilité générale;CGE;;ecrite;240;MINESUP, BTS session 2025;"


@pytest.fixture
def catalogue(session_terminee, compta_generale, comptabilite):
    return session_terminee


def test_la_simulation_n_enregistre_rien(catalogue):
    rapport = importer(lot([LIGNE]), simulation=True)

    assert [ligne.statut for ligne in rapport] == ["pret"]
    assert not Sujet.objects.exists()


def test_l_import_cree_un_sujet_en_brouillon(catalogue, comptabilite):
    rapport = importer(lot([LIGNE]))

    assert rapport[0].statut == "importe"
    sujet = Sujet.objects.get(pk=rapport[0].sujet_id)
    # La session 2025 est terminée, et pourtant le sujet n'est pas publié : c'est une décision à part.
    assert sujet.statut == Sujet.Statut.BROUILLON
    assert sujet.titre == "Comptabilité générale"
    assert list(sujet.specialites.all()) == [comptabilite]
    assert sujet.duree == 240
    assert sujet.fichier.read().startswith(b"%PDF")


def test_specialites_vides_toutes_celles_de_la_matiere(catalogue, compta_generale, comptabilite, marketing):
    SpecialiteMatiere.objects.create(specialite=marketing, matiere=compta_generale, coefficient=2)
    ligne = LIGNE.replace(";CGE;", ";;")

    sujet = Sujet.objects.get(pk=importer(lot([ligne]))[0].sujet_id)

    assert set(sujet.specialites.all()) == {comptabilite, marketing}


def test_plusieurs_photos_font_un_pdf_de_plusieurs_pages(catalogue):
    ligne = LIGNE.replace("compta.pdf", "page1.png|page2.png")
    rapport = importer(lot([ligne], {"page1.png": png(), "page2.png": png()}))

    sujet = Sujet.objects.get(pk=rapport[0].sujet_id)
    assert len(PdfReader(sujet.fichier.open("rb")).pages) == 2


@pytest.mark.parametrize(
    "ligne, motif",
    [
        (LIGNE.replace(";2025;", ";2019;"), "session BTS 2019 absente"),
        (LIGNE.replace("Comptabilité générale", "Compta generale"), "matière inconnue"),
        (LIGNE.replace(";CGE;", ";MCV;"), "non rattachée"),
        (LIGNE.replace("compta.pdf", "absent.pdf"), "absent du lot"),
        (LIGNE.replace(";240;", ";4h;"), "durée invalide"),
        (LIGNE.replace(";ecrite;", ";orale;"), "type d'épreuve invalide"),
        (LIGNE.replace("MINESUP, BTS session 2025", ""), "source obligatoire"),
        (LIGNE.replace(";BTS;", ";BAC;"), "examen inconnu"),
    ],
)
def test_une_ligne_invalide_est_refusee_avec_son_motif(catalogue, marketing, ligne, motif):
    rapport = importer(lot([ligne]))

    assert rapport[0].statut == "erreur"
    assert motif in rapport[0].message
    assert not Sujet.objects.exists()


def test_un_faux_pdf_est_refuse(catalogue):
    rapport = importer(lot([LIGNE], {"compta.pdf": b"<html>pas un pdf</html>"}))
    assert rapport[0].statut == "erreur"


def test_les_bonnes_lignes_passent_meme_si_d_autres_sont_fausses(catalogue):
    rapport = importer(lot([LIGNE, LIGNE.replace(";2025;", ";2019;")]))

    assert [ligne.statut for ligne in rapport] == ["importe", "erreur"]
    assert [ligne.numero for ligne in rapport] == [2, 3]


def test_les_doublons_sont_ignores(catalogue):
    importer(lot([LIGNE]))

    # Déjà en base, puis deux fois dans le même tableau.
    assert importer(lot([LIGNE]))[0].statut == "doublon"
    autre = LIGNE.replace(";ecrite;", ";pratique;")
    assert [ligne.statut for ligne in importer(lot([autre, autre]))] == ["importe", "doublon"]
    assert Sujet.objects.count() == 2


def test_tableau_excel_francais_en_windows_1252(catalogue):
    rapport = importer(lot([LIGNE], encodage="cp1252"))
    assert rapport[0].statut == "importe"


def test_entetes_avec_accents_et_majuscules(catalogue):
    entete = "Fichier;Examen;Année;Matière;Spécialités;Titre;Type;Durée;Source;Barème"
    assert importer(lot([LIGNE], entete=entete))[0].statut == "importe"


def test_colonnes_obligatoires_manquantes(catalogue):
    with pytest.raises(ImportImpossible):
        importer(lot(["compta.pdf;BTS"], entete="fichier;examen"))


def test_zip_sans_tableau(catalogue):
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as archive:
        archive.writestr("compta.pdf", PDF)
    tampon.seek(0)
    with pytest.raises(ImportImpossible):
        importer(tampon)


def test_fichier_trop_volumineux(catalogue, settings):
    # Plus grand que le tableau (environ 150 octets), plus petit que le PDF.
    settings.IMPORT_TAILLE_MAX_FICHIER = 300
    rapport = importer(lot([LIGNE]))
    assert rapport[0].statut == "erreur"
    assert "trop volumineux" in rapport[0].message


def test_tableau_trop_volumineux(catalogue, settings):
    settings.IMPORT_TAILLE_MAX_FICHIER = 50
    with pytest.raises(ImportImpossible):
        importer(lot([LIGNE]))


def test_un_moderateur_n_importe_que_dans_ses_matieres(catalogue, bts, compta_generale, marketing):
    autre = Matiere.objects.create(examen=bts, nom="Marketing fondamental")
    SpecialiteMatiere.objects.create(specialite=marketing, matiere=autre, coefficient=4)
    moderateur = Utilisateur.objects.create_user(email="mod@example.com", password="Moderation-2027")
    moderateur.groups.add(Group.objects.get(name="Modérateur"))
    AffectationModerateur.objects.create(moderateur=moderateur, matiere=compta_generale)
    lignes = [LIGNE, LIGNE.replace("Comptabilité générale", "Marketing fondamental").replace(";CGE;", ";MCV;")]

    rapport = importer(lot(lignes), utilisateur=moderateur)

    assert [ligne.statut for ligne in rapport] == ["importe", "erreur"]
    assert "pas attribuée" in rapport[1].message


def test_modele_de_tableau():
    contenu = modele_csv()
    assert contenu.startswith("﻿" + ENTETE + ";fourni_par")


def test_colonne_fourni_par(catalogue):
    from partenaires.models import Etablissement

    iai = Etablissement.objects.create(nom="IAI-Cameroun")
    entete = ENTETE + ";fourni_par"
    rapport = importer(lot([LIGNE + ";iai-cameroun"], entete=entete))
    assert Sujet.objects.get(pk=rapport[0].sujet_id).fourni_par == iai

    inconnu = importer(lot([LIGNE.replace("compta.pdf", "autre.pdf") + ";Inconnu"], {"autre.pdf": PDF}, entete=entete))
    assert inconnu[0].statut == "erreur" and "établissement inconnu" in inconnu[0].message


def test_page_d_import_de_l_admin(admin_client, catalogue):
    liste = admin_client.get(reverse("admin:sujets_sujet_changelist")).content.decode()
    assert reverse("admin:sujets_sujet_importer") in liste

    simulation = admin_client.post(
        reverse("admin:sujets_sujet_importer"),
        {"lot": SimpleUploadedFile("lot.zip", lot([LIGNE]).getvalue()), "simulation": "on"},
    )
    assert "Prêt" in simulation.content.decode()
    assert not Sujet.objects.exists()

    admin_client.post(reverse("admin:sujets_sujet_importer"), {"lot": SimpleUploadedFile("lot.zip", lot([LIGNE]).getvalue())})
    assert Sujet.objects.count() == 1

    modele = admin_client.get(reverse("admin:sujets_sujet_modele_import"))
    assert modele["Content-Disposition"] == 'attachment; filename="sujets.csv"'


def test_un_zip_invalide_est_signale(admin_client, catalogue):
    reponse = admin_client.post(
        reverse("admin:sujets_sujet_importer"), {"lot": SimpleUploadedFile("lot.zip", b"pas un zip")}
    )
    assert "pas un ZIP valide" in reponse.content.decode()


def test_commande_depuis_un_dossier(catalogue, tmp_path):
    (tmp_path / "sujets.csv").write_text("\n".join([ENTETE, LIGNE]), encoding="utf-8")
    (tmp_path / "compta.pdf").write_bytes(PDF)

    call_command("importer_sujets", str(tmp_path), stdout=io.StringIO())
    assert not Sujet.objects.exists()

    call_command("importer_sujets", str(tmp_path), "--appliquer", stdout=io.StringIO())
    assert Sujet.objects.count() == 1
    assert SourceDossier(tmp_path).noms
