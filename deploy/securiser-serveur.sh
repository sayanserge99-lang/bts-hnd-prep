#!/bin/sh
# Durcissement du VPS (Ubuntu 24.04), à lancer une fois en root après l'installation, puis sans danger à relancer :
#   sudo sh deploy/securiser-serveur.sh
#
# 1. Pare-feu (ufw) : seuls SSH, HTTP et HTTPS sont ouverts.
# 2. fail2ban : une adresse qui rate 5 connexions SSH en 10 minutes est bannie une heure.
# 3. Mises à jour de sécurité d'Ubuntu installées automatiquement chaque nuit (redémarrage à 4 h si nécessaire ;
#    les conteneurs repartent seuls, restart: unless-stopped).
# 4. SSH : connexion par mot de passe coupée, mais SEULEMENT si une clé SSH est déjà installée (sinon vous
#    seriez enfermé dehors) ; root ne peut plus se connecter avec un mot de passe.
#
# Docker ouvre lui-même les ports qu'il publie, sans passer par ufw : compose.prod.yaml ne publie que Nginx
# (80, et 443 une fois HTTPS installé) ; la base et Redis restent invisibles depuis Internet.
set -eu

PORT_SSH="${PORT_SSH:-22}"

[ "$(id -u)" -eq 0 ] || { echo "À lancer en root : sudo sh deploy/securiser-serveur.sh" >&2; exit 1; }

echo "== Paquets"
apt-get update -q
DEBIAN_FRONTEND=noninteractive apt-get install -y -q ufw fail2ban unattended-upgrades

echo "== Pare-feu"
ufw default deny incoming
ufw default allow outgoing
ufw allow "$PORT_SSH"/tcp comment "SSH"
ufw allow 80/tcp comment "HTTP"
ufw allow 443/tcp comment "HTTPS"
ufw --force enable
ufw status verbose

echo "== fail2ban"
cat > /etc/fail2ban/jail.d/btshnd.local <<EOF
[DEFAULT]
bantime = 1h
findtime = 10m
maxretry = 5

[sshd]
enabled = true
port = $PORT_SSH
backend = systemd
EOF
systemctl enable --now fail2ban
systemctl restart fail2ban

echo "== Mises à jour automatiques"
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF
cat > /etc/apt/apt.conf.d/52btshnd-redemarrage <<'EOF'
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:00";
EOF
systemctl enable --now unattended-upgrades

echo "== SSH"
cles=0
for fichier in /root/.ssh/authorized_keys /home/*/.ssh/authorized_keys; do
    [ -s "$fichier" ] && cles=1
done
if [ "$cles" -eq 1 ]; then
    cat > /etc/ssh/sshd_config.d/50-btshnd.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
EOF
    # Vérifie la configuration avant de recharger : une erreur ici ne coupe pas l'accès.
    sshd -t && systemctl reload ssh
    echo "SSH : connexion par clé uniquement."
else
    echo "ATTENTION : aucune clé SSH installée, la connexion par mot de passe reste ouverte."
    echo "Ajoutez votre clé (ssh-copy-id), puis relancez ce script."
fi

echo "== Terminé. Bannis par fail2ban : fail2ban-client status sshd"
