"""Offres de lancement validées par Serge Alain le 27/10/2026 : Pass session 5 000 FCFA, Premium 30 jours 1 500 FCFA.

Créées seulement si elles manquent (une base qui les a déjà, ou les a modifiées dans l'admin, n'est pas touchée).
Le retour en arrière ne supprime rien : des paiements et abonnements peuvent y être rattachés.
"""

from django.db import migrations

OFFRES = [
    {"nom": "Pass session", "prix": 5000, "type": "session", "duree_jours": None},
    {"nom": "Premium 30 jours", "prix": 1500, "type": "duree", "duree_jours": 30},
]


def creer(apps, schema_editor):
    Offre = apps.get_model("paiements", "Offre")
    for offre in OFFRES:
        if not Offre.objects.filter(type=offre["type"], nom=offre["nom"]).exists():
            Offre.objects.create(**offre)


class Migration(migrations.Migration):
    dependencies = [("paiements", "0004_abonnement_rappel_envoye_le")]

    operations = [migrations.RunPython(creer, migrations.RunPython.noop)]
