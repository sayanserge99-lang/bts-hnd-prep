from django.urls import path

from . import views

app_name = "communaute"

urlpatterns = [
    path("sujet/", views.envoyer_sujet, name="envoyer_sujet"),
    path("corrige/<int:pk>/", views.proposer_corrige, name="proposer_corrige"),
    path("mes-contributions/", views.mes_contributions, name="mes_contributions"),
]
