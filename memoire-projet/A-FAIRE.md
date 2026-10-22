# À faire

## Fait

- [x] Python installé, venv, dépendances, migrations, `pytest` vert (22/10/2026).
- [x] Migration des groupes Étudiant, Modérateur, Administrateur et leurs permissions.

## Prochain

- [x] `git init` + premier commit (61249a5). Auteur local : Ayoung Sanama Serge Alain <sayanserge99@gmail.com>.
- [x] Dépôt GitHub : https://github.com/sayanserge99-lang/bts-hnd-prep (public). Le remote contient le nom de compte, car Windows a aussi le compte AyounSanama en mémoire.
- [x] GitHub Actions : `.github/workflows/tests.yml` (check, migrations manquantes, pytest sur PostgreSQL 17, Python 3.13).
- [ ] Python 3.15 n'est pas officiellement supporté par Django 5.2 (ça marche, mais) :
      fixer l'image Docker de production sur Python 3.13.

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
- [ ] Établissement dans le profil : à ajouter quand la liste des IPES sera saisie (partenaires.Etablissement).
- [ ] Option « Partager mes résultats avec mon établissement » (CDC 10.6) : avec le tableau de bord IPES (V3).
- [x] Traductions EN : 270 textes traduits, test de complétude.
- [ ] Faire relire les traductions anglaises par un anglophone (vocabulaire HND : « past papers », « marking guide »).
- [ ] Production : lancer `compilemessages` dans le Dockerfile au lieu de versionner le `.mo`.
- [x] Formulaire de demande de retrait (sujets) avec actions d'admin Accepter / Refuser.
- [ ] Rédiger les pages légales (mentions, confidentialité, CGV, contact) : contenu à fournir par Serge Alain / juriste.
- [ ] Renseigner DJANGO_ADMINS dans .env.production pour être prévenu des demandes de retrait.
- [ ] Demande de retrait des corrigés : à ajouter avec les corrigés (V2).
- [ ] Décider le quota de téléchargement des visiteurs (CDC 7 : « limité ») ; aujourd'hui tout est ouvert.
- [ ] Accueil : apparier spécialités BTS ↔ HND comme sur la maquette (aucun lien en base aujourd'hui).
- [ ] Alpine.js : pas encore nécessaire (ajouter quand il le sera : minuteur d'examen blanc, menus).
- [x] Modérateurs limités à leurs matières (liste, fiches, actions, listes de choix), accès admin automatique.
- [ ] V3 : rôle « Établissement » pour le tableau de bord IPES (CDC 10.6), absent des 3 rôles du CDC section 7.
- [ ] Corrige : décider si on ajoute `verifie_par` (FK utilisateur) pour tracer la vérification.
- [ ] Forum (V3) : pas encore modélisé.

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
