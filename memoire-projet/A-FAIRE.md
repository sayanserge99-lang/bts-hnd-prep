# À faire

Mis à jour le 28/10/2026. Ouvert d'abord, dans l'ordre de travail validé par Serge Alain ; ce qui est fait est en bas.

## 1. Préalables à la bêta (Claude, un commit chacun)

- [ ] Brouillons des pages légales FR/EN (confidentialité avec la copie locale des réponses d'examen, conditions
      d'utilisation, mentions légales), champs [À COMPLÉTER] : structure, NIU, adresse, contact, hébergeur.
      Relecture par un juriste avant ouverture.
- [ ] Restauration des sauvegardes : procédure écrite (deploy/DEPLOIEMENT.md §5) à essayer une fois en local.
- [ ] E-mails en production : test d'envoi au démarrage (le fournisseur SMTP reste à choisir, réglages EMAIL_*).
- [ ] Bannière « Bêta » + bouton « Donner mon avis » (formulaire court, enregistré en base, visible de l'admin).
- [ ] Vérifier le suivi des erreurs (Sentry, déjà en place) et la fermeture du paiement (déjà en place) : tests à jour.

## 2. Après les préalables (Claude)

- [ ] Menu : « Tableau de bord » et « Examens blancs » dans la barre du haut (connecté), comme la maquette.
- [ ] Paiement : préfixe « +237 » affiché devant le champ téléphone.
- [ ] Textes : accueil « télécharger gratuitement » → « avec un compte » ; Pass « valable jusqu'à la fin de la
      session 2027 ».
- [ ] Accueil : paires de spécialités BTS ↔ HND (« spécialité équivalente » ; aucun lien en base aujourd'hui).
- [ ] Forum : recherche dans les discussions (puis, plus tard, abonnement à une discussion).

## 3. Pour Serge Alain

- [ ] Essai réel sur téléphone : examen court (mode avion, navigateur fermé, réouverture, fin du temps), minuteur en
      veille / changement d'onglet, mode hors ligne (Galaxy) ; puis Firefox et Samsung Internet.
- [ ] Remplir `contenu/referentiel-a-remplir.xlsx` : sessions 2020-2026 (dates de fin officielles réelles),
      spécialités, matières et coefficients (circulaire du MINESUP, CDC 3.10), chapitres.
- [ ] Choisir l'hébergeur (VPS) et le nom de domaine ; HTTPS Let's Encrypt fait ensemble (procédure non testée).
- [ ] Choisir le fournisseur d'e-mails (SMTP) ; créer le compte Sentry (offre gratuite) ; identifiants Google OAuth.
- [ ] Créer le superutilisateur ; renseigner DJANGO_ADMINS (avis des demandes de retrait).
- [ ] IPES : ville et région de HINTEL, autres IPES, comptes responsables d'IAI-Cameroun et HINTEL, conventions.
- [ ] Faire relire l'anglais par un anglophone (vocabulaire HND), et les épreuves provisoires par un enseignant
      de chaque matière.
- [ ] Remplacer les épreuves provisoires par les vrais sujets (IAI, HINTEL, contributions), matière par matière.
- [ ] Paiement réel : choisir l'agrégateur (puis Claude écrit sa classe dans paiements/fournisseurs/), structure
      au CFCE et NIU, EXPLOITANT_* et PAIEMENT_* dans .env.production ; enquête auprès de 50 étudiants sur le prix
      du Pass (CDC v3, questions ouvertes).

## 4. À la mise en ligne

- [ ] deploy/securiser-serveur.sh (après la clé SSH), phrase de sauvegarde et destination rclone, DJANGO_ADMIN_URL,
      double authentification de l'équipe, restauration d'essai sur le serveur.

## 5. Plus tard (décisions ou limites connues)

- [ ] Remboursement : aucune procédure dans le site (à la main, à écrire dans les conditions de vente).
- [ ] Codes d'accès : pas de date d'expiration propre au code ; prix et facturation des lots aux IPES hors plateforme.
- [ ] Corrigé : ajouter `verifie_par` (qui a vérifié) ?
- [ ] Épreuves internes : pas dans le mode hors ligne, pas d'avis aux étudiants à la publication.
- [ ] Hors ligne : les lectures de PDF hors ligne ne sont pas comptées dans les statistiques.
- [ ] Rendu : les $ dans un bloc de code sont pris pour des formules.
- [ ] Photos de sujets et de contributions : pas de recadrage automatique ni de WebP (retouche manuelle).
- [ ] django-storages si stockage S3 (aujourd'hui : volume Docker `fichiers`).
- [ ] Annonces par e-mail (voir DECISIONS) ; Alpine.js si un jour nécessaire.
- [ ] Brouillons de questions générés par IA depuis le texte du PDF, validés par un enseignant.
- [ ] Étude de faisabilité : recalculer les scénarios (sans budget SMS : seuil 430 abonnés, 0,97 % ; « vente
      courte » fin mars 2027 ; contenu BTS + HND), question de trésorerie (2,36 M FCFA), « janvier à juin » à aligner
      sur la règle du Pass (aussi dans les maquettes), « textes officiels non protégés » → question au juriste.
- [ ] Maquettes (document) : étiqueter l'écran corrigé « écran V3 ».

## Fait

- **Base** : venv, Docker dev et prod (Gunicorn, Nginx, X-Accel-Redirect), PostgreSQL 17, Redis, Celery (texte, OCR,
  compression, index), dépôt GitHub (https://github.com/sayanserge99-lang/bts-hnd-prep), CI (check, migrations,
  pytest, pip-audit, essais JavaScript), sauvegardes chiffrées quotidiennes 30 jours copiées hors serveur (rclone).
- **V1** : comptes (inscription, connexion avec blocage, mot de passe oublié, export, suppression), catalogue,
  recherche plein texte, fiches, favoris, quota visiteurs (3 sujets par jour), règle de publication (test critique),
  import du référentiel et des sujets en lot, pages d'erreur, contact, robots.txt, sitemap, demandes de retrait.
- **V2** : corrigés (rendu sûr, badges, signalement, retrait), QCM et quiz (révision des erreurs, quota 3/jour,
  « Signaler cette question »), examens blancs (minuteur serveur, une question à la fois, verrou à 0:00, marge de 90 s
  pour le transport, bandeau « Connexion perdue », copie locale des réponses), progression, hors ligne (PWA),
  connexion Google (inactive sans identifiants), statistiques, espace établissement et épreuves internes.
- **V3** : contributions et modération (7 jours offerts par sujet validé), forum, codes d'accès des IPES, Premium,
  paiement Mobile Money avec agrégateur simulé (Pass 5 000 et mensuel 1 500 par migration, cumul sans perte,
  confirmation d'un mois acheté pendant un Pass), reçus, rappels, filigrane et liens temporaires des corrigés.
- **Sécurité** : limites anti-abus, CSP, double authentification de l'équipe, adresse d'admin réglable, suivi des
  erreurs Sentry sans données personnelles, paiement fermé tant que structure et NIU sont vides.
- **Bilinguisme** : 1 082 textes traduits, langue de l'examen par défaut, e-mails dans la langue du destinataire,
  test qui échoue sur toute chaîne marquée sans traduction anglaise.
- **Maquettes** : groupes A et B, écrans 7, 9 et 10, données de démo (etudiant.demo@example.com / Demo-BTS-2027),
  examen court de 5 minutes, accès depuis un téléphone du Wi-Fi, 70 épreuves provisoires d'entraînement.
