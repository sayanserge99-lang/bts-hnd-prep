"""Tâches de fond (CDC 5) : traitement des PDF, sans ralentir les pages vues par l'étudiant."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("btshnd")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
