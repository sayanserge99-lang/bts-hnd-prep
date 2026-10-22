from django.contrib.auth.models import Group, Permission


def synchroniser_administrateur(sender, **kwargs):
    """Après chaque migrate, le groupe Administrateur reçoit aussi les permissions des nouveaux modèles."""
    groupe = Group.objects.filter(name="Administrateur").first()
    if groupe:
        groupe.permissions.set(Permission.objects.all())
