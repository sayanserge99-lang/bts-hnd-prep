from django.urls import path

from . import views, views_examens, views_hors_ligne

app_name = "entrainement"

urlpatterns = [
    path("examens-blancs/", views_examens.liste, name="examens"),
    path("examens-blancs/<int:pk>/", views_examens.consignes, name="consignes"),
    path("examens-blancs/<int:pk>/demarrer/", views_examens.demarrer, name="demarrer_examen"),
    path("epreuve/<int:pk>/", views_examens.epreuve, name="epreuve"),
    path("epreuve/<int:pk>/enregistrer/", views_examens.enregistrer, name="enregistrer"),
    path("epreuve/<int:pk>/rendre/", views_examens.rendre, name="rendre"),
    path("epreuve/<int:pk>/auto-evaluation/", views_examens.auto_evaluation, name="auto_evaluation"),
    path("epreuve/<int:pk>/resultat/", views_examens.resultat, name="resultat_examen"),
    path("", views.accueil, name="accueil"),
    path("progression/", views.progression_etudiant, name="progression"),
    path("hors-ligne/quiz/", views_hors_ligne.telecharger_quiz, name="quiz_hors_ligne"),
    path("hors-ligne/synchroniser/<int:pk>/", views_hors_ligne.synchroniser, name="synchroniser_hors_ligne"),
    path("lancer/", views.lancer, name="lancer"),
    path("sujet/<int:pk>/quiz/", views.lancer_sujet, name="lancer_sujet"),
    path("tentative/<int:pk>/", views.tentative, name="tentative"),
    path("tentative/<int:pk>/repondre/", views.repondre, name="repondre"),
    path("tentative/<int:pk>/resultat/", views.resultat, name="resultat"),
]
