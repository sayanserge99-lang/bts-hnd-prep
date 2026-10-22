from django.urls import path

from . import views

app_name = "sujets"

urlpatterns = [
    path("", views.liste, name="liste"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/pdf/", views.pdf, name="pdf"),
]
