# État du projet

**Dernière mise à jour : 22/10/2026**

## Où on en est

Phase 0 (cadrage). Le squelette Django **tourne** :
- venv `.venv` (Python 3.15.1, Django 5.2.18), dépendances installées ;
- migrations 0001 des 7 applications + `accounts/0002_groupes_roles` ; `migrate` appliqué sur SQLite (`db.sqlite3`) ;
- `pytest` : **15 tests verts** (12 règle de publication, 3 groupes de rôles), en local (SQLite) et sur GitHub Actions (PostgreSQL 17, Python 3.13).
- Dépôt public : https://github.com/sayanserge99-lang/bts-hnd-prep — résultats CI lisibles sans connexion via l'API GitHub.
- Contre-épreuve faite : en désactivant la règle de publication, 7 tests échouent.

## Prochaine étape

1. Docker (Django + PostgreSQL + Redis) pour le développement local et la production (Docker Desktop à installer).
2. Recherche plein texte (SearchVectorField + index GIN).
3. Templates Tailwind/HTMX/Alpine, pages publiques de la V1.

## Repères

- Lancer : `.venv\Scripts\activate` puis `python manage.py runserver` / `pytest`.
  Python 3.15 n'est pas dans le PATH de la session de Claude : utiliser `.venv/Scripts/python`.
- Règle critique : `sujets/models.py` (`Sujet.save`, `SujetQuerySet`) et `sujets/admin.py` (action `publier`).
- Tests : `sujets/tests/test_regle_publication.py`, `accounts/tests/test_groupes.py`.
- Rôles : migration `accounts/migrations/0002_groupes_roles.py` ; le groupe Administrateur est
  resynchronisé avec toutes les permissions après chaque `migrate` (`accounts/signals.py`).
- Base : SQLite par défaut ; PostgreSQL si `POSTGRES_DB` est défini (voir `.env.example`).
