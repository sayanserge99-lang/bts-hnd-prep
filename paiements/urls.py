from django.urls import path

from . import views

app_name = "paiements"

urlpatterns = [
    path("offre/<int:pk>/", views.commander, name="commander"),
    path("notification/", views.notification, name="notification"),
    path("<str:reference>/", views.suivi, name="suivi"),
    path("<str:reference>/recu/", views.recu, name="recu"),
    path("<str:reference>/simulateur/", views.simulateur, name="simulateur"),
]
