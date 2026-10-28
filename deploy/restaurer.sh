#!/bin/sh
# Restauration d'une sauvegarde faite par deploy/sauvegarde.sh : la base ET les fichiers (PDF des sujets, corrigés,
# contributions), à la même date. Depuis le dossier du projet :
#   sh deploy/restaurer.sh 2026-10-28_0300        (les dates disponibles : ls sauvegardes/)
# Depuis la copie hors du serveur, rapatrier d'abord les deux fichiers :
#   rclone copy b2:btshnd-sauvegardes sauvegardes --include "*_2026-10-28_0300.*"
#
# ATTENTION : la base et les fichiers actuels sont REMPLACÉS. Le site est arrêté pendant la restauration
# (quelques minutes), puis redémarré. Confirmation demandée, sauf avec CONFIRMER=oui.
set -eu

DATE="${1:?Usage : sh deploy/restaurer.sh AAAA-MM-JJ_HHMM (dates disponibles : ls sauvegardes/)}"
DESTINATION="${DESTINATION:-./sauvegardes}"
PHRASE="${PHRASE:-/root/.btshnd-sauvegarde-phrase}"
COMPOSE="docker compose -f compose.prod.yaml --env-file .env.production"
BASE="$DESTINATION/base_$DATE.dump.gpg"
FICHIERS="$DESTINATION/fichiers_$DATE.tar.gz.gpg"

for fichier in "$BASE" "$FICHIERS"; do
    [ -s "$fichier" ] || { echo "ERREUR : $fichier introuvable ou vide" >&2; exit 1; }
done
[ -r "$PHRASE" ] || { echo "ERREUR : phrase de chiffrement absente ($PHRASE)" >&2; exit 1; }

if [ "${CONFIRMER:-}" != "oui" ]; then
    printf "Remplacer la base et les fichiers actuels par la sauvegarde du %s ? Tapez oui : " "$DATE"
    read -r reponse
    [ "$reponse" = "oui" ] || { echo "Abandon : rien n'a été modifié."; exit 1; }
fi

umask 077
TEMPORAIRE=$(mktemp -d)
trap 'rm -rf "$TEMPORAIRE"' EXIT  # les copies en clair ne survivent pas au script

# Déchiffrer d'abord : une phrase fausse ou une archive abîmée arrête tout avant de toucher au site.
dechiffrer() {
    gpg --batch --yes --quiet --pinentry-mode loopback --passphrase-file "$PHRASE" --decrypt --output "$2" "$1"
}
dechiffrer "$BASE" "$TEMPORAIRE/base.dump"
dechiffrer "$FICHIERS" "$TEMPORAIRE/fichiers.tar.gz"
gzip -t "$TEMPORAIRE/fichiers.tar.gz"

# Personne n'écrit pendant la restauration : site et worker arrêtés, la base reste allumée.
$COMPOSE stop web worker

# $POSTGRES_USER et $POSTGRES_DB sont voulus tels quels : ils s'évaluent dans le conteneur de la base.
# shellcheck disable=SC2016
$COMPOSE exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --exit-on-error' \
    < "$TEMPORAIRE/base.dump"

# L'archive contient le dossier media/ : on le vide puis on le remplace (le volume est monté sur /app/media).
$COMPOSE run --rm --no-deps -T web sh -c 'find /app/media -mindepth 1 -delete && tar -xzf - -C /app' \
    < "$TEMPORAIRE/fichiers.tar.gz"

$COMPOSE start web worker
echo "$(date) restauration OK : base et fichiers du $DATE"
