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
