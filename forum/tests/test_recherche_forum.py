"""Recherche dans le forum : titres, détails et réponses visibles ; chaque discussion dans la langue de son examen."""

import pytest
from django.urls import reverse

from catalogue.models import Examen, Matiere
from forum.models import Discussion, Reponse
from forum.tests.test_forum import awa, ben, compte, question  # noqa: F401 (fixtures)

pytestmark = pytest.mark.django_db


def chercher(client, texte, **autres):
    return client.get(reverse("forum:recherche"), {"q": texte, **autres}).content.decode()


def test_trouve_par_le_titre_sans_les_accents_et_par_debut_de_mot(client, question):
    page = chercher(client, "annuite degress")
    assert "Annuité dégressive ?" in page and "1 discussion trouvée" in page


def test_trouve_par_une_reponse_mais_pas_par_une_reponse_masquee(client, question, ben):
    Reponse.objects.create(discussion=question, auteur=ben, texte="Multiplie le taux linéaire par le coefficient fiscal.")
    assert "Annuité dégressive ?" in chercher(client, "coefficient fiscal")
    Reponse.objects.create(discussion=question, auteur=ben, texte="Lien vers un site de triche", masquee=True)
    assert "Annuité dégressive ?" not in chercher(client, "triche")


def test_les_discussions_masquees_ne_sortent_pas(client, question):
    Discussion.objects.filter(pk=question.pk).update(masquee=True)
    assert "Annuité dégressive ?" not in chercher(client, "annuité")


def test_tous_les_mots_sont_exiges_et_un_texte_vide_ne_cherche_rien(client, question):
    assert "Aucune discussion ne contient tous ces mots" in chercher(client, "annuité banane")
    page = chercher(client, "")
    assert "trouvée" not in page and "Aucune discussion" not in page


def test_le_hnd_se_cherche_en_anglais(client, question):
    hnd = Examen.objects.create(code="HND", nom="Higher National Diploma", langue="en")
    matiere = Matiere.objects.create(examen=hnd, nom="Financial Accounting")
    Discussion.objects.create(matiere=matiere, auteur=compte("ndi@example.com"), titre="Depreciation of vehicles")
    page = chercher(client, "depreciating")  # racine anglaise : depreciating → depreci
    assert "Depreciation of vehicles" in page and "Annuité" not in page


def test_dans_une_matiere(client, question, compta_generale, bts, awa):
    autre = Matiere.objects.create(examen=bts, nom="Droit")
    Discussion.objects.create(matiere=autre, auteur=awa, titre="Annuité d'un loyer ?")
    assert "2 discussions trouvées" in chercher(client, "annuité")
    page = chercher(client, "annuité", matiere=compta_generale.pk)
    assert "1 discussion trouvée" in page and "Annuité dégressive ?" in page


def test_le_champ_est_sur_l_accueil_et_les_matieres(client, question, compta_generale):
    assert 'action="/forum/recherche/"' in client.get(reverse("forum:accueil")).content.decode()
    page = client.get(reverse("forum:matiere", args=[compta_generale.pk])).content.decode()
    assert f'name="matiere" value="{compta_generale.pk}"' in page
