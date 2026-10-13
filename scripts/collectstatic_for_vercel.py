import os
import sys
from pathlib import Path

import django
from django.core.management import call_command


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

os.environ.pop("VERCEL", None)
for setting in (
    "DATABASE_URL",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "DB_HOST",
    "DB_PORT",
    "AWS_STORAGE_BUCKET_NAME",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_S3_ENDPOINT_URL",
):
    os.environ.pop(setting, None)
os.environ["DJANGO_DEBUG"] = "true"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tracker.settings")

django.setup()

call_command("collectstatic", interactive=False)
