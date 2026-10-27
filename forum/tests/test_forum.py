"""Forum (CDC 3.7) : questions-réponses par matière, modéré."""

import pytest
from django.contrib.auth.models import Group
from django.core import mail
from django.urls import reverse

from accounts.models import AffectationModerateur, ProfilEtude, Utilisateur
from catalogue.models import Matiere
from forum.models import Discussion, Reponse, SignalementForum
from sujets.models import Sujet

pytestmark = pytest.mark.django_db


def compte(email, specialite=None, **champs):
    utilisateur = Utilisateur.objects.create_user(email=email, password="Forum-Secret-2027", first_name=email.split("@")[0], **champs)
    if specialite:
        ProfilEtude.objects.create(utilisateur=utilisateur, examen=specialite.examen, specialite=specialite)
    return utilisateur


@pytest.fixture
def awa(comptabilite):
    return compte("awa@example.com", comptabilite)


@pytest.fixture
def ben(comptabilite):
    return compte("ben@example.com", comptabilite)


@pytest.fixture
def question(awa, compta_generale):
    return Discussion.objects.create(matiere=compta_generale, auteur=awa, titre="Annuité dégressive ?", texte="Comment la calculer ?")


# --- Lecture et écriture ---------------------------------------------------------------------------------

def test_lecture_ouverte_ecriture_reservee(client, question, compta_generale):
    assert "Annuité dégressive ?" in client.get(reverse("forum:accueil")).content.decode()
    assert "Annuité dégressive ?" in client.get(reverse("forum:matiere", args=[compta_generale.pk])).content.decode()
    page = client.get(reverse("forum:discussion", args=[question.pk])).content.decode()
    assert "Comment la calculer ?" in page and "Se connecter pour répondre" in page

    assert client.get(reverse("forum:nouvelle", args=[compta_generale.pk])).status_code == 302
    client.post(reverse("forum:discussion", args=[question.pk]), {"texte": "Anonyme"})
    assert not Reponse.objects.exists()


def test_poser_une_question_sur_un_sujet(client, awa, compta_generale, creer_sujet, session_terminee):
    sujet = creer_sujet(session_terminee, statut=Sujet.Statut.PUBLIE)
    client.force_login(awa)
    assert "Posez-la au forum" in client.get(reverse("sujets:detail", args=[sujet.pk])).content.decode()

    reponse = client.post(reverse("forum:nouvelle", args=[compta_generale.pk]), {
        "titre": "Exercice 2 du sujet 2025", "texte": "Je bloque sur la question b.", "sujet": sujet.pk,
    })
    discussion = Discussion.objects.get()
    assert reponse.url == reverse("forum:discussion", args=[discussion.pk])
    assert discussion.sujet == sujet and discussion.auteur == awa
    assert "1 question sur ce sujet" in client.get(reverse("sujets:detail", args=[sujet.pk])).content.decode()


def test_pas_de_question_rattachee_a_un_sujet_non_publie(client, awa, compta_generale, creer_sujet, session_en_cours, bts):
    client.force_login(awa)
    brouillon = creer_sujet(session_en_cours)
    url = reverse("forum:nouvelle", args=[compta_generale.pk])
    assert client.get(url, {"sujet": brouillon.pk}).status_code == 404
    autre = Matiere.objects.create(examen=bts, nom="Droit")
    assert client.get(reverse("forum:nouvelle", args=[autre.pk]), {"sujet": brouillon.pk}).status_code == 404


def test_repondre_previent_l_auteur(client, ben, awa, question):
    client.force_login(ben)
    reponse = client.post(reverse("forum:discussion", args=[question.pk]), {"texte": "Taux × valeur résiduelle."})
    message = Reponse.objects.get()
    assert reponse.url.endswith(f"#reponse-{message.pk}")
    question.refresh_from_db()
    assert question.derniere_activite >= message.cree_le
    assert mail.outbox[0].to == [awa.email]

    # Répondre à sa propre question ne s'envoie pas d'e-mail.
    client.force_login(awa)
    client.post(reverse("forum:discussion", args=[question.pk]), {"texte": "Merci !"})
    assert len(mail.outbox) == 1


