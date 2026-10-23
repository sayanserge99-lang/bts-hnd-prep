# État du projet

**Dernière mise à jour : 23/10/2026**

## Où on en est

**V1 et V2 terminées côté code** (corrigés, QCM, examens blancs, progression, hors ligne, statistiques, Google, établissements, quiz sur une épreuve). Le projet tourne :
- venv `.venv` (Python 3.15.1, Django 5.2.18), dépendances installées ;
- migrations 0001 des 7 applications + `accounts/0002_groupes_roles` + `sujets/0002-0003` (recherche) ;
- **PostgreSQL uniquement** (plus de SQLite) : base du `compose.yaml`, joignable aussi depuis le venv sur localhost:5432 ;
- `pytest` : **257 tests verts** (dont 20 corrigés, 17 QCM, 14 examens blancs, 11 progression, 12 hors ligne,
  10 statistiques, 16 Google).
- **Connexion Google (V2)** `accounts/google.py` : OpenID Connect sans dépendance (state, PKCE, nonce ; vérifie iss,
  aud, exp, email_verified). Compte existant → connecté ; sinon page « Dernière étape » (spécialité + consentement
  non précoché). Inactive tant que GOOGLE_CLIENT_ID/SECRET sont vides (bouton et adresses absents).
  Compte sans mot de passe : la suppression se confirme en tapant son e-mail.
- **Espace établissement (23/10, `/etablissement/`)** : compte responsable créé par l'admin (inline sur la fiche
  Établissement) ; il confirme ou retire les étudiants qui déclarent son établissement (changer d'établissement
  annule la confirmation) ; dépose des épreuves internes (PDF vérifié, 20 Mo), publiables seulement avec une
  convention de partenariat active ; voit les résultats des étudiants confirmés qui ont activé « Partager mes
  résultats » (consentement révocable, tracé). Étudiant confirmé : page « Épreuves de mon établissement »,
  PDF servi après contrôle (404 sinon). Lien « Mon établissement » dans l'en-tête des responsables.
- **Quiz sur une épreuve (23/10, options 1 + 2 choisies par Serge Alain)** : `Question.sujet` (facultatif) ;
  bouton « Quiz sur cette épreuve » sur la fiche du sujet (toutes ses questions, max 40, mode `sujet` du Quiz).
  Filtre unique `filtre_questions_visibles` / `Question.objects.visibles()` : une question liée à un sujet non
  publié (ou masqué) n'entre dans **aucun** quiz (contre-épreuve faite). Import CSV des questions dans l'admin
  (Questions → Importer des questions) : `entrainement/importation.py`, simulation, doublons, cohérence vérifiée,
  toujours en brouillon, modérateur limité. Option 3 (IA) reportée. Démo : questions d'algorithmique liées au sujet 2025.
- **Demandes de Serge Alain (23/10)** : informatique en premier (`Specialite.ordre`, IG et SWE = 1, contenu de démo
  complet : 3 matières BTS + Database Systems HND, questions, 2 corrigés, examen blanc) ; Entraînement montre toutes
  les matières (« bientôt » si pas de questions) ; établissement facultatif dans le profil (IAI-Cameroun, HINTEL
  — ville à compléter) ; statistiques par établissement (ordre alphabétique, CDC 10.6) ; `Sujet.fourni_par` + filtre
  du catalogue + colonne d'import.
- **Statistiques (V2, module 5b)** `/admin/statistiques/` (administrateurs seulement, lien dans l'en-tête de l'admin) :
  inscrits, nouveaux, actifs, quiz et examens sur 30 j comparés aux 30 j d'avant, à traiter, contenu, sujets les plus
  consultés (compteur anonyme `ConsultationJour`, équipe non comptée), revenus et conversion quand le paiement est ouvert.
  Admin renommée « BTS-HND Prep — Administration ».
- **Hors ligne (V2, module 5a)** : site installable (manifest, icônes `static/icons/`), service worker servi par Django
  (`/sw.js`, template `pwa/sw.js`), bouton « Garder hors ligne » sur la fiche (fiche + corrigé + PDF en cache),
  quiz téléchargeables (`/entrainement/hors-ligne/quiz/`) joués sans réseau, synchronisés et recorrigés par le
  serveur, page `/hors-ligne/`. JS `static/js/hors-ligne.js` testé dans jsdom (défaut trouvé et corrigé).
  **Pas encore essayé sur le téléphone** : le Galaxy s'est déconnecté avant l'essai (adb « no devices »).
