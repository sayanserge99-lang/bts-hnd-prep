"""CDC 3.10 : paires de spécialités BTS ↔ HND de la V1, posées si les deux existent et ne sont pas déjà liées.
Les autres paires (V2 et suivantes) se saisissent dans le classeur du référentiel ou l'administration."""

from django.db import migrations

PAIRES = [("CGE", "ACC"), ("BF", "BAF"), ("MCV", "MKT"), ("IG", "SWE")]


def apparier(apps, schema_editor):
    Specialite = apps.get_model("catalogue", "Specialite")
    for code_bts, code_hnd in PAIRES:
        bts = Specialite.objects.filter(examen__code="BTS", code=code_bts, equivalent__isnull=True).first()
        hnd = Specialite.objects.filter(examen__code="HND", code=code_hnd, equivalent__isnull=True).first()
        if bts and hnd:
            Specialite.objects.filter(pk=bts.pk).update(equivalent=hnd)
            Specialite.objects.filter(pk=hnd.pk).update(equivalent=bts)


class Migration(migrations.Migration):
    dependencies = [("catalogue", "0003_specialite_equivalent")]

    # Retour : on garde les liens (le champ disparaît de toute façon avec 0003).
    operations = [migrations.RunPython(apparier, migrations.RunPython.noop)]
