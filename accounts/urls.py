from django.urls import path
from django.views.generic import TemplateView

from paiements.views import activer_code

from . import views, views_double_auth

app_name = "accounts"

urlpatterns = [
    path("inscription/", views.inscription, name="inscription"),
    path("connexion/", views.Connexion.as_view(), name="connexion"),
    path("deconnexion/", views.deconnexion, name="deconnexion"),
    path("google/", views.google_debut, name="google"),
    path("google/retour/", views.google_retour, name="google_retour"),
    path("google/inscription/", views.google_finir, name="google_finir"),
    path("mot-de-passe/", views.MotDePasseOublie.as_view(), name="mot_de_passe_oublie"),
    path(
        "mot-de-passe/envoye/",
        TemplateView.as_view(template_name="accounts/mot_de_passe_envoye.html"),
        name="mot_de_passe_envoye",
    ),
    path("mot-de-passe/<uidb64>/<token>/", views.NouveauMotDePasse.as_view(), name="nouveau_mot_de_passe"),
    path("profil/", views.profil, name="profil"),
    path("profil/modifier/", views.modifier_profil, name="modifier_profil"),
    path("profil/mot-de-passe/", views.mot_de_passe, name="mot_de_passe"),
    path("profil/code/", activer_code, name="activer_code"),
    path("double-authentification/", views_double_auth.verifier, name="double_auth"),
    path("double-authentification/configurer/", views_double_auth.configurer, name="double_auth_configurer"),
    path("profil/partage/", views.basculer_partage, name="partage"),
    path("profil/mes-donnees/", views.exporter, name="exporter"),
    path("profil/supprimer/", views.supprimer, name="supprimer"),
]
