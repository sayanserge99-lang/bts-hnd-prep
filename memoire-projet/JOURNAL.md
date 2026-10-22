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
- Recherche plein texte : champ `recherche` + index GIN, config `fr_unaccent`, commande `reindexer_recherche`, 10 tests.
  Bogue trouvé par le test de classement : `SearchRank("recherche")` recalculait le vecteur et perdait les poids → `F("recherche")`.
  SQLite retiré (PostgreSQL uniquement), port 5432 ouvert dans compose.yaml. 25/25 tests verts.
- Pages publiques V1 (accueil, catalogue, fiche, PDF, pages légales vides), commande `donnees_demo`, 15 tests.
  Corrigé avant test : le choix d'examen en HTMX aurait remplacé toute la page par le fragment → liens BTS/HND.
  Tailwind --watch inopérant sur un dossier Windows monté → recompilation en boucle toutes les 2 s. 40/40 tests verts.
- Comptes V1 (inscription, connexion bloquée après 5 échecs via Redis, mot de passe oublié, espace perso,
  favoris HTMX, export JSON, suppression). Corrigé avant test : le champ de spécialités groupées lisait la base
  au chargement du code → groupes construits à chaque formulaire. Tests isolés du Redis de dev. 56/56 verts.
- Traductions anglaises : 270 textes, `.po` + `.mo`, test de complétude (contre-épreuve faite : une traduction
  vidée → le test échoue). Bascule FR/EN enregistrée dans le profil (vue `changer_langue`). 60/60 verts.
- Demande de retrait : formulaire, masquage immédiat + 3 protections (certification, 3/jour/IP, accusé),
  actions Accepter / Refuser. 11 tests, 71/71 verts. Trou trouvé dans le garde-fou des traductions
  (il ne voyait pas les textes jamais extraits) → la CI lance makemessages avant pytest.
- Production : Dockerfile multi-cibles, compose.prod.yaml, Nginx (gzip, cache 1 an, X-Accel-Redirect), réglages
  sécurité, SMTP, ADMINS. Essayée en local : PDF publié OK, brouillon 404 par vue, /media/ et /fichiers-proteges/,
  en-tête forgé sans effet ; check --deploy propre (ajouté à la CI). Sauvegarde testée : 66 sujets restaurés,
  66 PDF dans l'archive. Vérification faussée une fois par la ligne d'import du shell Django → refaite. 73/73 verts.
- Inventaire des espaces : public, étudiant, administration (modérateur + admin) ; un 4e (IPES, V3) sans rôle au CDC.
- Modérateurs limités à leurs matières + accès admin automatique selon le groupe. 8 tests ; contre-épreuve :
  restriction désactivée → 6 échecs. 81/81 verts.
- Celery : worker (dev + prod), tâche traiter_pdf_du_sujet lancée après validation en base quand le fichier change,
  OCR (OCRmyPDF 17 --mode skip, Tesseract fra+eng), compression Ghostscript /ebook gardée si plus légère.
  8 tests (vrai scan généré, OCR, compression > 50 %). Essai réel avec le worker : scan OCRisé en 1,9 s,
  trouvé par « regularisation ». CI : Tesseract + Ghostscript installés. 89/89 verts.
- CI bloquée plus de 10 min à l'installation apt (reconstruction de man-db sur Ubuntu 24.04) → désactivée,
  installation en 10 s, passage vert (6394fb8). Les journaux de la CI ne sont pas lisibles sans connexion :
  impossible de confirmer depuis ici que les tests d'OCR n'y sont pas sautés (-rs les listerait).
- Import de sujets en lot (demande de Serge Alain) : ZIP + sujets.csv, photos JPG/PNG assemblées en PDF (img2pdf),
  simulation, doublons, modèle CSV, page d'admin, commande importer_sujets, Nginx 200 Mo sur cette page.
  Défaut trouvé par un test : un tableau trop gros faisait planter la page (500) → message d'erreur. 26 tests.
  Essai réel : session 2021 absente → 3 refus clairs ; une fois créée, 2 importés + 1 refus, OCR des 2 photos,
  recherche OK. Données d'essai supprimées. 115/115 verts.
- CI de afb122b verte, mais apt a pris 719 s (contre 10 s au passage précédent) : cause non identifiée, noté.
- V2 lancée. Module 1, corrigés : rendu Markdown + MathML, onglets, badges, filtre, signalement, retrait de corrigé,
  aperçu admin, règle de publication sur les corrigés (save + update groupé). 19 tests.
  Faille trouvée par un test : latex2mathml recopie 	ext{<script>} sans l'échapper (mon commentaire disait
  l'inverse) → nettoyage nh3 de tout le HTML final avec une liste MathML ; contre-épreuve faite.
  Défauts corrigés en route : refus de retrait republiait un corrigé sans la règle ; acceptation ne vidait pas
  le début du corrigé ; chaînes de formules non brutes (, 	) dans donnees_demo. 134/134 verts.
- V2 module 2, QCM : quiz rapide, correction immédiate HTMX, révision des erreurs, admin (cohérence avant publication,
  actions), 14 questions de démo (4 types, formules), navigation activée. 17 tests ; essai réel avec un compte
  temporaire : 8 questions, explication absente avant réponse, 10/20, révision de 4 erreurs. 151/151 verts.
