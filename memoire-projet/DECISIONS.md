# Décisions validées

## Cadrage (cahier des charges v2)

- Django 5.2 LTS, PostgreSQL, Tailwind + HTMX + Alpine.js, Celery + Redis.
- 7 applications : accounts, catalogue, sujets, entrainement, communaute, paiements, partenaires.
- 3 rôles techniques par groupes Django : Étudiant, Modérateur, Administrateur. Pas de champ « rôle ».
  « Premium » = état d'abonnement ; « contributeur » = usage ouvert à tout étudiant.
- V1 : e-mail seulement (pas de SMS). Paiement désactivé tant que structure + NIU absents.
  Fonctionnalités V2/V3 présentes dans le code mais masquées par des drapeaux (`FONCTIONNALITES` dans settings).
- Chaque matière appartient à un seul examen (BTS ≠ HND).

## Règle de publication (exigence la plus critique)

- Un sujet ne peut être publié que si `session.date_fin_officielle < aujourd'hui`
  (le jour de fin lui-même compte encore comme session en cours).
- Appliquée dans `Sujet.save()`, `Sujet.clean()`, `SujetQuerySet.update/bulk_update/bulk_create`
  et l'action admin « Publier ». Couverte par `sujets/tests/test_regle_publication.py`.
- (27/10) La date de fin d'une session qui a des sujets publiés ne peut pas passer à une date à venir
  (`Session.save/clean`, `SessionQuerySet.update`, import du référentiel) : si la date était fausse, on masque
  d'abord les sujets. Filet : `Sujet.objects.publies()` exige aussi `date_fin_officielle < aujourd'hui`, donc un
  sujet n'est jamais montré trop tôt, même si la base était modifiée par un autre chemin.

## Validées le 22/10/2026 (points de l'analyse du CDC v2)

- **Point 5 – Pass session** : couvre la prochaine session de l'examen dont la date de fin
  officielle n'est pas encore passée (`date_fin_officielle >= date d'achat`).
- **Point 6** : la date de fin du Pass est calculée depuis `Session.date_fin_officielle`,
  pas stockée sur l'Offre. La session suivante doit exister en base avant d'ouvrir la vente.
- **Point 7 – Coefficient** : la durée est sur le Sujet (une épreuve = une durée) ;
  le coefficient reste sur `SpecialiteMatiere` et s'affiche selon la spécialité consultée.
- **Point 8** : le type d'épreuve n'est que sur le Sujet.
- **Point 9** : contrainte CHECK « exactement une cible » sur Tentative, Signalement,
  DemandeRetrait, Abonnement.
