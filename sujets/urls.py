from django.urls import path

from . import views

app_name = "sujets"

urlpatterns = [
    path("", views.liste, name="liste"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/pdf/", views.pdf, name="pdf"),
    path("<int:pk>/favori/", views.basculer_favori, name="favori"),
    path("corriges/<int:pk>/pdf/", views.pdf_corrige, name="pdf_corrige"),
    path("corriges/<int:pk>/signaler/", views.signaler_corrige, name="signaler_corrige"),
]
