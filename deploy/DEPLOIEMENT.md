# Mise en ligne de BTS-HND Prep

Ce guide installe la plateforme sur un VPS Linux (Ubuntu 24.04, 2 vCPU, 4 Go de RAM, CDC 5)
avec Docker. Comptez une heure la première fois.

## 1. Préparer le serveur

```sh
# Docker et le plugin compose (méthode officielle)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"   # puis se déconnecter et se reconnecter

# Le code
sudo mkdir -p /srv/bts-hnd-prep && sudo chown "$USER" /srv/bts-hnd-prep
git clone https://github.com/sayanserge99-lang/bts-hnd-prep.git /srv/bts-hnd-prep
cd /srv/bts-hnd-prep
```

Avant la mise en production réelle, faites valider le choix de l'hébergeur au regard de la
loi n° 2024/017 sur les transferts de données hors du Cameroun (CDC 10.2).

## 2. Renseigner les secrets

```sh
cp .env.production.example .env.production
nano .env.production
```

| Variable | À mettre |
|---|---|
| `DJANGO_SECRET_KEY` | `python3 -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DJANGO_ALLOWED_HOSTS` | le nom de domaine, par exemple `bts-hnd-prep.cm` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://` suivi du nom de domaine |
| `POSTGRES_PASSWORD` | un mot de passe long et aléatoire |
| `EMAIL_*` | les accès SMTP du fournisseur d'e-mails |
| `DJANGO_ADMINS` | l'adresse qui reçoit les alertes (demandes de retrait, erreurs) |

Le fichier `.env.production` ne doit jamais être envoyé sur GitHub (il est dans `.gitignore`).

## 3. Démarrer

```sh
docker compose -f compose.prod.yaml --env-file .env.production up -d --build
docker compose -f compose.prod.yaml --env-file .env.production exec web python manage.py createsuperuser
```

Les migrations s'appliquent automatiquement au démarrage du conteneur `web`.
Le site répond alors sur le port 80 du serveur.

## 4. HTTPS (Let's Encrypt)

> Cette étape n'a pas encore été testée : elle demande un vrai nom de domaine.

1. Faire pointer le nom de domaine vers l'adresse IP du VPS.
2. Obtenir le certificat sur le serveur, Nginx arrêté :
   `docker compose -f compose.prod.yaml stop nginx && sudo certbot certonly --standalone -d <domaine>`
3. Dans `compose.prod.yaml`, publier aussi le port 443 et monter `/etc/letsencrypt` en lecture seule dans `nginx`.
4. Dans `deploy/nginx.conf`, ajouter un bloc `listen 443 ssl` avec `ssl_certificate` et
   `ssl_certificate_key`, et rediriger le port 80 vers HTTPS.
5. Passer `DJANGO_HTTPS=1` dans `.env.production`, puis relancer avec `up -d --build`.

## 5. Sauvegardes (CDC 4 : quotidiennes, 30 jours)

```sh
crontab -e
# ajouter :
0 3 * * * cd /srv/bts-hnd-prep && sh deploy/sauvegarde.sh >> /var/log/btshnd-sauvegarde.log 2>&1
```

Les sauvegardes vont dans `sauvegardes/`. Copiez-les aussi hors du serveur : une sauvegarde
restée sur la même machine disparaît avec elle.

Restaurer la base :

```sh
docker compose -f compose.prod.yaml --env-file .env.production exec -T db \
    sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean' < sauvegardes/base_AAAA-MM-JJ_HHMM.dump
```

## 6. Mettre à jour

```sh
cd /srv/bts-hnd-prep
git pull
docker compose -f compose.prod.yaml --env-file .env.production up -d --build
```

## Ce que fait la configuration

- **Nginx** sert le CSS et le JavaScript (compressés, gardés un an en cache) et transmet le reste à Django.
- **Les PDF ne sont jamais accessibles par leur chemin.** Django vérifie que le sujet est publié, puis
  demande à Nginx de l'envoyer (en-tête `X-Accel-Redirect`). Un sujet non publié reste introuvable.
- **Gunicorn** fait tourner Django avec 3 processus.
- **Redis** garde le compteur de tentatives de connexion, partagé entre les processus.
