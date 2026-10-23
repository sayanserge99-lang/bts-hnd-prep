from django.urls import path

from . import views

app_name = "partenaires"

urlpatterns = [
    path("", views.espace, name="espace"),
    path("etudiants/<int:pk>/valider/", views.valider, name="valider"),
    path("etudiants/<int:pk>/retirer/", views.retirer, name="retirer"),
    path("epreuves/deposer/", views.deposer, name="deposer"),
    path("epreuves/<int:pk>/publication/", views.basculer_publication, name="publication"),
    path("epreuves/<int:pk>/supprimer/", views.supprimer_epreuve, name="supprimer_epreuve"),
    path("epreuves/<int:pk>/pdf/", views.pdf_epreuve, name="pdf_epreuve"),
    path("mes-epreuves/", views.mes_epreuves, name="mes_epreuves"),
]
