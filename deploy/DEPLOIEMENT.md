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

# Sécurité du serveur : pare-feu (22, 80, 443), fail2ban, mises à jour automatiques, SSH par clé.
# Installez d'abord votre clé SSH (depuis votre PC : ssh-copy-id utilisateur@serveur), sinon le script
# laisse la connexion par mot de passe ouverte pour ne pas vous enfermer dehors.
sudo sh deploy/securiser-serveur.sh
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
| `DJANGO_ADMIN_URL` | une adresse d'administration difficile à deviner, avec la barre finale, par exemple `gestion-7f3k/` (par défaut `admin/`, que les robots essaient en premier) |
| `CSP_FORM_ACTION_EN_PLUS` | l'adresse de la page de paiement de l'agrégateur, par exemple `https://checkout.agregateur.cm` (le navigateur refuse sinon d'y aller après le formulaire) |

Le fichier `.env.production` ne doit jamais être envoyé sur GitHub (il est dans `.gitignore`).

## 3. Démarrer

```sh
docker compose -f compose.prod.yaml --env-file .env.production up -d --build
docker compose -f compose.prod.yaml --env-file .env.production exec web python manage.py createsuperuser
```

Les migrations s'appliquent automatiquement au démarrage du conteneur `web`.
Le site répond alors sur le port 80 du serveur.

**Double authentification de l'équipe.** À la première ouverture de l'administration, chaque membre de
l'équipe (vous compris) scanne un QR code avec une application (Google Authenticator, Microsoft
Authenticator ou Aegis) et note ses 10 codes de secours. Ensuite, le code à 6 chiffres est demandé à chaque
session. Téléphone perdu : un autre administrateur supprime sa ligne dans **Comptes → Doubles
authentifications** ; si vous êtes seul administrateur, gardez vos codes de secours hors du téléphone.

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

Les sauvegardes sont **chiffrées** (AES-256) et **copiées hors du serveur** : une sauvegarde restée sur la
même machine disparaît avec elle, et une sauvegarde en clair chez un hébergeur expose les données des étudiants.

1. La phrase de chiffrement, lisible par root seulement. **Notez-la aussi ailleurs** (gestionnaire de mots de
   passe, papier) : sans elle, les sauvegardes sont illisibles, même pour vous.
   ```sh
   sudo apt install -y gnupg rclone
   openssl rand -base64 32 | sudo tee /root/.btshnd-sauvegarde-phrase && sudo chmod 600 /root/.btshnd-sauvegarde-phrase
   ```
2. L'espace de stockage distant (Backblaze B2, Google Drive, OneDrive…) : `sudo rclone config`, créer une
   destination, par exemple `b2`, puis vérifier avec `sudo rclone lsd b2:`.
3. La sauvegarde chaque nuit (crontab de root : `sudo crontab -e`) :
   ```sh
   0 3 * * * cd /srv/bts-hnd-prep && DESTINATION_DISTANTE=b2:btshnd-sauvegardes sh deploy/sauvegarde.sh >> /var/log/btshnd-sauvegarde.log 2>&1
   ```

Restaurer la base (déchiffrer, puis `pg_restore`) :

```sh
sudo gpg --batch --pinentry-mode loopback --passphrase-file /root/.btshnd-sauvegarde-phrase \
    -d sauvegardes/base_AAAA-MM-JJ_HHMM.dump.gpg > /tmp/base.dump
docker compose -f compose.prod.yaml --env-file .env.production exec -T db \
    sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean' < /tmp/base.dump
rm /tmp/base.dump
```

Essayez une restauration une fois par trimestre : une sauvegarde jamais restaurée n'est qu'un espoir.

## 6. Importer des sujets en lot

Depuis l'admin : **Sujets → Importer des sujets** (ZIP jusqu'à 200 Mo). Pour un très gros lot,
copiez sur le serveur un dossier contenant `sujets.csv` et les fichiers, puis :

```sh
docker compose -f compose.prod.yaml --env-file .env.production cp ./mon-lot web:/tmp/mon-lot
# Simulation (rien n'est enregistré), puis import réel :
docker compose -f compose.prod.yaml --env-file .env.production exec web python manage.py importer_sujets /tmp/mon-lot
docker compose -f compose.prod.yaml --env-file .env.production exec web python manage.py importer_sujets /tmp/mon-lot --appliquer
```

Les sujets arrivent en brouillon ; le worker fait l'OCR et la compression ; publiez-les ensuite
avec l'action « Publier » de l'admin.

## 7. Connexion avec Google (facultatif)

Tant que `GOOGLE_CLIENT_ID` et `GOOGLE_CLIENT_SECRET` sont vides, le bouton « Continuer avec Google »
n'apparaît pas. Pour l'activer, avec le compte Google du projet :

1. Ouvrir https://console.cloud.google.com/, créer un projet « BTS-HND Prep ».
2. **API et services → Écran de consentement OAuth** : type « Externe », nom de l'application,
   adresse de contact, lien vers la politique de confidentialité ; portées `openid`, `email`, `profile`.
3. **API et services → Identifiants → Créer des identifiants → ID client OAuth** : type « Application Web ».
4. **URI de redirection autorisés** : `https://<domaine>/compte/google/retour/`
   (et `http://localhost:8000/compte/google/retour/` pour essayer en développement).
5. Copier l'ID client et le code secret dans `.env.production`, puis relancer avec `up -d --build`.

À la première connexion avec Google, l'étudiant choisit sa spécialité et coche lui-même le
consentement (CDC 10.2) : la connexion Google ne contourne pas cette étape.

## 8. Mettre à jour

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
- **Redis** garde le compteur de tentatives de connexion, partagé entre les processus, et la file des tâches.
- **Le worker Celery** traite chaque PDF ajouté : lecture du texte pour la recherche, OCR des scans
  (Tesseract, français et anglais), compression (Ghostscript, gardée seulement si le fichier est plus léger).
  Si un traitement a échoué, l'action d'admin « Relancer le traitement des PDF » le refait.
