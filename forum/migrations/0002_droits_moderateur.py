"""Le modérateur modère le forum de ses matières (limité ensuite par AffectationModerateur, dans l'admin)."""

from django.contrib.auth.management import create_permissions
from django.db import migrations

DROITS = {"discussion": ["change", "view"], "reponse": ["change", "view"], "signalementforum": ["change", "view"]}


def donner_les_droits(apps, schema_editor):
    configuration = apps.get_app_config("forum")
    configuration.models_module = True
    create_permissions(configuration, apps=apps, verbosity=0)
    configuration.models_module = None
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    moderateur = Group.objects.filter(name="Modérateur").first()
    if moderateur:
        codenames = [f"{action}_{modele}" for modele, actions in DROITS.items() for action in actions]
        moderateur.permissions.add(*Permission.objects.filter(content_type__app_label="forum", codename__in=codenames))


class Migration(migrations.Migration):
    dependencies = [
        ("forum", "0001_initial"),
        ("accounts", "0002_groupes_roles"),
    ]

    operations = [migrations.RunPython(donner_les_droits, migrations.RunPython.noop)]
