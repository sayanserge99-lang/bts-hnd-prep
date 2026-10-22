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
- **Interface** : Tailwind v4 en exécutable autonome (pas de Node), polices du système, HTMX servi localement ;
  les pages marchent aussi sans JavaScript (formulaire GET classique).
