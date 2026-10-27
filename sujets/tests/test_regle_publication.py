"""Règle absolue du CDC (4.2) : aucun sujet publié avant la fin officielle de sa session."""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from communaute.models import DemandeRetrait
from sujets.models import PublicationInterdite, Sujet

pytestmark = pytest.mark.django_db

PUBLIE = Sujet.Statut.PUBLIE
BROUILLON = Sujet.Statut.BROUILLON


def test_publication_refusee_pendant_la_session(creer_sujet, session_en_cours):
    sujet = creer_sujet(session_en_cours)
    sujet.statut = PUBLIE

    with pytest.raises(PublicationInterdite):
        sujet.save()

    sujet.refresh_from_db()
    assert sujet.statut == BROUILLON


def test_creation_directe_en_publie_refusee(creer_sujet, session_en_cours):
    with pytest.raises(PublicationInterdite):
        creer_sujet(session_en_cours, statut=PUBLIE)
    assert not Sujet.objects.exists()


def test_publication_refusee_le_jour_de_fin(creer_sujet, session_en_cours):
    session_en_cours.date_fin_officielle = timezone.localdate()
    session_en_cours.save()
    sujet = creer_sujet(session_en_cours)
    sujet.statut = PUBLIE

    with pytest.raises(PublicationInterdite):
        sujet.save()


def test_publication_autorisee_le_lendemain_de_la_fin(creer_sujet, session_en_cours):
    session_en_cours.date_fin_officielle = timezone.localdate() - timedelta(days=1)
    session_en_cours.save()
    sujet = creer_sujet(session_en_cours)
    sujet.statut = PUBLIE
    sujet.save()

    sujet.refresh_from_db()
    assert sujet.statut == PUBLIE
    assert sujet.date_publication is not None


def test_validation_de_formulaire_signale_le_statut(creer_sujet, session_en_cours):
    sujet = creer_sujet(session_en_cours)
    sujet.statut = PUBLIE

    with pytest.raises(ValidationError) as erreur:
        sujet.full_clean()
    assert "statut" in erreur.value.message_dict


def test_mise_a_jour_groupee_refusee_si_un_seul_sujet_bloque(creer_sujet, session_terminee, session_en_cours):
    autorise = creer_sujet(session_terminee)
    bloque = creer_sujet(session_en_cours)

    with pytest.raises(PublicationInterdite):
        Sujet.objects.filter(pk__in=[autorise.pk, bloque.pk]).update(statut=PUBLIE)

    assert Sujet.objects.filter(statut=PUBLIE).count() == 0


def test_bulk_update_refuse(creer_sujet, session_en_cours):
    sujet = creer_sujet(session_en_cours)
    sujet.statut = PUBLIE

    with pytest.raises(PublicationInterdite):
        Sujet.objects.bulk_update([sujet], ["statut"])


def test_action_admin_ne_publie_que_les_sujets_autorises(admin_client, creer_sujet, session_terminee, session_en_cours):
    autorise = creer_sujet(session_terminee)
    bloque = creer_sujet(session_en_cours)

    reponse = admin_client.post(
        reverse("admin:sujets_sujet_changelist"),
        {"action": "publier", "_selected_action": [autorise.pk, bloque.pk]},
        follow=True,
    )

    assert reponse.status_code == 200
    autorise.refresh_from_db()
    bloque.refresh_from_db()
    assert autorise.statut == PUBLIE
    assert bloque.statut == BROUILLON


def test_le_superutilisateur_ne_peut_pas_forcer_par_le_formulaire(admin_client, creer_sujet, session_en_cours, comptabilite):
    sujet = creer_sujet(session_en_cours)
    sujet.specialites.add(comptabilite)

    reponse = admin_client.post(
        reverse("admin:sujets_sujet_change", args=[sujet.pk]),
        {
            "titre": sujet.titre,
            "session": session_en_cours.pk,
            "matiere": sujet.matiere.pk,
            "specialites": [comptabilite.pk],
            "type_epreuve": sujet.type_epreuve,
            "duree": sujet.duree,
            "source": sujet.source,
            "statut": PUBLIE,
        },
    )

    # Le formulaire est réaffiché avec l'erreur sur le statut, rien n'est enregistré.
    assert "ne peuvent pas être publiés" in reponse.content.decode()
    sujet.refresh_from_db()
    assert sujet.statut == BROUILLON


def test_depublication_toujours_possible(creer_sujet, session_terminee):
    sujet = creer_sujet(session_terminee, statut=PUBLIE)
    sujet.statut = BROUILLON
    sujet.save()

    sujet.refresh_from_db()
    assert sujet.statut == BROUILLON
    assert sujet.date_publication is None


def test_specialite_hors_matiere_refusee(creer_sujet, session_terminee, comptabilite, marketing):
    sujet = creer_sujet(session_terminee)
    sujet.specialites.add(comptabilite)

    with pytest.raises(ValidationError):
        sujet.specialites.add(marketing)


