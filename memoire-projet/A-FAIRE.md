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
- [x] Recherche : renommer une matière réindexe ses sujets (signal).
- [x] Docker de développement : `Dockerfile` (Python 3.13), `compose.yaml` (web, PostgreSQL 17, Redis 7).
- [x] Docker de production : Gunicorn, Nginx, X-Accel-Redirect, X-Real-IP, SMTP, check --deploy, sauvegardes.
- [ ] HTTPS Let's Encrypt sur le vrai serveur (procédure écrite dans deploy/DEPLOIEMENT.md, non testée).
- [x] Celery : texte, OCR des scans, compression, pages, index ; action d'admin « Relancer le traitement ».
- [x] Import de sujets en lot (ZIP + CSV, photos acceptées, simulation, doublons, commande serveur).
- [x] Classeur du référentiel et commande d'import (27/10).
- [ ] Serge Alain : remplir `contenu/referentiel-a-remplir.xlsx` — sessions 2020-2026 (dates de fin officielles
      réelles), spécialités, matières/coefficients d'après la circulaire du MINESUP (CDC 3.10), chapitres.
- [ ] django-storages si stockage S3 (aujourd'hui : volume Docker `fichiers`).
- [ ] Retouche des photos de sujets (recadrage, contraste) avant publication : manuelle (étude de faisabilité 2.1).
- [ ] Images WebP (CDC 4) : à traiter avec l'envoi de photos par les contributeurs (V3).
- [x] Copier les sauvegardes hors du serveur (rclone, chiffrées).
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
- [x] Demande de retrait des corrigés (fait avec les corrigés, V2).
- [x] Quota des visiteurs : 3 sujets différents par jour, puis compte gratuit (27/10).
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
- [x] Hors ligne : un sujet retiré est effacé des téléphones dès qu'ils ont du réseau.
- [ ] Hors ligne : essai réel sur téléphone (Galaxy).
- [ ] Hors ligne : compter les consultations de PDF (statistiques) — les lectures hors ligne ne sont pas vues.
- [x] Progression V2 : taux par matière/chapitre, points faibles + quiz conseillé, compte à rebours, historique.
- [x] Examens blancs V2 : minuteur serveur, sauvegarde continue, reprise, remise auto, auto-évaluation.
- [ ] Examens blancs : tester le minuteur sur un vrai téléphone (mise en veille, changement d'onglet).
- [x] QCM V2 : quiz rapide, correction immédiate, révision des erreurs, cohérence des questions, quota prêt.
- [x] QUIZ_GRATUITS_PAR_JOUR = 3 (validé le 27/10).
- [x] Corrigés V2 : rendu Markdown/MathML sûr, badges, filtre, signalement, retrait, aperçu admin.
- [ ] Corrige : décider si on ajoute `verifie_par` (FK utilisateur) pour tracer la vérification.
- [x] V3 : filigrane nominatif et lien temporaire sur le PDF du corrigé Premium (CDC 4).
- [ ] Rendu : les $ à l'intérieur d'un bloc de code sont pris pour des formules (limite connue).
- [x] Affichage MathML vérifié sur Chrome Android (Galaxy A15) : fraction et tableaux OK.
- [ ] Vérifier aussi sur Firefox et sur l'ancien navigateur Samsung Internet.
- [x] V3 module 1 : contributions (envoi de sujets et de corrigés, file de modération, récompense).
- [x] JOURS_OFFERTS_PAR_SUJET = 7 (validé le 27/10). Tant que le paiement est fermé, tout est gratuit : les
      jours offerts aujourd'hui expirent avant l'ouverture du Premium.
- [ ] Contributions : pas de conversion WebP des photos (assemblées en PDF), pas de recadrage automatique.
- [x] Audit de sécurité : limites anti-abus (admin comprise), CSP, adresse d'admin réglable, pip-audit en CI.
- [x] Double authentification de l'équipe ; sauvegardes chiffrées et copiées hors du serveur ; script de
      durcissement du VPS ; refus de l'adresse d'admin par défaut en production.
- [ ] À la mise en ligne : lancer deploy/securiser-serveur.sh (après avoir installé sa clé SSH), créer la phrase
      de sauvegarde et la destination rclone, choisir DJANGO_ADMIN_URL, activer sa double authentification,
      faire une restauration d'essai.
- [x] Pages d'erreur, formulaire de contact, robots.txt et sitemap.xml.
- [x] V3 module 5 : paiement Mobile Money (parcours complet, agrégateur simulé, reçus).
- [ ] Choisir l'agrégateur (Serge Alain) puis écrire sa classe dans paiements/fournisseurs/ (initier, format de sa
      notification, consulter) ; régler PAIEMENT_FOURNISSEUR, PAIEMENT_SECRET, EXPLOITANT_* dans .env.production.
- [ ] Remboursement : aucune procédure dans le site (à traiter à la main, à écrire dans les conditions de vente).
- [x] V3 module 4 : Premium (règle unique, page Offres, protection des PDF de corrigés).
- [x] Prix validés le 27/10 : Pass session 5 000, mensuel 1 500.
- [ ] En production : créer ces deux offres dans l'admin (la commande de démo n'y tourne pas).
- [x] Rappel par e-mail 3 jours avant la fin d'un abonnement ; passage automatique à « expiré » (chaque matin).
- [x] V3 module 3 : codes d'accès (génération par lot, activation, suivi par l'établissement).
- [ ] Codes d'accès : pas de date d'expiration propre au code (il vit tant que la convention est active) ; prix et
      facturation des lots aux IPES hors plateforme (à décider avec Serge Alain).
