"""Spécialités équivalentes BTS ↔ HND (CDC 3.10, maquette de l'accueil)."""

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from catalogue.models import Examen, Specialite

pytestmark = pytest.mark.django_db


def section_specialites(page, titre="Spécialités disponibles"):
    """La section des cartes de spécialités (la liste déroulante du haut contient aussi les noms)."""
    return page.split(titre)[1].split("</section>")[0]


@pytest.fixture
def hnd():
    return Examen.objects.create(code="HND", nom="Higher National Diploma", langue="en")


@pytest.fixture
def accountancy(hnd):
    return Specialite.objects.create(examen=hnd, code="ACC", nom="Accountancy", filiere="commerciale")


def test_le_lien_est_symetrique_et_unique(comptabilite, marketing, accountancy):
    comptabilite.apparier(accountancy)
    accountancy.refresh_from_db()
    assert comptabilite.equivalent == accountancy and accountancy.equivalent == comptabilite
    # Accountancy passe à Marketing : Comptabilité n'a plus d'équivalente.
    marketing.apparier(accountancy)
    comptabilite.refresh_from_db()
    accountancy.refresh_from_db()
    assert comptabilite.equivalent is None and accountancy.equivalent == marketing
    marketing.apparier(None)
    accountancy.refresh_from_db()
    assert accountancy.equivalent is None


def test_l_equivalente_est_de_l_autre_examen(comptabilite, marketing):
    with pytest.raises(ValidationError):
        comptabilite.apparier(marketing)
    comptabilite.equivalent = marketing
    with pytest.raises(ValidationError):
        comptabilite.full_clean()


def test_l_accueil_montre_les_paires_comme_la_maquette(client, comptabilite, accountancy):
    comptabilite.apparier(accountancy)
    section = section_specialites(client.get(reverse("accueil")).content.decode())
    carte = section.split("Comptabilité et gestion des entreprises")[1].split("</div>")[0]
    assert "HND · Accountancy" in carte and "?examen=HND&specialite=ACC" in carte
    assert section.count(">Accountancy<") == 0  # pas de carte en double pour la spécialité appariée


def test_en_anglais_le_hnd_d_abord(client, comptabilite, accountancy):
    comptabilite.apparier(accountancy)
    client.cookies["django_language"] = "en"
    section = section_specialites(client.get(reverse("accueil")).content.decode(), "Available specialties")
    carte = section.split(">Accountancy<")[1].split("</div>")[0]
    assert "BTS · Comptabilité et gestion des entreprises" in carte


def test_l_admin_apparie_des_deux_cotes(admin_client, comptabilite, accountancy):
    from django.forms.models import model_to_dict

    donnees = {**{k: v for k, v in model_to_dict(comptabilite).items() if v is not None and k != "matieres"},
               "nom_fr": comptabilite.nom, "examen": comptabilite.examen_id, "equivalent": accountancy.pk,
               "specialitematiere_set-TOTAL_FORMS": 0, "specialitematiere_set-INITIAL_FORMS": 0}
    reponse = admin_client.post(reverse("admin:catalogue_specialite_change", args=[comptabilite.pk]), donnees)
    assert reponse.status_code == 302, reponse.content.decode()[:2000]
    accountancy.refresh_from_db()
    assert accountancy.equivalent == comptabilite
