from django.urls import path

from . import views

app_name = "forum"

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("matiere/<int:pk>/", views.matiere, name="matiere"),
    path("matiere/<int:pk>/nouvelle/", views.nouvelle, name="nouvelle"),
    path("discussion/<int:pk>/", views.discussion, name="discussion"),
    path("reponse/<int:pk>/accepter/", views.accepter, name="accepter"),
    path("signaler/<str:type_cible>/<int:pk>/", views.signaler, name="signaler"),
    path("modifier/<str:type_cible>/<int:pk>/", views.modifier, name="modifier"),
    path("supprimer/<str:type_cible>/<int:pk>/", views.supprimer, name="supprimer"),
]
