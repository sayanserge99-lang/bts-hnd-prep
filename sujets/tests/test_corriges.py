"""Corrigés (CDC 3.3, 10.7) : rendu, visibilité, règle de publication, accès, signalement, retrait."""

from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from accounts.models import Utilisateur
from communaute.models import DemandeRetrait, Signalement
from paiements.models import Abonnement, CodeAcces, Offre
from partenaires.models import Etablissement, Partenariat
from sujets.models import Corrige, PublicationInterdite, Sujet
from sujets.rendu import rendre

pytestmark = pytest.mark.django_db

PUBLIE = Sujet.Statut.PUBLIE


@pytest.fixture
def sujet(creer_sujet, session_terminee):
    return creer_sujet(session_terminee, titre="Comptabilité générale", statut=PUBLIE)


def creer_corrige(sujet, **champs):
    valeurs = {
        "sujet": sujet,
        "statut": Corrige.Statut.VERIFIE,
        "publication": Corrige.Publication.PUBLIE,
        "auteur": "M. Mbarga",
        "titulaire_droits": "BTS-HND Prep",
        "partie_gratuite": "## Exercice 1\n\nDébut visible par tous.",
        "contenu": "## Exercice 2\n\nSuite réservée aux abonnés.",
        **champs,
    }
    return Corrige.objects.create(**valeurs)


def onglet_corrige(client, sujet):
    return client.get(reverse("sujets:detail", args=[sujet.pk]), {"onglet": "corrige"}).content.decode()


# --- Rendu -------------------------------------------------------------------

def test_markdown_tableau_et_formules():
    html = rendre("| Compte | Débit |\n|---|---|\n| 681 | 4 800 000 |\n\nTaux : $t = \\frac{100}{5}$\n\n$$C_n = C_0(1+i)^n$$")

    assert "<table>" in html
    assert "<math" in html and "<mfrac>" in html
    assert 'display="block"' in html


def test_le_code_malveillant_est_retire():
    html = rendre('<script>alert(1)</script><img src=x onerror="alert(1)"> [lien](javascript:alert(1))')

    assert "<script" not in html
    assert "onerror" not in html
    assert "javascript:" not in html


def test_pas_de_script_cache_dans_une_formule():
    # latex2mathml recopie le contenu de \text{...} sans l'échapper : nh3 doit passer après.
    html = rendre("$\\text{<script>alert(1)</script>} x < y$ et $$\\text{<img src=x onerror=alert(1)>}$$")

    assert "<script" not in html and "alert(1)" not in html
    assert "onerror" not in html
    assert "<math" in html and "<mo>&lt;</mo>" in html


def test_une_formule_mal_ecrite_ne_casse_pas_la_page():
    assert "<code>" in rendre("$\\frac{1}{$ et la suite")


def test_un_montant_ne_se_coupe_pas_en_bout_de_ligne():
    html = rendre("| Base | Annuité |\n|---|---|\n| 12 000 000 | 4 800 000 |\n\nEn 2025 et 2026, 3 exercices.")

    assert "12 000 000" in html and "4 800 000" in html
    # Seules les espaces entre chiffres groupés par trois changent.
    assert "2025 et 2026, 3 exercices" in html


def test_un_prix_en_dollars_n_est_pas_une_formule():
    assert "<math" not in rendre("Entre 5 $ et 10 $ par mois.")


# --- Règle de publication et visibilité -------------------------------------

def test_un_corrige_ne_se_publie_pas_avant_la_fin_de_la_session(creer_sujet, session_en_cours):
    brouillon = creer_sujet(session_en_cours)
    with pytest.raises(PublicationInterdite):
        creer_corrige(brouillon)
    corrige = creer_corrige(brouillon, publication=Corrige.Publication.BROUILLON)
    with pytest.raises(PublicationInterdite):
        Corrige.objects.filter(pk=corrige.pk).update(publication=Corrige.Publication.PUBLIE)


def test_seuls_les_corriges_publies_rediges_et_de_sujet_publie_sont_visibles(sujet, creer_sujet, session_terminee):
    visible = creer_corrige(sujet)
    creer_corrige(sujet, publication=Corrige.Publication.BROUILLON)
    creer_corrige(sujet, statut=Corrige.Statut.EN_PREPARATION)
    masque = creer_sujet(session_terminee, titre="Masqué", statut=Sujet.Statut.MASQUE)
    creer_corrige(masque)

    assert list(Corrige.objects.visibles()) == [visible]


def test_le_corrige_verifie_passe_avant_celui_de_la_communaute(sujet):
    communaute = creer_corrige(sujet, statut=Corrige.Statut.COMMUNAUTE)
    verifie = creer_corrige(sujet)
    assert list(sujet.corriges.visibles()) == [verifie, communaute]


# --- Affichage ----------------------------------------------------------------

def test_onglet_corrige(client, sujet):
    creer_corrige(sujet)
    contenu = onglet_corrige(client, sujet)

    assert "Vérifié par un enseignant" in contenu
    assert "M. Mbarga" in contenu
    assert "Début visible par tous" in contenu
    # CDC 10.7 : avertissement et signalement sous chaque corrigé.
    assert "peut contenir des erreurs" in contenu
    assert "Se connecter pour signaler une erreur" in contenu


def test_sans_paiement_ouvert_le_corrige_est_complet_pour_tous(client, sujet):
    creer_corrige(sujet)
    assert "Suite réservée aux abonnés" in onglet_corrige(client, sujet)