def test_le_texte_est_nettoye(client, ben, question):
    client.force_login(ben)
    client.post(reverse("forum:discussion", args=[question.pk]), {
        "texte": "<script>alert(1)</script> ![x](http://pistage.example/x.png) [lien](http://pub.example) $\\frac{a}{b}$",
    })
    page = client.get(reverse("forum:discussion", args=[question.pk])).content.decode()
    assert "<script>alert" not in page and "pistage.example" not in page
    assert 'rel="nofollow ugc noopener noreferrer"' in page and "<mfrac>" in page


def test_seul_l_auteur_choisit_la_reponse_qui_l_a_aide(client, awa, ben, question):
    reponse = Reponse.objects.create(discussion=question, auteur=ben, texte="Voici.")
    url = reverse("forum:accepter", args=[reponse.pk])
    client.force_login(ben)
    assert client.post(url).status_code == 404

    client.force_login(awa)
    client.post(url)
    question.refresh_from_db()
    assert question.reponse_acceptee == reponse
    assert "A aidé l'auteur de la question" in client.get(reverse("forum:discussion", args=[question.pk])).content.decode()
    client.post(url)  # second clic : retiré
    question.refresh_from_db()
    assert question.reponse_acceptee is None


def test_une_question_courte_sans_details(client, awa, compta_generale):
    client.force_login(awa)
    page = client.get(reverse("forum:nouvelle", args=[compta_generale.pk])).content.decode()
    assert "Détails (facultatif)" in page
    client.post(reverse("forum:nouvelle", args=[compta_generale.pk]), {"titre": "Comment définit-on un algorithme ?", "texte": ""})
    discussion = Discussion.objects.get()
    assert client.get(reverse("forum:discussion", args=[discussion.pk])).status_code == 200


def test_limite_quotidienne(client, settings, awa, compta_generale):
    settings.FORUM_MESSAGES_PAR_JOUR = 1
    client.force_login(awa)
    url = reverse("forum:nouvelle", args=[compta_generale.pk])
    client.post(url, {"titre": "Première", "texte": "Texte"})
    client.post(url, {"titre": "Deuxième", "texte": "Texte"})
    assert Discussion.objects.count() == 1


def test_forum_ferme(client, settings, question):
    settings.FONCTIONNALITES = {**settings.FONCTIONNALITES, "forum": False}
    assert client.get(reverse("forum:accueil")).status_code == 404
    assert client.get(reverse("forum:discussion", args=[question.pk])).status_code == 404


# --- Modération ---------------------------------------------------------------------------------------------

def test_trois_signalements_masquent_le_message(client, settings, comptabilite, question, ben):
    reponse = Reponse.objects.create(discussion=question, auteur=ben, texte="Publicité !")
    url = reverse("forum:signaler", args=["reponse", reponse.pk])
    temoins = [compte(f"t{numero}@example.com", comptabilite) for numero in range(3)]

    client.force_login(temoins[0])
    client.post(url, {"motif": "Publicité"})
    client.post(url, {"motif": "Publicité encore"})  # le même compte ne compte qu'une fois
    assert SignalementForum.objects.count() == 1
    client.force_login(temoins[1])
    client.post(url, {"motif": "Publicité"})
    reponse.refresh_from_db()
    assert not reponse.masquee

    client.force_login(temoins[2])
    client.post(url, {"motif": "Publicité"})
    reponse.refresh_from_db()
    assert reponse.masquee
    assert "Publicité !" not in client.get(reverse("forum:discussion", args=[question.pk])).content.decode()


def test_une_discussion_masquee_disparait(client, comptabilite, question):
    temoins = [compte(f"t{numero}@example.com", comptabilite) for numero in range(3)]
    for temoin in temoins:
        client.force_login(temoin)
        reponse = client.post(reverse("forum:signaler", args=["discussion", question.pk]), {"motif": "Sujet en cours !"})
    assert reponse.url == reverse("forum:matiere", args=[question.matiere_id])
    assert client.get(reverse("forum:discussion", args=[question.pk])).status_code == 404


