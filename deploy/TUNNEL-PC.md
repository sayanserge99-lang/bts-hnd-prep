# Serveur d'essai depuis le PC (tunnel Cloudflare)

Sans compte, sans carte : la version de production tourne sur le PC (Docker), et un tunnel Cloudflare lui donne
une adresse publique en HTTPS (`https://….trycloudflare.com`). Projet Docker séparé (`btshnd-essai`) : sa propre
base et ses propres fichiers, à côté du serveur de développement, qui n'est jamais exposé (DEBUG afficherait des
secrets).

**Limites** : le site s'arrête quand le PC s'éteint, se met en veille ou perd Internet ; l'adresse change à chaque
redémarrage du tunnel ; Cloudflare ne garantit rien pour ces tunnels rapides (essais seulement). Mêmes règles que le
serveur d'essai : comptes fictifs ou testeurs connus et prévenus.

## Démarrer

Les secrets sont dans `.env.essai` (jamais versionné ; modèle : la fin de ce fichier).

```sh
export FICHIER_ENV=.env.essai
docker compose -p btshnd-essai -f compose.prod.yaml -f compose.tunnel.yaml --env-file .env.essai up -d --build
docker compose -p btshnd-essai logs tunnel | grep trycloudflare.com      # l'adresse publique
```

La première fois seulement, le contenu de démonstration (mots de passe tirés au hasard, affichés une fois) :

```sh
docker compose -p btshnd-essai -f compose.prod.yaml -f compose.tunnel.yaml --env-file .env.essai exec web python manage.py donnees_demo
```

Sur le PC : http://localhost:8081. Les e-mails (mot de passe oublié…) s'écrivent dans
`docker compose -p btshnd-essai logs web`.

## Arrêter

```sh
docker compose -p btshnd-essai -f compose.prod.yaml -f compose.tunnel.yaml --env-file .env.essai stop    # garde les données
```

`down -v` efface la base et les fichiers d'essai.

## `.env.essai`

| Variable | Valeur |
|---|---|
| `DJANGO_ALLOWED_HOSTS` | `.trycloudflare.com,localhost` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://*.trycloudflare.com,http://localhost:8081` |
| `DJANGO_HTTPS` | `0` : Cloudflare chiffre jusqu'au visiteur ; entre le tunnel et Nginx, HTTP sur le réseau Docker |
| `DJANGO_SERVEUR_ESSAI` | `1` |
| `EMAIL_BACKEND` | `django.core.mail.backends.console.EmailBackend` |
| `PORT_HTTP` | `8081` |
| `DJANGO_SECRET_KEY`, `POSTGRES_*`, `DJANGO_ADMIN_URL` | tirés au hasard |
