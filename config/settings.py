import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent

# DJANGO_PRODUCTION=1 active les réglages du serveur en ligne (compose.prod.yaml).
PRODUCTION = os.environ.get("DJANGO_PRODUCTION") == "1"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-uniquement-a-changer")
if PRODUCTION and SECRET_KEY == "dev-uniquement-a-changer":
    raise ImproperlyConfigured("DJANGO_SECRET_KEY doit être défini en production.")
DEBUG = os.environ.get("DJANGO_DEBUG", "0" if PRODUCTION else "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o]

INSTALLED_APPS = [
    # modeltranslation doit précéder django.contrib.admin
    "modeltranslation",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "django.forms",
    "accounts",
    "catalogue",
    "sujets",
    "entrainement",
    "communaute",
    "paiements",
    "partenaires",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context_processors.fonctionnalites",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# PostgreSQL uniquement (CDC 5) : la recherche plein texte en dépend.
# Valeurs par défaut = base du compose.yaml, joignable depuis le venv sur localhost:5432.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "btshnd"),
        "USER": os.environ.get("POSTGRES_USER", "btshnd"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "btshnd"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

AUTH_USER_MODEL = "accounts.Utilisateur"
LOGIN_URL = "accounts:connexion"
LOGIN_REDIRECT_URL = "accounts:profil"
LOGOUT_REDIRECT_URL = "accueil"

# CDC 4 : limitation des tentatives de connexion (par adresse e-mail).
CONNEXION_ESSAIS_MAX = 5
CONNEXION_BLOCAGE_SECONDES = 15 * 60

# CDC 3.8 : quiz par jour de l'offre gratuite, appliqué seulement une fois le paiement ouvert.
# [À FIXER] : le quota exact reste à décider (CDC 7) ; 3 est une valeur d'attente.
QUIZ_GRATUITS_PAR_JOUR = 3

# CDC 10.1 : une demande de retrait masque le contenu tout de suite ; on en limite le nombre par adresse IP.
DEMANDES_RETRAIT_PAR_JOUR = 3

# Version des CGU et de la politique de confidentialité enregistrée avec chaque consentement (CDC 10.2).
VERSION_POLITIQUES = "1.0"

# Redis partagé entre les processus (indispensable au blocage des connexions en production).
if os.environ.get("REDIS_URL"):
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": os.environ["REDIS_URL"]}}

# Celery : file de tâches dans Redis. Sans Redis (venv seul, CI), les tâches s'exécutent sur place.
CELERY_BROKER_URL = os.environ.get("REDIS_URL", "memory://")
CELERY_TASK_ALWAYS_EAGER = not os.environ.get("REDIS_URL")
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
# Un OCR de sujet scanné prend quelques secondes par page ; au-delà de 10 minutes, on abandonne.
CELERY_TASK_TIME_LIMIT = 10 * 60
CELERY_TASK_SOFT_TIME_LIMIT = 9 * 60

# E-mails : affichés dans les logs en développement, envoyés par SMTP en production.
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend" if PRODUCTION else "django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "BTS-HND Prep <ne-pas-repondre@localhost>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
# Destinataires des alertes (nouvelle demande de retrait, erreurs) : "Nom <adresse>,Nom <adresse>".
ADMINS = [
    (nom.strip(), adresse.strip(" >"))
    for nom, adresse in (a.split("<") for a in os.environ.get("DJANGO_ADMINS", "").split(",") if "<" in a)
]

# Les champs de formulaire utilisent templates/forms/champ.html.
FORM_RENDERER = "config.formulaires.Rendu"

# Derrière Nginx : l'adresse du visiteur arrive dans X-Real-IP, et Nginx envoie les PDF
# (X-Accel-Redirect) une fois que Django a vérifié la publication.
DERRIERE_PROXY = PRODUCTION
FICHIERS_PAR_NGINX = PRODUCTION

if PRODUCTION:
    # Noms de fichiers statiques versionnés : le navigateur les garde en cache sans risque.
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"},
    }
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"

# DJANGO_HTTPS=1 une fois le certificat installé sur le serveur (CDC 4 : HTTPS partout).
if os.environ.get("DJANGO_HTTPS") == "1":
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    # Une heure pour commencer ; à augmenter (un an) quand HTTPS est stable.
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDES", "3600"))
    # Sous-domaines et préchargement HSTS : à décider avec le nom de domaine et un HSTS d'un an.
    SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W021"]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr"
LANGUAGES = [("fr", _("Français")), ("en", _("English"))]
LOCALE_PATHS = [BASE_DIR / "locale"]
MODELTRANSLATION_DEFAULT_LANGUAGE = "fr"
# Une spécialité HND peut n'avoir qu'un nom anglais (et inversement) : on affiche l'autre langue.
MODELTRANSLATION_FALLBACK_LANGUAGES = {"default": ("fr", "en")}
TIME_ZONE = "Africa/Douala"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
# Les PDF ne sont jamais servis directement depuis MEDIA_ROOT : ils passent par une vue
# qui vérifie la publication (sinon un sujet non publié serait lisible par son URL).
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
SUJETS_PAR_PAGE = 20

# Import de sujets en lot (sujets.importation) : garde-fous contre un ZIP anormal.
IMPORT_TAILLE_MAX_FICHIER = 50 * 1024 * 1024
IMPORT_TAILLE_MAX_TOTALE = 500 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Drapeaux des fonctionnalités V2/V3 : présentes dans le code, masquées tant que False.
FONCTIONNALITES = {
    "corriges": True,
    "entrainement": True,
    "examens_blancs": False,
    "hors_ligne": False,
    "contributions": False,
    "forum": False,
}

# CDC 10.4 : aucun paiement sans structure déclarée ni NIU.
EXPLOITANT = {
    "structure": os.environ.get("EXPLOITANT_STRUCTURE", ""),
    "niu": os.environ.get("EXPLOITANT_NIU", ""),
}
PAIEMENT_ACTIF = bool(EXPLOITANT["structure"] and EXPLOITANT["niu"])
