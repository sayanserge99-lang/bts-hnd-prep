# Serveur d'essai gratuit (Oracle Cloud « Always Free »)

Une répétition complète de la mise en ligne, sans frais : même installation Docker que le vrai site
(`DEPLOIEMENT.md`), avec `DJANGO_SERVEUR_ESSAI=1`. Le jour du VPS payant, on refait les mêmes étapes.

> Pas encore essayé sur Oracle : les points marqués **(à vérifier ensemble)** se valident la première fois.

**Règle du serveur d'essai** : comptes fictifs ou testeurs connus et prévenus. Pas d'inscriptions publiques ni de
vraies données d'étudiants : le serveur est hors du Cameroun et les pages légales sont en brouillon (CDC 10.2).

## 1. Le compte (Serge Alain)

1. Créer le compte sur oracle.com/cloud/free (carte demandée pour la vérification, rien n'est débité).
2. **Région d'origine** : Europe (Paris ou Marseille), en général la plus rapide depuis le Cameroun.
   Ce choix est définitif.
3. Une adresse gratuite sur duckdns.org (connexion Google) : par exemple `btshndprep.duckdns.org`.

## 2. La machine

Depuis le PC, une clé SSH (une seule fois) :

```sh
ssh-keygen -t ed25519 -C "serveur-essai-btshnd"   # garder le chemin proposé ; une phrase de passe est conseillée
cat ~/.ssh/id_ed25519.pub                          # à coller dans Oracle à l'étape suivante
```

Dans la console Oracle, **Compute → Instances → Create instance** :

| Réglage | Valeur |
|---|---|
| Image | Canonical Ubuntu 24.04 (aarch64) |
| Shape | `VM.Standard.A1.Flex` (Ampere), **2 OCPU, 12 Go** (tout le quota gratuit) |
| Réseau | VCN créé par défaut, sous-réseau public, adresse IPv4 publique attribuée |
| Clé SSH | coller le contenu de `id_ed25519.pub` |
| Disque de démarrage | 50 Go (gratuit jusqu'à 200 Go au total) |

« Out of capacity » : réessayer plus tard ou choisir un autre domaine de disponibilité.

Noter l'**adresse IP publique**, puis sur duckdns.org la faire pointer vers elle.

## 3. Ouvrir les ports 80 et 443 (deux pare-feu chez Oracle)

1. **Pare-feu du réseau** : *Networking → Virtual Cloud Networks → (le VCN) → Security Lists → Default* →
   *Add Ingress Rules* : source `0.0.0.0/0`, TCP, port de destination `80`, puis une seconde règle pour `443`.
2. **Pare-feu de la machine** : les images Ubuntu d'Oracle bloquent tout sauf SSH (règle `REJECT` dans iptables).
   **(à vérifier ensemble)**

   ```sh
   ssh ubuntu@<adresse IP>
   sudo iptables -L INPUT --line-numbers            # repérer le numéro N de la ligne REJECT
   sudo iptables -I INPUT N -p tcp --dport 80 -m state --state NEW -j ACCEPT
   sudo iptables -I INPUT N -p tcp --dport 443 -m state --state NEW -j ACCEPT
   sudo netfilter-persistent save                    # garder les règles après un redémarrage
   ```

   `deploy/securiser-serveur.sh` utilise ufw, qui gère aussi iptables : sur Oracle, on vérifie ensemble s'il faut
   le lancer tel quel ou garder seulement fail2ban, les mises à jour automatiques et le durcissement SSH.
   **(à vérifier ensemble)**

## 4. Installer comme le vrai site

Suivre `DEPLOIEMENT.md`, sections 1 à 5 (Docker, code, secrets, démarrage, HTTPS, sauvegardes), avec dans
`.env.production` :

| Variable | Serveur d'essai |
|---|---|
| `DJANGO_ALLOWED_HOSTS` | `btshndprep.duckdns.org` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://btshndprep.duckdns.org` |
| `DJANGO_SERVEUR_ESSAI` | `1` : bandeau « Serveur d'essai », aucun moteur de recherche, données de démonstration permises |
| `EXPLOITANT_STRUCTURE`, `EXPLOITANT_NIU` | **vides** : le serveur d'essai refuse de démarrer avec le paiement |
| `EMAIL_*` | facultatif ; sans fournisseur, pas d'e-mail (mot de passe oublié inutilisable) |

L'image se construit pour le processeur Arm d'Oracle sans réglage : le Dockerfile choisit la bonne version de
Tailwind (`TARGETARCH`).

## 5. Le contenu de démonstration

```sh
docker compose -f compose.prod.yaml --env-file .env.production exec web python manage.py donnees_demo
```

Les 70 épreuves provisoires, les corrigés, les quiz, l'examen court, l'enseignante et l'étudiante de démonstration.
**Les mots de passe des comptes de démonstration sont tirés au hasard et affichés une seule fois** : les noter.
(Sur Internet, un mot de passe connu de tous ouvrirait l'administration : l'enseignante est modératrice.)

## 6. Passer au vrai serveur

Nouveau serveur (VPS payant), même procédure avec `DJANGO_SERVEUR_ESSAI=0`, le vrai référentiel
(`DEPLOIEMENT.md`, section 6) et les vrais sujets. Rien du serveur d'essai ne se recopie : ni la base, ni les comptes.
