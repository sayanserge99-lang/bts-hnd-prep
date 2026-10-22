# État du projet

**Dernière mise à jour : 22/10/2026**

## Où on en est

**V1 terminée côté code ; V2 en cours** (module 1/5 fait : corrigés). Le projet tourne :
- venv `.venv` (Python 3.15.1, Django 5.2.18), dépendances installées ;
- migrations 0001 des 7 applications + `accounts/0002_groupes_roles` + `sujets/0002-0003` (recherche) ;
- **PostgreSQL uniquement** (plus de SQLite) : base du `compose.yaml`, joignable aussi depuis le venv sur localhost:5432 ;
- `pytest` : **134 tests verts** (dont 19 corrigés). Les tests d'OCR demandent Tesseract/Ghostscript (Docker, CI).
- **Corrigés (V2, module 1)** : onglets Sujet/Corrigé, Markdown + tableaux + formules en MathML (`sujets/rendu.py`,
  nettoyé par nh3), badges vérifié/communauté/en préparation + filtre dans la liste, avertissement, signalement
  (connecté), demande de retrait d'un corrigé, aperçu dans l'admin. Règle de publication appliquée aux corrigés.
  Accès partiel prêt : tout est visible tant que PAIEMENT_ACTIF est faux (`paiements/acces.py`).
- **Import de sujets en lot** (`sujets/importation.py`) : ZIP = sujets.csv + PDF ou photos (plusieurs photos = un PDF
  multipage). Admin « Sujets → Importer des sujets » (simulation par défaut, modèle CSV) et commande
  `importer_sujets <zip|dossier> [--appliquer]`. Toujours en brouillon ; session et matière doivent exister ;
  doublons (session+matière+type) ignorés ; modérateur limité à ses matières. Essai réel OK (photos → OCR → recherche).
- **Celery** (service `worker`) : chaque PDF ajouté ou remplacé → texte (pypdf), OCR si scan (OCRmyPDF/Tesseract
  fra+eng), compression Ghostscript gardée si plus légère, nb de pages, index de recherche. Essai réel OK (1,9 s).
- **Modérateurs limités à leurs matières** dans l'admin (`accounts/moderation.py`, 8 pages) ; matières attribuées
  depuis la fiche de l'utilisateur ; entrer dans le groupe Modérateur/Administrateur ouvre l'accès à /admin/.
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

1. V2, module 2 : QCM (banque de questions, quiz rapide de 10, correction immédiate, révision des erreurs).
   Puis 3 : examens blancs ; 4 : suivi de progression ; 5 : PWA, statistiques back-office, connexion Google.
2. Choix du VPS / hébergeur et du nom de domaine (Serge Alain), puis suivre `deploy/DEPLOIEMENT.md` (HTTPS non testé).
   Retours de Serge Alain sur les pages (pas encore reçus).
3. Fin de la V1 : rédaction des pages légales (contenu de Serge Alain), collecte des vrais sujets puis import en lot
   (avant : saisir les sessions 2020-2026 avec leurs dates de fin officielles, et les matières de chaque spécialité).
   Puis V2 : corrigés, QCM, examens blancs, suivi de progression, PWA hors ligne.

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
- Celery ne se recharge pas tout seul : après une modification de `sujets/tasks.py` ou `traitement_pdf.py`,
  `docker compose restart worker`. Journal : `docker compose logs -f worker`.
- Données fictives : `docker compose exec web python manage.py donnees_demo` (refusé si DEBUG=0).
- Superutilisateur : pas encore créé (`docker compose exec web python manage.py createsuperuser`).