def test_paiement_ouvert_la_suite_est_reservee(client, settings, sujet):
    settings.PAIEMENT_ACTIF = True
    creer_corrige(sujet)

    contenu = onglet_corrige(client, sujet)
    assert "Début visible par tous" in contenu
    assert "Suite réservée aux abonnés" not in contenu
    assert "La suite avec le Pass session" in contenu


def test_paiement_ouvert_un_abonne_lit_tout(client, settings, sujet):
    settings.PAIEMENT_ACTIF = True
    corrige = creer_corrige(sujet, fichier=SimpleUploadedFile("c.pdf", b"%PDF-1.4", content_type="application/pdf"))
    abonne = Utilisateur.objects.create_user(email="abonne@example.com", password="Revision-2027")
    offre = Offre.objects.create(nom="Pass", prix=5000, type=Offre.Type.SESSION)
    partenaire = Partenariat.objects.create(
        etablissement=Etablissement.objects.create(nom="IPES", ville="Douala", region="littoral"),
        convention="conventions/c.pdf", date_debut=timezone.localdate() - timedelta(days=1),
        date_fin=timezone.localdate() + timedelta(days=300), taux_partage=10, statut=Partenariat.Statut.ACTIF,
    )
    code = CodeAcces.objects.create(code="ESSAI-1", offre=offre, partenariat=partenaire)
    Abonnement.objects.create(
        utilisateur=abonne, offre=offre, code_acces=code,
        debut=timezone.localdate(), fin=timezone.localdate() + timedelta(days=30),
    )

    assert client.get(reverse("sujets:pdf_corrige", args=[corrige.pk])).status_code == 404
    client.force_login(abonne)
    assert "Suite réservée aux abonnés" in onglet_corrige(client, sujet)
    assert client.get(reverse("sujets:pdf_corrige", args=[corrige.pk])).status_code == 200


def test_le_pdf_d_un_corrige_non_visible_est_introuvable(client, sujet):
    corrige = creer_corrige(
        sujet, publication=Corrige.Publication.BROUILLON,
        fichier=SimpleUploadedFile("c.pdf", b"%PDF-1.4", content_type="application/pdf"),
    )
    assert client.get(reverse("sujets:pdf_corrige", args=[corrige.pk])).status_code == 404


def test_sujet_sans_corrige_ou_en_preparation(client, sujet):
    assert "pas encore de corrigé" in onglet_corrige(client, sujet)
    creer_corrige(sujet, statut=Corrige.Statut.EN_PREPARATION)
    assert "en préparation" in onglet_corrige(client, sujet)


def test_badges_et_filtre_dans_la_liste(client, sujet, creer_sujet, session_terminee):
    creer_corrige(sujet)
    sans = creer_sujet(session_terminee, titre="Sujet sans corrigé", statut=PUBLIE, type_epreuve="pratique")

    def resultats(**filtres):
        return client.get(reverse("sujets:liste"), {"examen": "BTS", **filtres}, headers={"HX-Request": "true"}).content.decode()

    assert "Vérifié par un enseignant" in resultats()
    filtre = resultats(corrige="verifie")
    assert sujet.titre in filtre
    assert sans.titre not in filtre


# --- Signalement et retrait -----------------------------------------------------

def test_signaler_une_erreur(client, sujet):
    corrige = creer_corrige(sujet)
    etudiant = Utilisateur.objects.create_user(email="etudiant@example.com", password="Revision-2027")
    client.force_login(etudiant)

    client.post(reverse("sujets:signaler_corrige", args=[corrige.pk]), {"motif": "court"})
    assert not Signalement.objects.exists()

    reponse = client.post(
        reverse("sujets:signaler_corrige", args=[corrige.pk]), {"motif": "L'annuité de l'année N+1 est fausse."}
    )
    assert reponse.status_code == 302
    assert Signalement.objects.get().corrige == corrige


def test_un_visiteur_ne_peut_pas_signaler(client, sujet):
    corrige = creer_corrige(sujet)
    client.post(reverse("sujets:signaler_corrige", args=[corrige.pk]), {"motif": "Une erreur dans le tableau."})
    assert not Signalement.objects.exists()


def test_demande_de_retrait_d_un_corrige(client, sujet):
    corrige = creer_corrige(sujet)
    client.post(
        f"{reverse('demande_de_retrait')}?corrige={corrige.pk}",
        {"corrige": corrige.pk, "demandeur_nom": "Auteur", "demandeur_email": "auteur@example.com",
         "motif": "Je suis l'auteur de ce corrigé.", "certifie_titulaire": "on"},
    )

    corrige.refresh_from_db()
    assert corrige.publication == Corrige.Publication.MASQUE
    assert "Début visible par tous" not in onglet_corrige(client, sujet)

    DemandeRetrait.objects.get().refuser()
    corrige.refresh_from_db()
    assert corrige.publication == Corrige.Publication.PUBLIE


def test_accepter_un_retrait_vide_tout_le_corrige(sujet):
    corrige = creer_corrige(sujet)
    DemandeRetrait.objects.create(demandeur_nom="A", demandeur_email="a@example.com", corrige=corrige, motif="M").accepter()

    corrige.refresh_from_db()
    assert corrige.partie_gratuite == ""
    assert "Retiré" in corrige.contenu
