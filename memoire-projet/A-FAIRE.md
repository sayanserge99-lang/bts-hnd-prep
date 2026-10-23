# À faire

## Fait

- [x] Python installé, venv, dépendances, migrations, `pytest` vert (22/10/2026).
- [x] Migration des groupes Étudiant, Modérateur, Administrateur et leurs permissions.

## Prochain

- [x] `git init` + premier commit (61249a5). Auteur local : Ayoung Sanama Serge Alain <sayanserge99@gmail.com>.
- [x] Dépôt GitHub : https://github.com/sayanserge99-lang/bts-hnd-prep (public). Le remote contient le nom de compte, car Windows a aussi le compte AyounSanama en mémoire.
- [x] GitHub Actions : `.github/workflows/tests.yml` (check, migrations manquantes, pytest sur PostgreSQL 17, Python 3.13).
- [x] CI : paquets système en cache (cache-apt-pkgs-action) ; l'étape apt variait de 10 s à 12 min.
- [x] Image Docker (dev et prod) et CI en Python 3.13 (le venv local reste en 3.15).

## Squelette (suite)

- [x] Recherche plein texte : index GIN, accents ignorés (fr_unaccent), débuts de mot, titre et matière > texte.
- [ ] Recherche : un renommage de matière ne met pas l'index à jour (lancer `reindexer_recherche`) ; à automatiser si besoin.
- [x] Docker de développement : `Dockerfile` (Python 3.13), `compose.yaml` (web, PostgreSQL 17, Redis 7).
- [x] Docker de production : Gunicorn, Nginx, X-Accel-Redirect, X-Real-IP, SMTP, check --deploy, sauvegardes.
- [ ] HTTPS Let's Encrypt sur le vrai serveur (procédure écrite dans deploy/DEPLOIEMENT.md, non testée).
- [x] Celery : texte, OCR des scans, compression, pages, index ; action d'admin « Relancer le traitement ».
- [x] Import de sujets en lot (ZIP + CSV, photos acceptées, simulation, doublons, commande serveur).
- [ ] Avant le premier vrai import : saisir sessions 2020-2026 (dates de fin officielles réelles) et matières/coefficients
      d'après la circulaire du MINESUP (CDC 3.10).
