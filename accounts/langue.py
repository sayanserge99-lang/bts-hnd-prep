"""Langue de l'interface pour un étudiant connecté : celle de son compte (à l'inscription, celle de son examen :
HND en anglais, BTS en français), tant que le navigateur n'a pas de choix enregistré (nouvel appareil, cookie
effacé). La bascule FR/EN pose ce cookie et l'enregistre sur le compte (accounts.views.changer_langue)."""

from django.conf import settings
from django.utils import translation


class LangueDuCompte:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        utilisateur = getattr(request, "user", None)
        a_appliquer = (
            utilisateur is not None and utilisateur.is_authenticated
            and settings.LANGUAGE_COOKIE_NAME not in request.COOKIES and utilisateur.langue != request.LANGUAGE_CODE
        )
        if a_appliquer:
            translation.activate(utilisateur.langue)
            request.LANGUAGE_CODE = utilisateur.langue
        reponse = self.get_response(request)
        if a_appliquer:
            reponse.set_cookie(settings.LANGUAGE_COOKIE_NAME, utilisateur.langue)
        return reponse
