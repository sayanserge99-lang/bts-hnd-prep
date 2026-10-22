# État du projet

**Dernière mise à jour : 22/10/2026**

## Où on en est

Phase 0 (cadrage). Le squelette Django **tourne** :
- venv `.venv` (Python 3.15.1, Django 5.2.18), dépendances installées ;
- migrations 0001 des 7 applications + `accounts/0002_groupes_roles` + `sujets/0002-0003` (recherche) ;
- **PostgreSQL uniquement** (plus de SQLite) : base du `compose.yaml`, joignable aussi depuis le venv sur localhost:5432 ;
- `pytest` : **73 tests verts** (12 publication, 10 recherche, 16 pages, 16 comptes, 4 langues, 12 retrait, 3 groupes).
- **Production prête** (`compose.prod.yaml`, `deploy/`) : Gunicorn + Nginx, PDF via X-Accel-Redirect, IP via X-Real-IP,
  SMTP, `check --deploy` propre (et dans la CI), sauvegarde quotidienne testée (restauration OK).
  Essayée en local sur le port 8080 avec un `.env.production` de test (non versionné). Pas encore sur un vrai serveur.
- **Demande de retrait** (`/demande-de-retrait/?sujet=<id>`, lien en bas de chaque fiche) : masquage immédiat,
  certification obligatoire, 3 demandes/jour par IP, accusé de réception ; admin : Accepter (PDF supprimé, trace
  gardée) ou Refuser (republié si la session est terminée, sinon brouillon).
- **Interface traduite en anglais** : 270 textes dans `locale/en/LC_MESSAGES/django.po` (+ `.mo` versionné).
  Un test échoue si un texte n'a pas de traduction ; la CI lance `makemessages` avant, donc un texte oublié
  fait échouer GitHub Actions. La langue choisie est enregistrée dans le profil.
- **Comptes V1** (`/compte/`) : inscription e-mail (consentement non précoché enregistré), connexion (bloquée 15 min
  après 5 échecs, via Redis), mot de passe oublié (e-mail dans les logs en dev), espace perso (sujets récents,
  favoris), modification du profil, export JSON et suppression du compte (CDC 10.2).
- **Pages publiques V1** : accueil, catalogue (filtres année/spécialité/matière/type + recherche, HTMX), fiche sujet,
  PDF servi par une vue (jamais par MEDIA_URL), pages légales vides « à rédiger ».
  Tailwind v4 autonome (service `tailwind` du compose), HTMX 2.0.4 dans `static/js/`. Pas encore vues à l'écran par Claude.
- Dépôt public : https://github.com/sayanserge99-lang/bts-hnd-prep — résultats CI lisibles sans connexion via l'API GitHub.
- Contre-épreuve faite : en désactivant la règle de publication, 7 tests échouent.

## Prochaine étape

1. Choix du VPS / hébergeur et du nom de domaine (Serge Alain), puis suivre `deploy/DEPLOIEMENT.md` (HTTPS non testé).
2. Celery : extraction du texte des PDF (remplit `texte_extrait`, puis l'index de recherche) et compression.
3. Retours de Serge Alain sur les pages (pas encore reçus).

## Repères

- Lancer avec Docker (Docker Desktop ouvert) : `docker compose up -d` → http://localhost:8000/admin/ ;
  tests : `docker compose exec web pytest` ; arrêt : `docker compose down`.
- Lancer depuis le venv (le conteneur `db` doit tourner) : `.venv\Scripts\activate` puis
  `python manage.py runserver` / `pytest`.
- Pour Claude : Python et Docker ne sont pas dans le PATH de sa session. Utiliser `.venv/Scripts/python`
  et `export PATH="/c/Users/ayoun/AppData/Local/Programs/DockerDesktop/resources/bin:$PATH"`.
  Ne pas éditer ces fichiers avec `sed` quand le texte contient des barres obliques inverses.
- Règle critique : `sujets/models.py` (`Sujet.save`, `SujetQuerySet`) et `sujets/admin.py` (action `publier`).
- Recherche : `Sujet.objects.rechercher(texte, langue)` ; index mis à jour par `Sujet.save()`,
  sinon `manage.py reindexer_recherche`.
- Tests : `sujets/tests/test_regle_publication.py`, `sujets/tests/test_recherche.py`, `accounts/tests/test_groupes.py`.
- Rôles : migration `accounts/migrations/0002_groupes_roles.py` ; le groupe Administrateur est
  resynchronisé avec toutes les permissions après chaque `migrate` (`accounts/signals.py`).
- Nouveau texte à l'écran : `docker compose exec web python manage.py makemessages -l en --ignore=.venv --ignore=static --no-obsolete`,
  traduire dans le .po, puis `docker compose exec web python manage.py compilemessages --ignore=.venv` et `docker compose restart web`.
- Production locale : `docker compose -f compose.prod.yaml --env-file .env.production up -d --build` → http://localhost:8080.
  Sous Git Bash, `export MSYS_NO_PATHCONV=1` avant `deploy/sauvegarde.sh` (sinon /app devient un chemin Windows).
  Le shell Django 5.2 affiche une ligne d'import : utiliser `shell --no-imports -c` pour lire une valeur.
- Données fictives : `docker compose exec web python manage.py donnees_demo` (refusé si DEBUG=0).
- Superutilisateur : pas encore créé (`docker compose exec web python manage.py createsuperuser`).
