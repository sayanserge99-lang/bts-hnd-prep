#!/bin/sh
# Sauvegarde quotidienne de la base et des fichiers, chiffrée, conservée 30 jours, copiée hors du serveur (CDC 4).
# Sur le VPS, depuis le dossier du projet, lancée chaque nuit par cron (voir deploy/DEPLOIEMENT.md, section 5) :
#   0 3 * * * cd /srv/bts-hnd-prep && sh deploy/sauvegarde.sh >> /var/log/btshnd-sauvegarde.log 2>&1
#
# Chiffrement : AES-256 (GPG) avec la phrase du fichier PHRASE (lisible par root seulement). Sans cette phrase,
# une sauvegarde volée ou copiée chez un hébergeur est illisible — mais elle l'est aussi pour vous : gardez-en
# une copie hors du serveur (papier, gestionnaire de mots de passe).
# Copie hors du serveur : si DESTINATION_DISTANTE est réglée (une destination rclone, par exemple
# « b2:btshnd-sauvegardes » ou « gdrive:btshnd »), chaque sauvegarde y est envoyée.
set -eu

DESTINATION="${DESTINATION:-./sauvegardes}"
JOURS_DE_CONSERVATION="${JOURS_DE_CONSERVATION:-30}"
PHRASE="${PHRASE:-/root/.btshnd-sauvegarde-phrase}"
DESTINATION_DISTANTE="${DESTINATION_DISTANTE:-}"
COMPOSE="docker compose -f compose.prod.yaml --env-file .env.production"
DATE=$(date +%Y-%m-%d_%H%M)

[ -r "$PHRASE" ] || { echo "ERREUR : phrase de chiffrement absente ($PHRASE), voir deploy/DEPLOIEMENT.md" >&2; exit 1; }
mkdir -p "$DESTINATION"
umask 077  # fichiers intermédiaires lisibles par root seulement

chiffrer() {
    # Le fichier en clair n'existe que le temps du chiffrement.
    gpg --batch --yes --quiet --pinentry-mode loopback --passphrase-file "$PHRASE" \
        --symmetric --cipher-algo AES256 --output "$1.gpg" "$1"
    rm -f "$1"
    [ -s "$1.gpg" ] || { echo "ERREUR : $1.gpg est vide" >&2; exit 1; }
}

# Base : format compressé de pg_dump, restaurable avec pg_restore.
# $POSTGRES_USER et $POSTGRES_DB sont voulus tels quels : ils s'évaluent dans le conteneur de la base.
# shellcheck disable=SC2016
$COMPOSE exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
    > "$DESTINATION/base_$DATE.dump"
# Fichiers (PDF des sujets, corrigés, contributions) : archive du volume monté dans le conteneur web.
$COMPOSE exec -T web tar -czf - -C /app media > "$DESTINATION/fichiers_$DATE.tar.gz"

# Une sauvegarde vide signale un échec silencieux : on s'arrête avec une erreur.
for fichier in "$DESTINATION/base_$DATE.dump" "$DESTINATION/fichiers_$DATE.tar.gz"; do
    [ -s "$fichier" ] || { echo "ERREUR : $fichier est vide" >&2; exit 1; }
    chiffrer "$fichier"
done

find "$DESTINATION" -name 'base_*.dump.gpg' -mtime +"$JOURS_DE_CONSERVATION" -delete
find "$DESTINATION" -name 'fichiers_*.tar.gz.gpg' -mtime +"$JOURS_DE_CONSERVATION" -delete

if [ -n "$DESTINATION_DISTANTE" ]; then
    rclone copy "$DESTINATION" "$DESTINATION_DISTANTE" --include "*_$DATE.*.gpg"
    rclone delete "$DESTINATION_DISTANTE" --min-age "${JOURS_DE_CONSERVATION}d" --include "*.gpg"
    echo "$(date) copie hors du serveur OK : $DESTINATION_DISTANTE"
else
    echo "ATTENTION : DESTINATION_DISTANTE vide, la sauvegarde reste sur ce serveur seulement." >&2
fi

echo "$(date) sauvegarde OK : base_$DATE.dump.gpg, fichiers_$DATE.tar.gz.gpg"
