import os

from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-local-development-key")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get(
    "DJANGO_DEBUG", "false" if os.environ.get("VERCEL") else "true"
).lower() == "true"

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]
if os.environ.get("VERCEL_URL"):
    ALLOWED_HOSTS.append(os.environ["VERCEL_URL"].split(":", 1)[0])
if os.environ.get("VERCEL"):
    ALLOWED_HOSTS.append(".vercel.app")


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    'trees',
    "grove",
    "grove_market",
    "grove_finance",
    "grove_carbon",
    "grove_compliance",
    "ops.apps.OpsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
if not DEBUG:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "tracker.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.csrf",
                "trees.context_processors.mobile_navigation",
                "trees.context_processors.footer_configuration",
            ],
        },
    },
]

WSGI_APPLICATION = "tracker.wsgi.application"


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

if os.environ.get("DATABASE_URL"):
    database_url = urlparse(os.environ["DATABASE_URL"])
    if database_url.scheme not in {"postgres", "postgresql"}:
        raise RuntimeError("DATABASE_URL must use the PostgreSQL protocol.")
    database_options = parse_qs(database_url.query)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(database_url.path.lstrip("/")),
            "USER": unquote(database_url.username or ""),
            "PASSWORD": unquote(database_url.password or ""),
            "HOST": database_url.hostname,
            "PORT": database_url.port or 5432,
            "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", "0")),
            "OPTIONS": {
                "sslmode": database_options.get("sslmode", ["require"])[0],
                "connect_timeout": 10,
            },
        }
    }
elif os.environ.get("DB_NAME"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["DB_NAME"],
            "USER": os.environ.get("DB_USER", ""),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = "en-us"
LANGUAGES = [("en", "English"), ("bn", "বাংলা")]
LOCALE_PATHS = [BASE_DIR / "locale"]
CANOPY_FOOTER_URLS = {
    "facebook": os.environ.get("CANOPY_FACEBOOK_URL", ""),
    "instagram": os.environ.get("CANOPY_INSTAGRAM_URL", ""),
    "x": os.environ.get("CANOPY_X_URL", ""),
    "youtube": os.environ.get("CANOPY_YOUTUBE_URL", ""),
    "linkedin": os.environ.get("CANOPY_LINKEDIN_URL", ""),
    "google_play": os.environ.get("CANOPY_GOOGLE_PLAY_URL", ""),
    "privacy": os.environ.get("CANOPY_PRIVACY_URL", ""),
    "terms": os.environ.get("CANOPY_TERMS_URL", ""),
    "cookies": os.environ.get("CANOPY_COOKIE_POLICY_URL", ""),
    "accessibility": os.environ.get("CANOPY_ACCESSIBILITY_URL", ""),
    "guidelines": os.environ.get("CANOPY_GUIDELINES_URL", ""),
}
CANOPY_SUPPORT_EMAIL = os.environ.get("CANOPY_SUPPORT_EMAIL", "")

TIME_ZONE = "Asia/Dhaka"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedStaticFilesStorage"
        ),
    },
}

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field
LOGIN_URL = '/login/'
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

if os.environ.get("AWS_STORAGE_BUCKET_NAME"):
    if not all(
        os.environ.get(name)
        for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_S3_ENDPOINT_URL")
    ):
        raise RuntimeError(
            "S3-compatible media storage requires bucket, endpoint, access key, and secret key."
        )
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": os.environ["AWS_STORAGE_BUCKET_NAME"],
            "endpoint_url": os.environ["AWS_S3_ENDPOINT_URL"],
            "region_name": os.environ.get("AWS_S3_REGION_NAME", "auto"),
            "access_key": os.environ["AWS_ACCESS_KEY_ID"],
            "secret_key": os.environ["AWS_SECRET_ACCESS_KEY"],
            "default_acl": "private",
            "querystring_auth": True,
            "file_overwrite": False,
            "addressing_style": "path",
            },
    }

PLANTNET_API_KEY = os.environ.get("PLANTNET_API_KEY", "")
PLANTNET_API_URL = os.environ.get("PLANTNET_API_URL", "https://my-api.plantnet.org/v2")
INATURALIST_API_URL = os.environ.get("INATURALIST_API_URL", "https://api.inaturalist.org/v1")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_API_URL = os.environ.get("GEMINI_API_URL", "https://generativelanguage.googleapis.com/v1beta")
GEMINI_VISION_MODEL = os.environ.get("GEMINI_VISION_MODEL", "gemini-2.5-flash")
CRON_SECRET = os.environ.get("CRON_SECRET", "")

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "3600"))
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    CSRF_TRUSTED_ORIGINS = [
        origin.strip()
        for origin in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")
        if origin.strip()
    ]
    if os.environ.get("VERCEL_URL"):
        CSRF_TRUSTED_ORIGINS.append(f"https://{os.environ['VERCEL_URL']}")