- **Point 10** : DemandeRetrait.demandeur = nom + e-mail (pas de clé vers Utilisateur).
- **Point 11** : statut « masqué » sur Sujet et Corrigé ; une demande de retrait masque le contenu dès sa création.
- **Point 12** : Quiz → Matière (+ Chapitre facultatif) ; pas de `durée` sur CodeAcces (prise de l'Offre).

## Validées ensuite

- **PostgreSQL uniquement** (22/10/2026) : la base SQLite de secours est retirée, car la recherche
  plein texte (index GIN, unaccent) en dépend. Conforme au CDC (« PostgreSQL comme base unique »).
- **Recherche** : titre et nom de matière pèsent plus (poids A) que le texte extrait (poids C) ;
  chaque mot vaut comme début de mot ; accents ignorés en français ; tous les mots sont exigés.
- **PDF des sujets** : jamais servis par MEDIA_URL ; uniquement par la vue `sujets:pdf`, qui exige le statut publié
  (sinon un sujet non publié serait lisible en devinant son adresse). Testé.
- **Production** : un seul Dockerfile à trois cibles (dev, prod, nginx) ; secrets dans `.env.production` (jamais versionné) ;
  le serveur refuse de démarrer sans DJANGO_SECRET_KEY ; HSTS 1 h au départ, sous-domaines/préchargement à décider.
- **Corrigés** : en V2, le corrigé entier est visible par tous tant que le paiement est fermé ; la coupure
  « début gratuit / suite Premium » s'active seule avec PAIEMENT_ACTIF. Formules en MathML (pas de KaTeX :
  300 Ko de JS en moins). Tout le HTML final passe par nh3 (latex2mathml n'échappe pas 	ext{...}).
- **Réponses aux quiz** : une table `ReponseQuestion` (une ligne par réponse) en plus du JSON de `Tentative`
  (qui garde l'ordre des questions) : nécessaire aux taux de réussite par chapitre (CDC 3.6). Écart assumé au CDC 6.
- **Quiz** : pas de seconde chance après la correction ; la bonne réponse n'est jamais dans la page avant la réponse ;
  quota quotidien seulement une fois le paiement ouvert (comme l'accès partiel aux corrigés).
- **Examens blancs** : l'heure de fin est fixée par le serveur au départ (le temps court pendant une coupure,
  comme le jour de l'examen) ; le navigateur compte à rebours depuis le temps restant envoyé par le serveur ;
  marge de 90 s pour une copie envoyée tard sur une connexion lente. Minuteur en JavaScript simple (pas d'Alpine).
- **Hors ligne** : service worker servi par Django (adresses statiques exactes, version liée aux fichiers) ;
  réseau d'abord, copie gardée en secours ; seules les pages publiques (/ et /sujets/) sont gardées au passage,
  jamais /compte/, /entrainement/ ni /admin/. Un quiz téléchargé contient ses réponses (correction sans réseau) :
  accepté pour de l'entraînement ; le serveur recorrige tout à la synchronisation et compte le quiz dans le quota.
- **Connexion Google** : écrite à la main (OpenID Connect, ~150 lignes) plutôt qu'avec django-allauth, pour garder
  nos pages et imposer le consentement + la spécialité à la première connexion. Signature du jeton non vérifiée
  (reçu directement de Google par HTTPS, OIDC Core 3.1.3.7), contenu vérifié. Lien de compte par e-mail vérifié.
- **Informatique en premier** (Serge Alain, 23/10) : spécialité de lancement ; ordre réglable (`Specialite.ordre`).
- **Établissements** : les quatre usages demandés (profil + stats, épreuves internes, espace établissement, filtre).
  Établissement déclaré par l'étudiant = non vérifié : rien de réservé à un établissement sans validation par lui.
  Statistiques par établissement : administrateur seulement, ordre alphabétique, jamais de classement (CDC 10.6).
- **Espace établissement** (validé par Serge Alain, 23/10) : un responsable par compte, créé par l'administrateur
  (pas d'inscription libre) ; un établissement n'est « confirmé » pour un étudiant que si son responsable l'a validé ;
  publier une épreuve interne exige une convention de partenariat active (et une convention résiliée les masque) ;
  résultats visibles seulement des étudiants confirmés ayant consenti, consentement révocable et gardé (CDC 10.2).
  Les épreuves internes ne sont pas des sujets officiels : la règle de date de fin de session ne les concerne pas.
- **Questions tirées d'un sujet** (23/10) : elles suivent la visibilité du sujet partout (quiz de l'épreuve,
  quiz rapide, révision, hors ligne, compteurs), via un seul filtre ; on peut donc les préparer pendant la session.
  Import CSV : chapitre et sujet doivent exister (pas de création automatique, pour éviter les doublons de frappe).
- **Contributions** (23/10) : un sujet d'une session non terminée est refusé dès l'envoi (et à la validation),
  pas seulement à la publication ; tout rejet supprime le fichier (plus simple que de juger « suspect ») ; une
  contribution validée donne un sujet en brouillon, jamais publié directement. Récompense = abonnement sans offre,
  ajouté après l'abonnement en cours ; pas de récompense pour un corrigé (CDC 3.7 : « pour chaque sujet validé »).
- **Forum** (23/10, CDC muet sur le détail) : modération a posteriori (un message paraît tout de suite), masquage
  automatique à 3 signalements de comptes différents, le modérateur tranche ; lecture publique, écriture avec un
  compte ; pas de fichier joint ni d'image (pas de dépôt de sujet par cette voie) ; discussion liée à un sujet = suit
  sa visibilité. Pas de classement ni de points pour les membres.
- **Codes d'accès** (23/10) : générés par l'administrateur seulement (vendus hors plateforme), utilisables tant que
  la convention est active ; activer un code confirme l'étudiant dans l'établissement (le code en vient), sauf s'il en
  a déclaré un autre ; le responsable voit des compteurs, jamais qui a utilisé quel code.
- **Premium** (23/10) : une seule fonction décide (est_premium) ; le filigrane met l'e-mail du lecteur (identifiant
  lisible, dissuasif) ; le lien du PDF expire après 15 min et ne vaut que pour son compte — expiré, il ramène à la
  fiche qui en donne un neuf (pas d'erreur pour l'étudiant). Les prix viennent de la base, jamais du gabarit.
- **Paiement** (23/10) : construit avec un agrégateur simulé en attendant le choix de Serge Alain ; seule une
  notification signée (ou une consultation directe de l'agrégateur) déclare un paiement réussi, jamais le retour
  du navigateur ; montant fixé par le serveur et revérifié ; un montant différent n'ouvre rien (l'équipe vérifie).
  Numéro de reçu dérivé de la clé du paiement. Le simulateur n'existe qu'avec DEBUG, et le site refuse de démarrer
  en production avec le paiement ouvert sur le simulateur.
- **Sécurité** (23/10) : limites dans le cache Redis (simples, partagées entre processus) plutôt qu'une bibliothèque ;
  le blocage refuse même le bon mot de passe ; « mot de passe oublié » répond toujours pareil (ni limite ni existence
  du compte révélées). CSP stricte pour les scripts, tolérante pour les styles en ligne (barres de progression).
- **Double authentification** (27/10) : obligatoire pour l'équipe, seulement pour l'administration (les étudiants
  ne sont pas concernés) ; TOTP standard (toutes les applications), écrit à la main plutôt qu'avec django-otp
  (pas de modèles ni de pages de plus à maintenir) ; secret en clair dans la base (indispensable au calcul).
  Sauvegardes : chiffrement symétrique GPG (outil présent partout, restauration sans logiciel particulier).
- **Interface** : Tailwind v4 en exécutable autonome (pas de Node), polices du système, HTMX servi localement ;
  les pages marchent aussi sans JavaScript (formulaire GET classique).
- **Valeurs de lancement (27/10, Serge Alain)** : Pass session 5 000 FCFA, Premium mensuel 1 500 FCFA, 3 quiz
  gratuits par jour, 7 jours de Premium par sujet validé. Visiteurs sans compte : 3 sujets différents par jour
  (pas 3 requêtes : un lecteur PDF demande le fichier en plusieurs fois), compteur de session + plafond de 30 par
  adresse IP (un campus partage souvent une adresse ; le but est d'amener au compte gratuit, pas de bloquer).
  La règle de publication passe avant le quota (un sujet non publié reste introuvable).
- **Référentiel par Excel (27/10)** : .xlsx plutôt que CSV (Excel abîme dates et accents des CSV sous Windows,
  listes déroulantes possibles). L'import ne supprime jamais rien (une matière retirée se gère dans l'admin) ;
  une matière est retrouvée par son nom dans la langue de l'examen, sans tenir compte de la casse ni des espaces.
- **Maquettes (27/10, Serge Alain)** : pas de confirmation du mot de passe (œil « Afficher le mot de passe » à la
  place) ; ordre : points 1-6 puis 7-10, un commit par groupe, captures comparées à la maquette ; un Pass session
  finit à la date officielle de fin et ne se rachète pas tant qu'il est actif ; les périodes contiguës (achat, code,
  jours offerts) s'affichent fusionnées ; envoi de sujet : seules les sessions terminées sont proposées, contrôle
  aussi côté serveur, zone « Photographier ou choisir un fichier » (image/*, PDF, plusieurs fichiers).
  Pour plus tard : annonces par e-mail (résumé hebdomadaire au plus, seulement s'il y a du nouveau dans la spécialité,
  tâche Celery, case non cochée, consentement daté et versionné, désinscription en un clic) ; paires BTS ↔ HND
  (champ facultatif « spécialité équivalente », un lien par paire lu dans les deux sens, dans le référentiel).
  Contenu de démo marqué « [DÉMO] », commande refusée en production.
- **Groupe B (27/10)** : la langue d'un nouveau compte est celle de l'interface pendant l'inscription (modifiable
  dans le profil) ; l'examen n'est plus déduit de la spécialité mais choisi (cartes), et les deux doivent concorder.
  Le profil ne montre plus les derniers résultats : ils sont sur le tableau de bord (CDC 3.1), lié depuis le profil.
- **Écrans 7, 9, 10 (27/10, Serge Alain)** : un commit par écran ; contrôles de modération jamais par la couleur
  seule ; une contribution d'une session non terminée ne peut qu'être refusée (aucun « Valider ») ; motifs de refus
  prédéfinis + message ; résultat de quiz par chapitre (ambre sous 50 %) avec le plus faible « à revoir » ; examen
  blanc une question à la fois, sans correction avant la remise, chronomètre sur l'heure du serveur.
  Conseil du résultat : jamais d'affirmation non fondée (« revient souvent dans les sujets ») ; durée estimée
  au rythme de l'étudiant. Marge de transmission de 90 s après l'heure de fin conservée (à confirmer par Serge Alain).
- **GitHub (27/10)** : vérifier le résultat de la CI une seule fois après un envoi, jamais en boucle.
- **Offre mensuelle (27/10, Serge Alain)** : « Premium 30 jours » 1 500 FCFA est gardée (CDC v2 §3.8 : « mensuelle ou
  par session »). Les deux offres de lancement sont créées par la migration `paiements/0005_offres_de_lancement`
  (seulement si absentes, jamais supprimées en retour), plus par `donnees_demo`. Pass et mensuel se cumulent bout à
  bout sans perte de jours (le second commence au lendemain du premier, une seule période affichée) ; un Pass qui ne
  commencerait qu'après la fin de la session est refusé avec un message clair. Tests : un par sens + ce cas limite.
