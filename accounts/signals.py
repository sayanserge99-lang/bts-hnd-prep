from django.contrib.auth.models import Group, Permission

GROUPES_EQUIPE = ("Modérateur", "Administrateur")


def ouvrir_l_administration(sender, instance, action, reverse, **kwargs):
    """Entrer dans un groupe de l'équipe ouvre l'accès à /admin/ ; le quitter le referme."""
    if reverse or action not in ("post_add", "post_remove", "post_clear") or instance.is_superuser:
        return
    equipe = instance.groups.filter(name__in=GROUPES_EQUIPE).exists()
    if instance.is_staff != equipe:
        instance.is_staff = equipe
        instance.save(update_fields=["is_staff"])


def synchroniser_administrateur(sender, **kwargs):
    """Après chaque migrate, le groupe Administrateur reçoit aussi les permissions des nouveaux modèles."""
    groupe = Group.objects.filter(name="Administrateur").first()
    if groupe:
        groupe.permissions.set(Permission.objects.all())
