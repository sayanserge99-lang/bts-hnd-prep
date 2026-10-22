from django.urls import path

from . import views

app_name = "entrainement"

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("lancer/", views.lancer, name="lancer"),
    path("tentative/<int:pk>/", views.tentative, name="tentative"),
    path("tentative/<int:pk>/repondre/", views.repondre, name="repondre"),
    path("tentative/<int:pk>/resultat/", views.resultat, name="resultat"),
]
