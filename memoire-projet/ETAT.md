# État du projet

**Dernière mise à jour : 22/10/2026**

## Où on en est

Phase 0 (cadrage). Le squelette Django **tourne** :
- venv `.venv` (Python 3.15.1, Django 5.2.18), dépendances installées ;
- migrations 0001 des 7 applications + `accounts/0002_groupes_roles` + `sujets/0002-0003` (recherche) ;
- **PostgreSQL uniquement** (plus de SQLite) : base du `compose.yaml`, joignable aussi depuis le venv sur localhost:5432 ;
- `pytest` : **25 tests verts** (12 règle de publication, 10 recherche, 3 groupes de rôles), en local et sur GitHub Actions.
- Dépôt public : https://github.com/sayanserge99-lang/bts-hnd-prep — résultats CI lisibles sans connexion via l'API GitHub.
- Contre-épreuve faite : en désactivant la règle de publication, 7 tests échouent.

## Prochaine étape

1. Templates Tailwind/HTMX/Alpine, pages publiques de la V1 (accueil, catalogue des sujets avec filtres et recherche).
2. Docker de production (Gunicorn, Nginx), fichier séparé de compose.yaml.
3. Celery : extraction du texte des PDF (remplit `texte_extrait`, puis l'index de recherche).

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
- Superutilisateur : pas encore créé (`docker compose exec web python manage.py createsuperuser`).
