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
- **Fin de l'examen blanc (27/10, Serge Alain)** : à 0:00 la copie se ferme dans la page (réponses figées, panneaux
  inertes, toute modification annulée, sauvegarde automatique coupée) et part tout de suite (au retour du réseau si
  hors connexion) ; la marge serveur de 90 s ne sert qu'au transport, puis tout est refusé. Annoncé dans les consignes.
- **Mois pendant un Pass (28/10, Serge Alain)** : avant le paiement, « Votre Pass couvre déjà jusqu'au … Ce mois
  commencerait le …, après la session. » + « Acheter quand même » / « Annuler » ; rien n'est débité sans la
  confirmation. Sens inverse : le seul cas semblable (Pass qui ne commencerait qu'après la session) reste refusé.
- **Connexion perdue à l'examen blanc (28/10, Serge Alain)** : bandeau « Connexion perdue. Vos réponses sont gardées
  sur le téléphone et envoyées dès le retour du réseau. Attention : après la fin du temps, les réponses qui ne sont
  pas arrivées dans les 90 secondes ne sont pas comptées. » ; réponses renvoyées dès le retour du réseau.
- **Cahier des charges v3 (reçu le 28/10)** : §3.8 fixe les deux offres (Pass session 5 000 FCFA jusqu'à la date de
  fin officielle de la session suivante ; « Premium 30 jours » 1 500 FCFA ; périodes bout à bout). Le §6 en ligne
  reprend nos deux choix (28/10) : date de fin du Pass calculée depuis la Session, cible « question » dans
  Signalement. Plus d'écart entre le cahier des charges et le code sur ces points.
- **Copie locale des réponses d'examen blanc (28/10, Serge Alain)** : la phrase du bandeau est rendue vraie.
  IndexedDB, sinon localStorage, une entrée par tentative (identifiant, version, heure de saisie, réponses ; rien
  d'autre), tout sous try/catch (sans stockage, l'examen marche comme avant). Chaque envoi porte un numéro de version ;
  le serveur garde la plus haute reçue (`reponses["version_recue"]`, en-tête `X-Version-Recue`) et la copie s'efface
  jusqu'à elle (pas de comparaison d'horloges). Réouverture : copie plus récente remise dans la page et envoyée.
  Le serveur juge toujours à la réception : après fin + 90 s, refus (409), message « Ces réponses sont arrivées après
  la fin de l'épreuve et n'ont pas été comptées. » sur la page de l'épreuve terminée, puis effacement. Effacée aussi
  après la remise (la page suivante voit la version reçue) et à la déconnexion / suppression du compte.
- **Langue de l'interface (28/10, Serge Alain)** : étudiant HND en anglais par défaut, BTS en français ; la bascule
  reste disponible et prioritaire. Traductions écrites pour des étudiants anglophones camerounais (paper, past papers,
  marking guide, mock exam, session, specialty, subject = matière). Les contenus (sujets, corrigés, questions) ne se
  traduisent pas. Les e-mails partent dans la langue du destinataire. L'outil d'import Excel du référentiel et le
  simulateur de paiement (équipe, développement) restent en français.
- **Épreuves provisoires (28/10, Serge Alain)** : en attendant les vrais sujets, les sujets de démonstration portent des
  épreuves d'entraînement rédigées par l'équipe. Jamais présentées comme officielles : source et en-tête du PDF le
  disent. Aucun sujet copié d'un site tiers (recherche du 28/10 : le MINESUP ne publie pas les sujets ; les recueils
  en ligne sont payants et d'origine inconnue). Les vrais sujets viendront des IPES partenaires et des contributions.
- **Bêta (28/10, Serge Alain)** : préalables avant ouverture : pages légales en brouillon relues par un juriste,
  sauvegarde quotidienne 30 jours avec restauration essayée, e-mails par un fournisseur SMTP à choisir (test
  d'envoi au démarrage), Sentry sans données personnelles, bannière « Bêta » + « Donner mon avis » (sans e-mail
  demandé), paiement fermé sans structure et NIU. HTTPS fait avec Serge Alain une fois l'hébergeur choisi.
