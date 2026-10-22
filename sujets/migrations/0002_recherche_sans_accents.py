"""Configuration de recherche française qui ignore les accents : « degressif » trouve « dégressif »."""

from django.contrib.postgres.operations import UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("sujets", "0001_initial")]

    operations = [
        UnaccentExtension(),
        migrations.RunSQL(
            sql=[
                "CREATE TEXT SEARCH CONFIGURATION fr_unaccent (COPY = french);",
                "ALTER TEXT SEARCH CONFIGURATION fr_unaccent "
                "ALTER MAPPING FOR hword, hword_part, word WITH unaccent, french_stem;",
            ],
            reverse_sql="DROP TEXT SEARCH CONFIGURATION IF EXISTS fr_unaccent;",
        ),
    ]
