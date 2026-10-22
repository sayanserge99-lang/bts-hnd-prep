# Trois cibles :
#   dev   : serveur de développement (compose.yaml)
#   prod  : Gunicorn, CSS minifié, traductions compilées, fichiers statiques collectés (compose.prod.yaml)
#   nginx : Nginx avec les fichiers statiques de l'image prod
#
# Python 3.13 : dernière version officiellement supportée par Django 5.2.
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# gettext : compilation des traductions FR/EN (compilemessages).
# Tesseract (français, anglais) : OCR des sujets scannés ; Ghostscript : compression des PDF (CDC 5).
RUN apt-get update \
    && apt-get install -y --no-install-recommends gettext \
       tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng ghostscript \
    && rm -rf /var/lib/apt/lists/*

# Tailwind CSS en exécutable autonome : pas besoin de Node.js (CDC 5).
ARG TAILWIND_VERSION=v4.1.11
ARG TARGETARCH
RUN case "$TARGETARCH" in arm64) arch=arm64 ;; *) arch=x64 ;; esac \
    && python -c "import urllib.request; urllib.request.urlretrieve('https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-linux-${arch}', '/usr/local/bin/tailwindcss')" \
    && chmod +x /usr/local/bin/tailwindcss

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

RUN useradd --create-home app


FROM base AS dev
COPY . .
RUN chown -R app /app
USER app
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]


FROM base AS prod
COPY . .
# Clé factice : collectstatic doit charger les réglages, mais n'utilise pas la clé.
RUN tailwindcss -i assets/css/app.css -o static/css/app.css --minify \
    && python manage.py compilemessages --ignore=.venv \
    && DJANGO_PRODUCTION=1 DJANGO_SECRET_KEY=construction-de-l-image-uniquement python manage.py collectstatic --noinput \
    && mkdir -p media && chown -R app /app/media
USER app
EXPOSE 8000
# 3 processus pour un VPS de 2 vCPU (CDC 5).
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi --bind 0.0.0.0:8000 --workers 3 --timeout 120 --access-logfile -"]


FROM nginx:1.27-alpine AS nginx
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=prod /app/staticfiles /srv/static