- **Signaler une question (27/10)** : entité Signalement (troisième cible, exactement une par signalement), dans la
  file du modérateur de la matière du chapitre ; motif de 10 caractères au moins, 10 par jour et par compte.
- **Évolutions prévues, CDC §11 (29/10, Serge Alain)** : deux ajouts seulement avant la bêta : l'enseignant derrière
  chaque corrigé, et les codes de réduction. Après la bêta, selon les retours : tableau de bord administrateur
  (agrégé, pas d'export nominatif), classement volontaire sous pseudonyme, parrainage plafonné, rappels WhatsApp avec
  consentement séparé. Plus tard : copie corrigée par un enseignant, fiches et planning de révision, cartes mémoire,
  achat de codes en lot par les IPES, séances en direct. Exclu : résultats officiels, taux de réussite annoncé.
- **Enseignant derrière le corrigé (29/10, choix proposés par Claude, appliqués faute d'objection)** : seul un compte
  avec ProfilEnseignant peut passer un corrigé à « vérifié » (sinon « vérifié par » serait faux) ; « vérifié par » et
  la date sont posés par l'administration, effacés si le corrigé quitte « vérifié ». Le consentement est la seule
  source de la visibilité (pas de case « visible » en double). Initiales par défaut. Photo 2 Mo, recadrée 256 px,
  réenregistrée en JPEG sans métadonnées, servie par une vue qui vérifie l'accord (no-store) ; « Tout retirer »
  révoque et efface. Établissement et matières saisis par l'administrateur.
- **Codes de réduction (29/10, validé par Serge Alain)** : réservation atomique de l'utilisation à la commande
  (libérée si le paiement échoue ou expire, confirmée au webhook), car compter seulement au webhook ne peut pas empêcher
  deux paiements simultanés de dépasser la limite ; « établissement facultatif » = étudiants confirmés par
  l'établissement. Plancher PAIEMENT_PRIX_MINIMUM = 500 FCFA par défaut (à ajuster aux frais de l'agrégateur choisi) ;
  offres concernées obligatoires ; limite totale facultative ; un code sans remise réelle (plancher) est refusé.
- **Menu selon le rôle (29/10, Serge Alain)** : un compte sans profil d'étude qui a un rôle d'équipe (staff,
  responsable d'établissement, profil enseignant) n'a pas le menu de l'étudiant (tableau de bord, entraînement,
  examens blancs, offres) : Administration + Statistiques, Modération, Mon établissement, Mes corrigés. « Mon compte »
  au lieu de « Mon espace », sans études, abonnement ni favoris. Rien n'est bloqué : « Voir comme un étudiant » ouvre
  les quiz. Un compte d'équipe qui a aussi un profil d'étude garde le menu de l'étudiant.
- **Page « Ventes » avant la bêta (29/10, Serge Alain)** : CDC 11.2 (tableau de bord administrateur) avancé à sa
  demande. Administrateur seul ; revenus par mois et par offre, payeurs, part qui paie plus d'une fois, étudiants qui
  ont le plus payé, à relancer (fin dans 7 jours), non renouvelés (60 jours), codes de réduction, paiements à
  régulariser. Listes nominatives affichées, jamais exportées (précaution du CDC 11.2). Le classement des étudiants
  les plus actifs reste après la bêta.
- **Serveur d'essai sur Oracle Cloud Always Free (29/10, Serge Alain)** : avant le VPS payant, répétition complète
  de la mise en ligne (Ampere A1 2 OCPU / 12 Go, Ubuntu 24.04, région Europe, adresse DuckDNS). `DJANGO_SERVEUR_ESSAI=1` :
  bandeau, noindex + robots « Disallow: / », données de démonstration permises avec mots de passe tirés au hasard ;
  refus de démarrer si le paiement est configuré. Comptes fictifs ou testeurs connus seulement (serveur hors du
  Cameroun, pages légales en brouillon). Rien ne se recopie vers le vrai serveur.
