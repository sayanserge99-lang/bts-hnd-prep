# État du projet

**Dernière mise à jour : 22/10/2026**

## Où on en est

Phase 0 (cadrage). Le squelette Django **tourne** :
- venv `.venv` (Python 3.15.1, Django 5.2.18), dépendances installées ;
- migrations 0001 des 7 applications + `accounts/0002_groupes_roles` ; `migrate` appliqué sur SQLite (`db.sqlite3`) ;
- `pytest` : **15 tests verts** (12 règle de publication, 3 groupes de rôles).
- Contre-épreuve faite : en désactivant la règle de publication, 7 tests échouent.

## Prochaine étape

1. `git init` + premier commit + dépôt GitHub (en attente de l'accord de Serge Alain).
2. Docker (Django + PostgreSQL + Redis) et passage des tests sur PostgreSQL.
3. Recherche plein texte (SearchVectorField + index GIN), puis templates Tailwind/HTMX.

## Repères

- Lancer : `.venv\Scripts\activate` puis `python manage.py runserver` / `pytest`.
  Python 3.15 n'est pas dans le PATH de la session de Claude : utiliser `.venv/Scripts/python`.
- Règle critique : `sujets/models.py` (`Sujet.save`, `SujetQuerySet`) et `sujets/admin.py` (action `publier`).
- Tests : `sujets/tests/test_regle_publication.py`, `accounts/tests/test_groupes.py`.
- Rôles : migration `accounts/migrations/0002_groupes_roles.py` ; le groupe Administrateur est
  resynchronisé avec toutes les permissions après chaque `migrate` (`accounts/signals.py`).
- Base : SQLite par défaut ; PostgreSQL si `POSTGRES_DB` est défini (voir `.env.example`).
