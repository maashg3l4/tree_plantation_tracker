import os
import sys
from pathlib import Path


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tracker.settings")

from tracker.wsgi import application

django_application = application


def application(environ, start_response):
    if os.environ.get("VERCEL"):
        required_settings = (
            "DJANGO_SECRET_KEY",
            "DATABASE_URL",
            "AWS_STORAGE_BUCKET_NAME",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_S3_ENDPOINT_URL",
        )
        missing_settings = [
            name for name in required_settings if not os.environ.get(name)
        ]
        if missing_settings:
            raise RuntimeError(
                "Configure the required Vercel environment variables: "
                + ", ".join(missing_settings)
            )
    return django_application(environ, start_response)


if os.environ.get("VERCEL_RUN_MIGRATIONS", "").lower() == "true":
    from django.core.management import call_command

    call_command("migrate", interactive=False)
