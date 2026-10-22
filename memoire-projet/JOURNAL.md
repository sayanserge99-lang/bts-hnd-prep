# Journal

## 22/10/2026

- Analyse du cahier des charges v1, des maquettes, puis du CDC v2 : presque toutes les remarques intégrées.
- Analyse de l'étude de faisabilité : calculs justes ; 4 hypothèses à revoir (reporté, voir A-FAIRE).
- Points 5 à 12 validés par Serge Alain (voir DECISIONS).
- Création de ce dossier mémoire et du `CLAUDE.md` racine.
- Écriture du squelette Django : `config/`, 7 applications avec `models.py` et `admin.py`,
  `catalogue/translation.py`, test de la règle de publication.
- **Non vérifié** : Python absent de la machine, donc ni migrations générées ni tests exécutés.

## 22/10/2026 (suite)

- Python 3.15.1 installé par Serge Alain. venv créé, dépendances installées (Django 5.2.18).
- `manage.py check` OK, migrations générées, `migrate` OK. 12/12 tests verts du premier coup.
- Contre-épreuve : règle de publication désactivée → 7 tests échouent ; fichier restauré.
- Ajout de la migration des groupes (Étudiant, Modérateur, Administrateur) + 3 tests.
  Défaut trouvé par le test : l'Administrateur n'avait pas les permissions des modèles migrés
  après lui → resynchronisation par signal `post_migrate`. 15/15 tests verts.

- `git init`, `.gitattributes` (LF), premier commit 61249a5 sur `main`. Pas encore de dépôt distant.
- Dépôt GitHub relié et poussé (sayanserge99-lang/bts-hnd-prep). Le compte AyounSanama, enregistré dans Windows, n'avait pas accès : nom de compte ajouté dans l'URL du remote.
- GitHub Actions ajouté : check + makemigrations --check + pytest, sur PostgreSQL 17 et Python 3.13.
- Dépôt passé en public. Premier passage GitHub Actions vert (run 39752941518) : tests OK sur PostgreSQL.
- WSL 2 + Docker Desktop installés par Serge Alain. Ajout de Dockerfile, compose.yaml, .dockerignore : migrations OK sur PostgreSQL, admin répond (200), 15/15 tests verts dans le conteneur.
