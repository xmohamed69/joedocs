# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.
# Unauthorized copying, distribution, or modification is strictly prohibited.
# See LICENSE for details.

from pathlib import Path
import os
import sys

# ── Base directory ─────────────────────────────────────────────────────────────
# When frozen by PyInstaller, all files are extracted to sys._MEIPASS.
# When running as a normal script, BASE_DIR is the project root (two levels up
# from this file: joedocs/settings.py → joedocs/ → project root).
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

# ── Environment ────────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

from django.utils.translation import gettext_lazy as _

MAINTENANCE_MODE = os.getenv('MAINTENANCE_MODE', 'False').lower() == 'true'

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") + ["healthcheck.railway.app"]
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "docs",
    "website",
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

ROOT_URLCONF = "joedocs.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "joedocs.wsgi.application"

# ── Session persistence ────────────────────────────────────────────────────────
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = True
SESSION_ENGINE = "django.contrib.sessions.backends.db"

# ── Database ───────────────────────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "joedocs_db"),
        "USER": os.getenv("DB_USER", "joedocs_user"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:profile"
LOGOUT_REDIRECT_URL = "accounts:login"

LANGUAGE_CODE = "en"

LANGUAGES = [
    ("en", _("English")),
    ("fr", _("French")),
    ("ar", _("Arabic")),
]

TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Email ──────────────────────────────────────────────────────────────────────
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "joelinkaiofficial@gmail.com")

ORG_REQUEST_RECIPIENTS = os.getenv(
    "ORG_REQUEST_RECIPIENTS", "joelinkaiofficial@gmail.com"
).split(",")

CONTACT_RECIPIENTS = os.getenv(
    "CONTACT_RECIPIENTS",
    os.getenv("ORG_REQUEST_RECIPIENTS", "joelinkaiofficial@gmail.com"),
).split(",")

JOEDOCS_WEBSITE_CREATE_ORG_URL = "http://127.0.0.1:8000/website/create-organization/"
MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

X_FRAME_OPTIONS = 'SAMEORIGIN'

# ── AI settings ───────────────────────────────────────────────────────────────
AI_SERVICE = os.getenv('AI_SERVICE', 'stub')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
GROQ_API_BASE_URL = os.getenv(
    'GROQ_API_BASE_URL',
    'https://api.groq.com/openai/v1/chat/completions'
)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
AI_MODEL = os.getenv('AI_MODEL', 'gemini-2.0-flash')
AI_MAX_TOKENS = int(os.getenv('AI_MAX_TOKENS', '1024'))
AI_TEMPERATURE = float(os.getenv('AI_TEMPERATURE', '0.7'))
AI_ENABLE_METADATA_SUGGESTIONS = os.getenv('AI_ENABLE_METADATA_SUGGESTIONS', 'True').lower() == 'true'
AI_ENABLE_SUMMARIZATION = os.getenv('AI_ENABLE_SUMMARIZATION', 'True').lower() == 'true'
AI_REQUEST_TIMEOUT = int(os.getenv('AI_REQUEST_TIMEOUT', '30'))
AI_CACHE_RESULTS = os.getenv('AI_CACHE_RESULTS', 'True').lower() == 'true'
AI_CACHE_TTL = int(os.getenv('AI_CACHE_TTL', '3600'))
AI_RATE_LIMIT_PER_USER = int(os.getenv('AI_RATE_LIMIT_PER_USER', '100'))

LIBREOFFICE_PATH = os.getenv(
    'LIBREOFFICE_PATH',
    r'C:\Program Files\LibreOffice\program\soffice.exe'
)

CSRF_USE_SESSIONS = False

# ── Railway / production overrides ────────────────────────────────────────────
# These activate automatically when DATABASE_URL is set (Railway injects it).

_database_url = os.getenv("DATABASE_URL")
if _database_url:
    # Only import dj_database_url when actually needed (not installed by default)
    try:
        import dj_database_url
        DATABASES["default"] = dj_database_url.parse(
            _database_url,
            conn_max_age=600,
            conn_health_checks=True,
        )
    except ImportError:
        pass  # Running locally without dj_database_url installed — use DB_* vars above

_is_production = not DEBUG
if _is_production:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# WhiteNoise
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

_railway_host = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
_extra_origins = []
if _railway_host:
    _extra_origins = [f"https://{_railway_host}", f"http://{_railway_host}"]

CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
] + _extra_origins

if _railway_host:
    JOEDOCS_WEBSITE_CREATE_ORG_URL = (
        f"https://{_railway_host}/website/create-organization/"
    )