- **Progression (V2, module 4)** `/entrainement/progression/` (`entrainement/progression.py`) : compte à rebours
  (session prévue, sinon prochaine), taux par matière et par chapitre (table ReponseQuestion), 3 points faibles
  (≥ 3 réponses, < 100 %) avec quiz conseillé, historique paginé. « Mon espace » : derniers résultats + compte à
  rebours. Détail par chapitre et points faibles réservés au Premium une fois le paiement ouvert.
- **Examens blancs (V2, module 3)** `/entrainement/examens-blancs/` : consignes, heure de fin fixée sur le serveur,
  minuteur (`static/js/examen.js`, testé dans jsdom), sauvegarde HTMX continue (changement, frappe, 30 s), reprise
  après coupure, remise automatique à zéro ou au retour (90 s de marge), QCM corrigé à la remise, corrigé affiché
  seulement après, auto-évaluation par critères (`CritereBareme`), note /20. Visible seulement si le sujet est publié.
- **QCM (V2, module 2)** `/entrainement/` : matières de la spécialité, quiz rapide de 10 questions (matière ou chapitre),
  une question à la fois, correction immédiate + explication (HTMX), note /20, révision des erreurs (dernière réponse
  fausse), derniers quiz. Questions publiées par le modérateur seulement si cohérentes. Table `ReponseQuestion`.
  Limite de quiz par jour prête (QUIZ_GRATUITS_PAR_JOUR, [À FIXER]), active seulement avec PAIEMENT_ACTIF. Les tests d'OCR demandent Tesseract/Ghostscript (Docker, CI).
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

Code V1 + V2 fini. Proposé à Serge Alain le 23/10 (réponse attendue) :
1. **Mise en ligne (bêta)** : choix du VPS et du nom de domaine (Serge Alain), puis `deploy/DEPLOIEMENT.md`
   (HTTPS non testé). Avant : sessions 2020-2026 avec dates de fin officielles, matières, quelques vrais sujets.
2. **V3** (paiement Mobile Money, Premium, contributions, forum, codes IPES) : bloquée par le choix de l'agrégateur
   de paiement et la structure juridique + NIU.
3. Petits travaux faits le 23/10 : quiz d'épreuve hors ligne, page mot de passe (définir/changer), cache apt de la CI.
   Serge Alain choisit l'hébergeur et le domaine pendant ce temps.
À faire par Serge Alain : identifiants Google, comptes responsables IAI/HINTEL + conventions, ville de HINTEL,
pages légales, essai hors ligne sur le Galaxy.

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
  traduire dans le .po (retirer aussi les lignes « #| » des traductions devinées), puis `docker compose exec web python manage.py compilemessages --ignore=.venv` et `docker compose restart web`.
- Production locale : `docker compose -f compose.prod.yaml --env-file .env.production up -d --build` → http://localhost:8080.
  Sous Git Bash, `export MSYS_NO_PATHCONV=1` avant `deploy/sauvegarde.sh` (sinon /app devient un chemin Windows).
  Le shell Django 5.2 affiche une ligne d'import : utiliser `shell --no-imports -c` pour lire une valeur.
- Celery ne se recharge pas tout seul : après une modification de `sujets/tasks.py` ou `traitement_pdf.py`,
  `docker compose restart worker`. Journal : `docker compose logs -f worker`.
- Tester sur le téléphone de Serge Alain (Galaxy A15, débogage USB activé) : télécharger les platform-tools
  (https://dl.google.com/android/repository/platform-tools-latest-windows.zip), puis `adb reverse tcp:8000 tcp:8000`
  et ouvrir http://localhost:8000 dans Chrome. Captures : `adb shell screencap -p /sdcard/x.png` puis `adb pull`.
  (adb était dans le scratchpad de la session du 22/10 : à retélécharger.) Éviter les captures inutiles (notifications privées).
- Données fictives : `docker compose exec web python manage.py donnees_demo` (refusé si DEBUG=0).
- Superutilisateur : pas encore créé (`docker compose exec web python manage.py createsuperuser`).
