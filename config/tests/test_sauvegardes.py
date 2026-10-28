"""Sauvegardes et restauration (CDC 4) : garde-fous des scripts de deploy/, essayés en local le 28/10/2026."""

from pathlib import Path

from django.conf import settings

DEPLOY = Path(settings.BASE_DIR) / "deploy"


def test_la_sauvegarde_garde_30_jours_la_base_et_les_fichiers_chiffres():
    script = (DEPLOY / "sauvegarde.sh").read_text(encoding="utf-8")
    assert 'JOURS_DE_CONSERVATION="${JOURS_DE_CONSERVATION:-30}"' in script
    assert "pg_dump" in script and "tar -czf - -C /app media" in script and "--symmetric --cipher-algo AES256" in script


def test_la_restauration_dechiffre_tout_avant_d_arreter_le_site():
    """Une phrase fausse ou une archive abîmée doit tout arrêter avant que le site ne soit touché."""
    script = (DEPLOY / "restaurer.sh").read_text(encoding="utf-8")
    arret = script.index("stop web worker")
    assert script.index('dechiffrer "$BASE"') < arret and script.index('dechiffrer "$FICHIERS"') < arret
    assert script.index("gzip -t") < arret
    assert "pg_restore" in script and "tar -xzf - -C /app" in script and "start web worker" in script
    assert 'CONFIRMER:-}" != "oui"' in script  # remplacer la base demande de taper « oui »


def test_nginx_relit_l_adresse_du_conteneur_web():
    """Sans cela, après une restauration ou une mise à jour, Nginx visait l'ancienne adresse : erreur 502."""
    conf = (DEPLOY / "nginx.conf").read_text(encoding="utf-8")
    assert "resolver 127.0.0.11" in conf and "server web:8000 resolve;" in conf and "zone django" in conf
