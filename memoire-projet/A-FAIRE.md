# À faire

Mis à jour le 29/10/2026. Ouvert d'abord, dans l'ordre de travail validé par Serge Alain ; ce qui est fait est en bas.

## 1. Préalables à la bêta (Claude, un commit chacun)

- [x] Brouillons des pages légales FR/EN (confidentialité, conditions d'utilisation, mentions légales), champs
      [À COMPLÉTER] surlignés (28/10). Relecture par un juriste avant ouverture : voir section 3.
- [x] Restauration : deploy/restaurer.sh, essayée en local sur le stack de production (28/10) ; Nginx suit
      l'adresse du conteneur web recréé (défaut trouvé par l'essai).
- [x] E-mails : `manage.py verifier_email` à chaque démarrage de production, alertes check --deploy (28/10).
- [x] Bannière « Bêta » + « Donner mon avis » (AvisBeta, administration) (28/10).
- [x] Sentry sans données personnelles (déjà testé) ; règle de fermeture du paiement testée depuis l'environnement.

## 2. Après les préalables (Claude)

- [x] Menu : « Tableau de bord » et « Examens blancs » dans la barre du haut (dès 1 024 px) (28/10).
- [x] Paiement : « +237 » devant le champ téléphone ; textes de l'accueil et du Pass (28/10).
- [x] Accueil : paires BTS ↔ HND (Specialite.equivalent, colonne facultative du classeur) (28/10).
- [x] Forum : recherche (titres, détails, réponses ; langue de chaque examen) (28/10).
- [x] Recherche : « Vouliez-vous dire … ? » pour les sujets et le forum (29/10).
- [x] CDC 11.1 : enseignant derrière chaque corrigé vérifié (carte avec consentement, initiales, photo) (29/10).
- [x] CDC 11.1 : codes de réduction (réservation atomique, plancher, une utilisation par étudiant) (29/10).
- [x] Menu selon le rôle (Administration, Modération, Mon établissement, Mes corrigés) (29/10).
- [x] Page « Ventes » de l'administrateur (CDC 11.2 avancé) (29/10).
- [ ] Forum : abonnement à une discussion (plus tard).

## 3. Pour Serge Alain

- [x] Essai réel sur le Galaxy (Chrome) : application installée, examen court, coupure, fin du temps, veille (29/10).
- [ ] Même essai sur Firefox et Samsung Internet.
- [ ] Remplir `contenu/referentiel-a-remplir.xlsx` : sessions 2020-2026 (dates de fin officielles réelles),
      spécialités, matières et coefficients (circulaire du MINESUP, CDC 3.10), chapitres.
- [ ] Choisir l'hébergeur (VPS) et le nom de domaine ; HTTPS Let's Encrypt fait ensemble (procédure non testée).
- [ ] Choisir le fournisseur d'e-mails (SMTP) ; créer le compte Sentry (offre gratuite) ; identifiants Google OAuth.
- [ ] Créer le superutilisateur ; renseigner DJANGO_ADMINS (avis des demandes de retrait).
- [ ] Enseignants : créer leur profil enseignant dans l'administration et recueillir leur accord écrit (la case de
      leur page enregistre le consentement) ; sans profil, un compte ne peut pas marquer un corrigé « vérifié ».
- [ ] IPES : ville et région de HINTEL, autres IPES, comptes responsables d'IAI-Cameroun et HINTEL, conventions.
- [ ] Faire relire l'anglais par un anglophone (vocabulaire HND), et les épreuves provisoires par un enseignant
      de chaque matière.
- [ ] Faire relire les pages légales par un juriste et remplir les [À COMPLÉTER] (structure, NIU, RCCM, adresse,
      contact, hébergeur, durées de conservation, autorité de protection des données, âge minimum, licence des
      contributions) ; puis rédiger les conditions de vente (avant l'ouverture du paiement).
- [ ] Remplacer les épreuves provisoires par les vrais sujets (IAI, HINTEL, contributions), matière par matière.
- [ ] Paiement réel : choisir l'agrégateur (puis Claude écrit sa classe dans paiements/fournisseurs/), structure
      au CFCE et NIU, EXPLOITANT_* et PAIEMENT_* dans .env.production (PAIEMENT_PRIX_MINIMUM selon ses frais) ; enquête auprès de 50 étudiants sur le prix
      du Pass (CDC v3, questions ouvertes).

## 4. À la mise en ligne

- [ ] deploy/securiser-serveur.sh (après la clé SSH), phrase de sauvegarde et destination rclone, DJANGO_ADMIN_URL,
      double authentification de l'équipe, restauration d'essai sur le serveur.

## 5. Plus tard (décisions ou limites connues)

- [ ] Remboursement : aucune procédure dans le site (à la main, à écrire dans les conditions de vente).
- [ ] Codes d'accès : pas de date d'expiration propre au code ; prix et facturation des lots aux IPES hors plateforme.
- [ ] Épreuves internes : pas dans le mode hors ligne, pas d'avis aux étudiants à la publication.
- [ ] Hors ligne : les lectures de PDF hors ligne ne sont pas comptées dans les statistiques.
- [ ] Rendu : un bloc de code indenté de 4 espaces n'est pas protégé des formules (utiliser ``` ; corrigé le 29/10
      pour ``` / ~~~ et `en ligne`).
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