- [x] V3 module 2 : forum (questions-réponses par matière, signalements, modération).
- [x] Forum : modifier et supprimer ses propres messages.
- [ ] Forum : pas de recherche ni d'abonnement à une discussion (seul l'auteur de la question est prévenu).

## Étude de faisabilité (reporté, « on les fera le moment venu »)

- [ ] Recalculer les scénarios : sans le budget SMS (seuil → 430 abonnés, 0,97 %),
      ajouter un scénario « vente courte » (paiement ouvert fin mars 2027), volume de contenu BTS + HND.
- [ ] Ajouter la question de trésorerie (qui avance les 2,36 M FCFA).
- [ ] Aligner « janvier à juin » sur la règle du Pass (aussi dans les maquettes).
- [ ] Nuancer « textes officiels non protégés » (sujets d'examen) → question au juriste.

## Maquettes

- [x] Groupe A (27/10) : libellés, inscription sans confirmation + œil, paiement, quiz concentré, formules, filtres.
- [x] Groupe B (27/10) : tableau de bord, inscription BTS/HND en cartes, profil en blocs, envoi de sujet.
- [ ] Menu : la maquette nomme « Tableau de bord » et « Examens blancs » dans la barre du haut (connecté).
- [x] Données de démo « [DÉMO] » (27/10) : etudiant.demo@example.com / Demo-BTS-2027, quiz terminé (15/20), examen
      blanc commencé, 3 contributions en attente (dont session 2027 non terminée) ; refusée si DEBUG est faux.
- [ ] Écrans 7, 9, 10 comparés (27/10), écarts à traiter : résultat de quiz par chapitre (barres, conseil, « S'entraîner
      sur … ») ; examen blanc une question à la fois (grille, « Marquer », Précédente/Suivante, heure de sauvegarde) ;
      modération : colonne « Contrôles » en clair (la coche verte de « Doublon ? » signale un doublon : trompeur) et
      « Refuser et supprimer » pour une session non terminée.
- [ ] Plus tard : annonces par e-mail (voir DECISIONS) ; paires BTS ↔ HND (« spécialité équivalente »).
- [ ] Quiz : « Signaler cette question » (maquette) n'existe pas encore.
- [ ] Paiement : préfixe « +237 » affiché devant le champ (maquette) ; aujourd'hui seulement un exemple.

- [ ] Accueil : « télécharger gratuitement » → « avec un compte » (visiteur = téléchargement limité).
- [ ] Mobile : badge « Bientôt » sur l'onglet Entraînement.
- [ ] Écran corrigé : étiqueter « écran V3 ».
- [ ] Texte du Pass : « valable jusqu'à la fin de la session 2027 ».
