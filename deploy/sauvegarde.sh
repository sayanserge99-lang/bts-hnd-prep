#!/bin/sh
# Sauvegarde quotidienne de la base et des fichiers, conservée 30 jours (CDC 4).
# Sur le VPS, depuis le dossier du projet, lancée chaque nuit par cron :
#   0 3 * * * cd /srv/bts-hnd-prep && sh deploy/sauvegarde.sh >> /var/log/btshnd-sauvegarde.log 2>&1
set -eu

DESTINATION="${DESTINATION:-./sauvegardes}"
JOURS_DE_CONSERVATION="${JOURS_DE_CONSERVATION:-30}"
COMPOSE="docker compose -f compose.prod.yaml --env-file .env.production"
DATE=$(date +%Y-%m-%d_%H%M)

mkdir -p "$DESTINATION"

# Base : format compressé de pg_dump, restaurable avec pg_restore.
$COMPOSE exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
    > "$DESTINATION/base_$DATE.dump"

# Fichiers (PDF des sujets) : archive du volume monté dans le conteneur web.
$COMPOSE exec -T web tar -czf - -C /app media > "$DESTINATION/fichiers_$DATE.tar.gz"

# Une sauvegarde vide signale un échec silencieux : on s'arrête avec une erreur.
for fichier in "$DESTINATION/base_$DATE.dump" "$DESTINATION/fichiers_$DATE.tar.gz"; do
    [ -s "$fichier" ] || { echo "ERREUR : $fichier est vide" >&2; exit 1; }
done

find "$DESTINATION" -name 'base_*.dump' -mtime +"$JOURS_DE_CONSERVATION" -delete
find "$DESTINATION" -name 'fichiers_*.tar.gz' -mtime +"$JOURS_DE_CONSERVATION" -delete

echo "$(date) sauvegarde OK : base_$DATE.dump, fichiers_$DATE.tar.gz"
