"""Crée les trois rôles techniques du CDC (section 7) sous forme de groupes Django."""

from django.contrib.auth.management import create_permissions
from django.db import migrations

ETUDIANT = "Étudiant"
MODERATEUR = "Modérateur"
ADMINISTRATEUR = "Administrateur"

# (app, modèle) -> actions autorisées. Les droits Premium et les quotas se vérifient dans les vues.
PERMISSIONS = {
    ETUDIANT: {
        ("sujets", "favori"): ["add", "delete", "view"],
        ("communaute", "contribution"): ["add", "view"],
        ("communaute", "signalement"): ["add"],
    },
    # Limité ensuite aux matières de AffectationModerateur, dans l'admin.
    MODERATEUR: {
        ("catalogue", "examen"): ["view"],
        ("catalogue", "session"): ["view"],
        ("catalogue", "specialite"): ["view"],
        ("catalogue", "matiere"): ["view"],
        ("catalogue", "chapitre"): ["view"],
        ("sujets", "sujet"): ["add", "change", "view"],
        ("sujets", "corrige"): ["add", "change", "view"],
        ("entrainement", "question"): ["add", "change", "view"],
        ("entrainement", "choix"): ["add", "change", "delete", "view"],
        ("entrainement", "quiz"): ["add", "change", "view"],
        ("entrainement", "examenblanc"): ["add", "change", "view"],
        ("communaute", "contribution"): ["change", "view"],
        ("communaute", "signalement"): ["change", "view"],
        ("communaute", "demanderetrait"): ["view"],
    },
}


def creer_groupes(apps, schema_editor):
    # Les permissions ne sont normalement créées qu'après toutes les migrations.
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    for nom, droits in PERMISSIONS.items():
        groupe, _ = Group.objects.get_or_create(name=nom)
        for (app_label, modele), actions in droits.items():
            codenames = [f"{action}_{modele}" for action in actions]
            groupe.permissions.add(
                *Permission.objects.filter(content_type__app_label=app_label, codename__in=codenames)
            )

    administrateur, _ = Group.objects.get_or_create(name=ADMINISTRATEUR)
    administrateur.permissions.set(Permission.objects.all())


def supprimer_groupes(apps, schema_editor):
    apps.get_model("auth", "Group").objects.filter(name__in=[ETUDIANT, MODERATEUR, ADMINISTRATEUR]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("catalogue", "0001_initial"),
        ("communaute", "0001_initial"),
        ("entrainement", "0001_initial"),
        ("paiements", "0001_initial"),
        ("partenaires", "0001_initial"),
        ("sujets", "0001_initial"),
    ]

    operations = [migrations.RunPython(creer_groupes, supprimer_groupes)]