- [ ] django-storages si stockage S3 (aujourd'hui : volume Docker `fichiers`).
- [ ] Retouche des photos de sujets (recadrage, contraste) avant publication : manuelle (étude de faisabilité 2.1).
- [ ] Images WebP (CDC 4) : à traiter avec l'envoi de photos par les contributeurs (V3).
- [ ] Copier les sauvegardes hors du serveur (autre machine ou stockage distant).
- [ ] Créer un superutilisateur : `docker compose exec web python manage.py createsuperuser` (à faire par Serge Alain).
- [x] Tailwind + HTMX, gabarit de base, sélecteur de langue, accueil, catalogue, fiche sujet, pages légales vides.
- [x] Comptes : inscription, connexion avec blocage, mot de passe oublié, espace perso, favoris, export, suppression.
- [ ] Choisir le fournisseur d'e-mails (SMTP) et remplir `EMAIL_*` dans .env.production.
- [x] Option « Partager mes résultats avec mon établissement » (CDC 10.6), révocable.
- [x] Traductions EN : 270 textes traduits, test de complétude.
- [ ] Faire relire les traductions anglaises par un anglophone (vocabulaire HND : « past papers », « marking guide »).
- [x] Production : `compilemessages` lancé dans l'image prod (le `.mo` reste versionné pour le dev).
- [x] Formulaire de demande de retrait (sujets) avec actions d'admin Accepter / Refuser.
- [ ] Rédiger les pages légales (mentions, confidentialité, CGV, contact) : contenu à fournir par Serge Alain / juriste.
- [ ] Renseigner DJANGO_ADMINS dans .env.production pour être prévenu des demandes de retrait.
- [ ] Demande de retrait des corrigés : à ajouter avec les corrigés (V2).
- [ ] Décider le quota de téléchargement des visiteurs (CDC 7 : « limité ») ; aujourd'hui tout est ouvert.
- [ ] Accueil : apparier spécialités BTS ↔ HND comme sur la maquette (aucun lien en base aujourd'hui).
- [ ] Alpine.js : pas encore nécessaire (ajouter quand il le sera : minuteur d'examen blanc, menus).
- [x] Modérateurs limités à leurs matières (liste, fiches, actions, listes de choix), accès admin automatique.
- [x] Rôle responsable d'établissement (hors des 3 rôles du CDC 7 : lien ResponsableEtablissement, pas un groupe).
- [x] Informatique en premier, toutes les matières dans Entraînement, établissement dans le profil, stats et filtre.
- [ ] Compléter la ville et la région de HINTEL dans l'admin ; ajouter les autres IPES.
- [x] Espace établissement + épreuves internes (validation des étudiants, convention active, résultats partagés).
- [ ] Créer les comptes responsables d'IAI-Cameroun et HINTEL et saisir leurs conventions (admin, Serge Alain).
- [ ] Épreuves internes : pas encore dans le mode hors ligne, ni d'avis aux étudiants quand une épreuve est publiée.
- [x] Quiz sur une épreuve (questions rattachées à un sujet) + import CSV des questions.
- [ ] Option 3 : brouillons de questions générés par IA depuis le texte du PDF, validés par un enseignant (plus tard).
- [x] Quiz sur une épreuve téléchargeable hors ligne (bouton sur la fiche du sujet).
- [x] Connexion Google V2 (code prêt, inactive sans identifiants).
- [ ] Créer les identifiants OAuth Google (Serge Alain) et essayer la connexion en vrai.
- [x] « Définir un mot de passe » (compte Google) / « Changer mon mot de passe » dans Mon espace.
- [x] Statistiques back-office V2 : tableau de bord administrateur, compteur anonyme des consultations.
- [x] Hors ligne V2 : installable, sujets gardés (fiche, corrigé, PDF), quiz téléchargés + synchronisés.
- [ ] Hors ligne : essai réel sur téléphone ; un sujet retiré (demande de retrait) reste sur les téléphones qui l'ont gardé.
- [ ] Hors ligne : compter les consultations de PDF (statistiques) — les lectures hors ligne ne sont pas vues.
- [x] Progression V2 : taux par matière/chapitre, points faibles + quiz conseillé, compte à rebours, historique.
- [x] Examens blancs V2 : minuteur serveur, sauvegarde continue, reprise, remise auto, auto-évaluation.
- [ ] Examens blancs : tester le minuteur sur un vrai téléphone (mise en veille, changement d'onglet).
- [x] QCM V2 : quiz rapide, correction immédiate, révision des erreurs, cohérence des questions, quota prêt.
- [ ] Fixer QUIZ_GRATUITS_PAR_JOUR (CDC 7 : quotas « restent à fixer »).
- [x] Corrigés V2 : rendu Markdown/MathML sûr, badges, filtre, signalement, retrait, aperçu admin.
- [ ] Corrige : décider si on ajoute `verifie_par` (FK utilisateur) pour tracer la vérification.
- [x] V3 : filigrane nominatif et lien temporaire sur le PDF du corrigé Premium (CDC 4).
- [ ] Rendu : les $ à l'intérieur d'un bloc de code sont pris pour des formules (limite connue).
- [x] Affichage MathML vérifié sur Chrome Android (Galaxy A15) : fraction et tableaux OK.
- [ ] Vérifier aussi sur Firefox et sur l'ancien navigateur Samsung Internet.
- [x] V3 module 1 : contributions (envoi de sujets et de corrigés, file de modération, récompense).
- [ ] Fixer JOURS_OFFERTS_PAR_SUJET avec Serge Alain (7 jours pour l'instant). Tant que le paiement est fermé,
      tout est gratuit : les jours offerts aujourd'hui expirent avant l'ouverture du Premium.
- [ ] Contributions : pas de conversion WebP des photos (assemblées en PDF), pas de recadrage automatique.
- [x] V3 module 4 : Premium (règle unique, page Offres, protection des PDF de corrigés).
- [ ] Fixer les prix (Pass session, mensuel) : les offres de démo sont celles de l'étude de faisabilité.
- [ ] Rappel par e-mail avant la fin d'un abonnement ; passage du statut à « expiré » (aujourd'hui seules les dates
      comptent, le statut reste « actif »).
- [x] V3 module 3 : codes d'accès (génération par lot, activation, suivi par l'établissement).
- [ ] Codes d'accès : pas de date d'expiration propre au code (il vit tant que la convention est active) ; prix et
      facturation des lots aux IPES hors plateforme (à décider avec Serge Alain).
- [x] V3 module 2 : forum (questions-réponses par matière, signalements, modération).
- [ ] Forum : pas de modification ni de suppression de ses propres messages, pas de recherche, pas d'abonnement
      à une discussion (seul l'auteur de la question est prévenu). À ajouter selon les retours.

## Étude de faisabilité (reporté, « on les fera le moment venu »)

- [ ] Recalculer les scénarios : sans le budget SMS (seuil → 430 abonnés, 0,97 %),
      ajouter un scénario « vente courte » (paiement ouvert fin mars 2027), volume de contenu BTS + HND.
- [ ] Ajouter la question de trésorerie (qui avance les 2,36 M FCFA).
- [ ] Aligner « janvier à juin » sur la règle du Pass (aussi dans les maquettes).
- [ ] Nuancer « textes officiels non protégés » (sujets d'examen) → question au juriste.

## Maquettes

- [ ] Accueil : « télécharger gratuitement » → « avec un compte » (visiteur = téléchargement limité).
- [ ] Mobile : badge « Bientôt » sur l'onglet Entraînement.
- [ ] Écran corrigé : étiqueter « écran V3 ».
- [ ] Texte du Pass : « valable jusqu'à la fin de la session 2027 ».
