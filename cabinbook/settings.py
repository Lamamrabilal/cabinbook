from pathlib import Path
from datetime import timedelta
from celery.schedules import crontab
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = os.getenv("DEBUG", "False") == "True"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost").split(",")

# Sentry (monitoring d'erreurs) — désactivé si SENTRY_DSN n'est pas défini
# (dev local). PII désactivée explicitement : l'app manipule des données de
# santé (carte vitale, notes de séance) qui ne doivent pas se retrouver dans
# les rapports d'erreur envoyés à Sentry.
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        environment=os.getenv("SENTRY_ENVIRONMENT", "production" if not DEBUG else "development"),
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        send_default_pii=False,
        include_local_variables=False,
    )

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "django_filters",
    "django_celery_beat",
    # Apps
    "apps.accounts",
    "apps.appointments",
    "apps.notifications",
    "apps.billing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
CORS_ALLOWED_ORIGINS = os.getenv(
    "CORS_ALLOWED_ORIGINS", "http://localhost:5173"
).split(",")

CORS_ALLOW_CREDENTIALS = True

ROOT_URLCONF = "cabinbook.urls"
AUTH_USER_MODEL = "accounts.User"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["POSTGRES_DB"],
        "USER": os.environ["POSTGRES_USER"],
        "PASSWORD": os.environ["POSTGRES_PASSWORD"],
        "HOST": os.getenv("POSTGRES_HOST", "db"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}

# Cache & Celery
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}}
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

CELERY_BEAT_SCHEDULE = {
    "schedule-reminders-daily": {
        "task": "apps.notifications.tasks.schedule_reminders_for_tomorrow",
        "schedule": crontab(hour=10, minute=0),
    },
    "generate-slots-daily": {
        "task": "apps.notifications.tasks.generate_slots_from_availability",
        "schedule": crontab(hour=6, minute=0),
    },
    "sync-google-calendar-busy-periods": {
        "task": "apps.notifications.tasks.sync_busy_periods_from_google",
        "schedule": crontab(minute="*/15"),
    },
    "purge-old-timeslots-daily": {
        "task": "apps.notifications.tasks.purge_old_timeslots",
        "schedule": crontab(hour=3, minute=0),
    },
}

# JWT
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("apps.accounts.authentication.CookieJWTAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

# Stripe
STRIPE_SECRET_KEY = os.environ["STRIPE_SECRET_KEY"]
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICES = {
    "starter": os.getenv("STRIPE_PRICE_STARTER"),
    "pro": os.getenv("STRIPE_PRICE_PRO"),
    "cabinet": os.getenv("STRIPE_PRICE_CABINET"),
}

# Twilio (SMS + WhatsApp)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")
# Numero WhatsApp Business valide sur Twilio (format "+33...", sans prefixe "whatsapp:" - ajoute automatiquement par le code).
# Vide par defaut : les rappels WhatsApp restent inactifs jusqu'a validation
# du sender WhatsApp Business par Twilio (demarche a faire cote Twilio, pas dans le code).
TWILIO_WHATSAPP_FROM_NUMBER = os.getenv("TWILIO_WHATSAPP_FROM_NUMBER", "")

# Email
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@cabinbook.fr")

# Google Calendar (synchro agenda praticien) — identifiants OAuth2 créés
# dans Google Cloud Console (type "Application web"), URI de redirection
# autorisée = GOOGLE_REDIRECT_URI ci-dessous.
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/accounts/calendar/google/callback/"
)

# URL du frontend (utilisée dans les emails, SMS, et redirections Stripe)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# URL de ce backend Django lui-même (sert les pages publiques : booking.html,
# annuaire.html, avis.html). Distincte de FRONTEND_URL qui pointe vers le
# tableau de bord praticien (React), potentiellement hébergé ailleurs.
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000")

# Cle de chiffrement pour les champs sensibles (ex: carte Vitale)
FIELD_ENCRYPTION_KEY = os.environ["FIELD_ENCRYPTION_KEY"]

# Static / Media
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        }
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

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
            ]
        },
    }
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Sécurité production (actifs uniquement si DEBUG=False) ──
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000  # 1 an
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
