import os
import sys
from pathlib import Path


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tracker.settings")

from tracker.wsgi import application

if os.environ.get("VERCEL_RUN_MIGRATIONS", "").lower() == "true":
    from django.core.management import call_command

    call_command("migrate", interactive=False)