def test_un_sujet_masque_masque_ses_discussions(client, awa, compta_generale, creer_sujet, session_terminee):
    sujet = creer_sujet(session_terminee, statut=Sujet.Statut.PUBLIE)
    discussion = Discussion.objects.create(matiere=compta_generale, sujet=sujet, auteur=awa, titre="Q", texte="T")
    Sujet.objects.filter(pk=sujet.pk).update(statut=Sujet.Statut.MASQUE)  # demande de retrait reçue
    assert client.get(reverse("forum:discussion", args=[discussion.pk])).status_code == 404


def test_le_moderateur_rejette_un_signalement_abusif(client, question, ben, compta_generale):
    question.masquee = True
    question.save()
    SignalementForum.objects.create(utilisateur=ben, discussion=question, motif="Je n'aime pas")
    moderateur = compte("mod@example.com")
    moderateur.groups.add(Group.objects.get(name="Modérateur"))
    AffectationModerateur.objects.create(moderateur=moderateur, matiere=compta_generale)
    client.force_login(moderateur)

    liste = reverse("admin:forum_signalementforum_changelist")
    assert "Je n&#x27;aime pas" in client.get(liste).content.decode()
    client.post(liste, {"action": "rejeter", "_selected_action": [SignalementForum.objects.get().pk]})

    question.refresh_from_db()
    assert not question.masquee and SignalementForum.objects.get().traite


def test_un_moderateur_ne_voit_que_ses_matieres(client, question, bts):
    autre = Matiere.objects.create(examen=bts, nom="Droit")
    moderateur = compte("mod@example.com")
    moderateur.groups.add(Group.objects.get(name="Modérateur"))
    AffectationModerateur.objects.create(moderateur=moderateur, matiere=autre)
    client.force_login(moderateur)
    assert "Annuité dégressive" not in client.get(reverse("admin:forum_discussion_changelist")).content.decode()


def test_les_statistiques_comptent_les_signalements(client, question, ben):
    SignalementForum.objects.create(utilisateur=ben, discussion=question, motif="Hors sujet")
    client.force_login(Utilisateur.objects.create_superuser(email="admin@example.com", password="Administration-2027"))
    assert "signalements du forum" in client.get(reverse("statistiques")).content.decode()


# --- Modifier et supprimer ses messages ----------------------------------------------------------------------

def test_l_auteur_modifie_sa_question(client, awa, question):
    client.force_login(awa)
    client.post(reverse("forum:modifier", args=["discussion", question.pk]), {"titre": "Annuité dégressive, comment ?", "texte": "Précision."})
    question.refresh_from_db()
    assert question.titre == "Annuité dégressive, comment ?" and question.modifie_le
    assert "modifiée le" in client.get(reverse("forum:discussion", args=[question.pk])).content.decode()


def test_personne_d_autre_ne_modifie_ni_ne_supprime(client, ben, question):
    client.force_login(ben)
    assert client.get(reverse("forum:modifier", args=["discussion", question.pk])).status_code == 404
    assert client.post(reverse("forum:supprimer", args=["discussion", question.pk])).status_code == 404
    page = client.get(reverse("forum:discussion", args=[question.pk])).content.decode()
    assert reverse("forum:modifier", args=["discussion", question.pk]) not in page


def test_supprimer_sa_reponse(client, ben, question):
    reponse = Reponse.objects.create(discussion=question, auteur=ben, texte="Erreur de ma part")
    client.force_login(ben)
    client.post(reverse("forum:supprimer", args=["reponse", reponse.pk]))
    assert not Reponse.objects.exists()


def test_une_question_deja_repondue_reste(client, awa, ben, question):
    Reponse.objects.create(discussion=question, auteur=ben, texte="Voici la méthode.")
    client.force_login(awa)
    client.post(reverse("forum:supprimer", args=["discussion", question.pk]))
    assert Discussion.objects.filter(pk=question.pk).exists() and Reponse.objects.count() == 1


def test_supprimer_sa_question_sans_reponse(client, awa, question):
    client.force_login(awa)
    reponse = client.post(reverse("forum:supprimer", args=["discussion", question.pk]))
    assert reponse.url == reverse("forum:matiere", args=[question.matiere_id]) and not Discussion.objects.exists()


def test_un_message_masque_ne_se_retouche_pas(client, awa, question):
    Discussion.objects.filter(pk=question.pk).update(masquee=True)
    client.force_login(awa)
    assert client.get(reverse("forum:modifier", args=["discussion", question.pk])).status_code == 404
