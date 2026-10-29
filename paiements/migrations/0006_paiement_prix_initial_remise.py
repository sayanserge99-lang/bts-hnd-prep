"""CDC 11.1 (1/2) : prix initial et remise sur chaque paiement (les anciens : prix = montant payé)."""

from django.db import migrations, models


def prix_initial_des_anciens(apps, schema_editor):
    apps.get_model("paiements", "Paiement").objects.update(prix_initial=models.F("montant"))


class Migration(migrations.Migration):
    dependencies = [("paiements", "0005_offres_de_lancement")]

    operations = [
        migrations.AddField(
            model_name="paiement", name="prix_initial",
            field=models.PositiveIntegerField(default=0, verbose_name="prix de l'offre (FCFA)"), preserve_default=False,
        ),
        migrations.RunPython(prix_initial_des_anciens, migrations.RunPython.noop),
        migrations.AddField(
            model_name="paiement", name="remise",
            field=models.PositiveIntegerField(default=0, verbose_name="remise (FCFA)"),
        ),
    ]
