from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Charge un fichier .env dans os.environ (zero dependance).

    - Lignes vides et commentaires (#) ignores.
    - Format KEY=VALUE ; les guillemets entourant la valeur sont retires.
    - Les variables deja presentes dans l'environnement ne sont PAS ecrasees
      (l'environnement reel reste prioritaire sur le fichier).
    """
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-dev-secret-key")
DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() in {"1", "true", "yes", "on"}
ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if host.strip()]
# Necessite des qu'on POST depuis une origine non-default (DEBUG=False sur LAN).
# Format attendu : "http://192.168.1.42:8000,http://nom-pc.local:8000"
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.common.apps.CommonConfig",
    "apps.api.apps.ApiConfig",
    "apps.accounts.apps.AccountsConfig",
    "apps.references.apps.ReferencesConfig",
    "apps.hr.apps.HrConfig",
    "apps.projects.apps.ProjectsConfig",
    "apps.activities.apps.ActivitiesConfig",
    "apps.finance.apps.FinanceConfig",
    "apps.reporting.apps.ReportingConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise doit etre place juste apres SecurityMiddleware. Sert les
    # fichiers statiques (Waitress / runserver sans nginx).
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Connexion obligatoire par defaut (deny-by-default) sur tout le site,
    # sauf liste blanche (login, health, static, admin, api). Doit etre APRES
    # AuthenticationMiddleware.
    "apps.common.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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
                "apps.accounts.context_processors.user_access",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "eve_pilot"),
        "USER": os.getenv("POSTGRES_USER", "postgres"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "postgres"),
        "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Dakar"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Assets propres au projet (logo EVE, CSS partage). Les apps continuent
# d'apporter leurs propres static/.
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# WhiteNoise : compression + manifest pour cache busting des statiques.
# Active uniquement hors DEBUG (sinon le manifest casse les rechargements).
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "/connexion/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# --- Email -----------------------------------------------------------------
# Defaut : backend console (les mails sont ecrits dans le terminal, aucun envoi
# reel). Pour activer l'envoi reel via le serveur SMTP d'EVE, renseigner dans
# le fichier .env :
#   EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
#   EMAIL_HOST_USER=alydiouf@eve-sn.org
#   EMAIL_HOST_PASSWORD=...   (jamais commite)
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "vps75468.serveur-vps.net")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "465"))
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "True").lower() in {"1", "true", "yes", "on"}
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "False").lower() in {"1", "true", "yes", "on"}
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10"))
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "EVE Pilot <no-reply@eve-sn.org>")
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

# URL de base utilisee dans les emails pour construire des liens absolus.
SITE_BASE_URL = os.getenv("SITE_BASE_URL", "http://127.0.0.1:8000")

# --- Securite production --------------------------------------------------
# Activee par DJANGO_PROD_SECURITY=True dans le .env de production (derriere
# nginx + TLS). En dev, laisser False : sinon SECURE_SSL_REDIRECT boucle sur
# du HTTP local. Ne jamais mettre DEBUG=True en ligne.
_PROD_SECURITY = os.getenv("DJANGO_PROD_SECURITY", "False").lower() in {"1", "true", "yes", "on"}
if _PROD_SECURITY:
    # nginx termine le TLS et transmet X-Forwarded-Proto : Django sait alors
    # que la requete d'origine est en HTTPS.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    # HSTS : 30 jours pour le test (passer a 31536000 = 1 an une fois stable).
    SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_HSTS_SECONDS", "2592000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = False
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"

# Medias proteges : si True, protected_media delegue le streaming a nginx via
# X-Accel-Redirect (location `internal`). True en production, False en dev.
USE_X_ACCEL_REDIRECT = os.getenv("DJANGO_X_ACCEL_REDIRECT", "False").lower() in {"1", "true", "yes", "on"}

# Limite la taille des uploads en memoire (les gros fichiers vont sur disque).
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("DJANGO_DATA_UPLOAD_MAX", str(10 * 1024 * 1024)))

# Journalisation : tout vers la console (capturee par systemd/journald en prod).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "{asctime} {levelname} {name} {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": os.getenv("DJANGO_LOG_LEVEL", "INFO")},
    "loggers": {
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
}