def test_demande_de_retrait_masque_le_sujet(creer_sujet, session_terminee):
    sujet = creer_sujet(session_terminee, statut=PUBLIE)

    DemandeRetrait.objects.create(
        demandeur_nom="Ayant droit", demandeur_email="ayant.droit@example.com", sujet=sujet, motif="Droits"
    )

    sujet.refresh_from_db()
    assert sujet.statut == Sujet.Statut.MASQUE


# --- La date de fin d'une session déjà publiée ne peut pas être repoussée dans le futur -----------------------

def test_repousser_la_fin_d_une_session_publiee_est_refuse(creer_sujet, session_terminee):
    creer_sujet(session_terminee, statut=PUBLIE)
    session_terminee.date_fin_officielle = timezone.localdate() + timedelta(days=10)
    with pytest.raises(ValidationError, match="masquez d'abord ces sujets"):
        session_terminee.save()


def test_repousser_par_mise_a_jour_groupee_est_refuse(creer_sujet, session_terminee):
    creer_sujet(session_terminee, statut=PUBLIE)
    with pytest.raises(ValidationError):
        type(session_terminee).objects.filter(pk=session_terminee.pk).update(date_fin_officielle=timezone.localdate())


def test_le_superutilisateur_ne_peut_pas_repousser_la_fin_dans_l_admin(admin_client, creer_sujet, session_terminee):
    creer_sujet(session_terminee, statut=PUBLIE)
    plus_tard = timezone.localdate() + timedelta(days=10)
    reponse = admin_client.post(reverse("admin:catalogue_session_change", args=[session_terminee.pk]), {
        "examen": session_terminee.examen_id, "annee": session_terminee.annee,
        "date_debut": session_terminee.date_debut.isoformat(), "date_fin_officielle": plus_tard.isoformat(),
    })
    assert "masquez d&#x27;abord ces sujets" in reponse.content.decode()
    session_terminee.refresh_from_db()
    assert session_terminee.date_fin_officielle < timezone.localdate()


def test_repousser_la_fin_reste_possible_sans_sujet_publie(creer_sujet, session_terminee):
    creer_sujet(session_terminee)  # brouillon
    session_terminee.date_fin_officielle = timezone.localdate() + timedelta(days=10)
    session_terminee.save()


def test_un_sujet_n_est_jamais_montre_avant_la_fin_meme_par_un_autre_chemin(creer_sujet, session_terminee):
    """Filet : si la date était changée sans passer par Django (SQL direct), la liste publique l'ignore."""
    from django.db import connection

    sujet = creer_sujet(session_terminee, statut=PUBLIE)
    with connection.cursor() as curseur:
        curseur.execute("UPDATE catalogue_session SET date_fin_officielle = %s WHERE id = %s",
                        [timezone.localdate(), session_terminee.pk])
    assert not Sujet.objects.publies().filter(pk=sujet.pk).exists()


def test_rien_de_la_session_ne_reste_visible_si_la_date_change_par_un_autre_chemin(creer_sujet, session_terminee, compta_generale):
    """Corrigés, questions, examens blancs, discussions et favoris suivent le même filet que publies()."""
    from django.db import connection

    from accounts.models import Utilisateur
    from catalogue.models import Chapitre
    from entrainement.models import ExamenBlanc, Question
    from forum.models import Discussion
    from sujets.models import Corrige, Favori

    sujet = creer_sujet(session_terminee, statut=PUBLIE)
    awa = Utilisateur.objects.create_user(email="awa@example.com", password="Revision-2027")
    Corrige.objects.create(sujet=sujet, statut=Corrige.Statut.VERIFIE, publication=Corrige.Publication.PUBLIE,
                           auteur="M. Test", titulaire_droits="Test", regime_propriete=Corrige.RegimePropriete.PLATEFORME,
                           partie_gratuite="Début", contenu="Suite")
    chapitre = Chapitre.objects.create(matiere=compta_generale, titre="Amortissements")
    Question.objects.create(chapitre=chapitre, type="vrai_faux", enonce="?", sujet=sujet, publiee=True, langue="fr")
    ExamenBlanc.objects.create(titre="Examen", sujet=sujet, duree=60, publie=True)
    Discussion.objects.create(matiere=compta_generale, sujet=sujet, auteur=awa, titre="Question", texte="")
    Favori.objects.create(utilisateur=awa, sujet=sujet)
    visibles = lambda: (Corrige.objects.visibles().count(), Question.objects.visibles().count(),  # noqa: E731
                        ExamenBlanc.objects.visibles().count(), Discussion.objects.visibles().count())
    assert visibles() == (1, 1, 1, 1)

    with connection.cursor() as curseur:
        curseur.execute("UPDATE catalogue_session SET date_fin_officielle = %s WHERE id = %s",
                        [timezone.localdate(), session_terminee.pk])

    assert visibles() == (0, 0, 0, 0)
    assert not awa.favoris.filter(sujet__in=Sujet.objects.publies()).exists()
