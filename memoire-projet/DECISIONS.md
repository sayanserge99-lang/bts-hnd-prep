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
