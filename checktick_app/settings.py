# SimpleJWT defaults
from datetime import timedelta
import os
from pathlib import Path

import environ

env = environ.Env(
    DEBUG=(bool, False),
    SECRET_KEY=(str, ""),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    SECURE_SSL_REDIRECT=(bool, False),
    CSRF_TRUSTED_ORIGINS=(list, []),
    BRAND_TITLE=(str, "CheckTick"),
    BRAND_ICON_URL=(str, ""),  # Empty string falls back to checktick.html component
    BRAND_ICON_URL_DARK=(str, ""),  # Optional dark mode icon
    BRAND_ICON_ALT=(str, ""),  # Alt text for icon (defaults to BRAND_TITLE)
    BRAND_ICON_TITLE=(str, ""),  # Title/tooltip for icon (defaults to BRAND_TITLE)
    BRAND_ICON_SIZE_CLASS=(str, ""),  # Tailwind size classes (e.g., "w-8 h-8")
    BRAND_ICON_SIZE=(str, ""),  # Numeric size (e.g., "6" -> "w-6 h-6")
    BRAND_THEME=(str, "checktick-light"),
    BRAND_THEME_PRESET_LIGHT=(
        str,
        "nord",
    ),  # Default daisyUI preset for checktick-light
    BRAND_THEME_PRESET_DARK=(
        str,
        "business",
    ),  # Default daisyUI preset for checktick-dark
    BRAND_FONT_HEADING=(
        str,
        "'IBM Plex Sans', ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, 'Apple Color Emoji', 'Segoe UI Emoji'",
    ),
    BRAND_FONT_BODY=(
        str,
        "Merriweather, ui-serif, Georgia, Cambria, 'Times New Roman', Times, serif",
    ),
    BRAND_FONT_CSS_URL=(
        str,
        "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600;700&family=Merriweather:wght@300;400;700&display=swap",
    ),
    BRAND_THEME_CSS_LIGHT=(str, ""),  # Custom CSS for light theme
    BRAND_THEME_CSS_DARK=(str, ""),  # Custom CSS for dark theme
    HCAPTCHA_SITEKEY=(str, ""),
    HCAPTCHA_SECRET=(str, ""),
    # OIDC Configuration
    OIDC_RP_CLIENT_ID_AZURE=(str, ""),
    OIDC_RP_CLIENT_SECRET_AZURE=(str, ""),
    OIDC_OP_TENANT_ID_AZURE=(str, ""),
    OIDC_RP_CLIENT_ID_GOOGLE=(str, ""),
    OIDC_RP_CLIENT_SECRET_GOOGLE=(str, ""),
    OIDC_RP_SIGN_ALGO=(str, "RS256"),
    OIDC_OP_JWKS_ENDPOINT_GOOGLE=(str, "https://www.googleapis.com/oauth2/v3/certs"),
    OIDC_OP_JWKS_ENDPOINT_AZURE=(str, ""),
    SITE_URL=(str, "http://localhost:8000"),
    # Payment Processing (Paddle)
    PAYMENT_PROCESSING_SANDBOX_API_KEY=(str, ""),
    PAYMENT_PROCESSING_PRODUCTION_API_KEY=(str, ""),
    PAYMENT_PROCESSING_SANDBOX_CLIENT_TOKEN=(str, ""),
    PAYMENT_PROCESSING_PRODUCTION_CLIENT_TOKEN=(str, ""),
    PAYMENT_PROCESSING_SANDBOX_WEBHOOK_SECRET=(str, ""),
    PAYMENT_PROCESSING_PRODUCTION_WEBHOOK_SECRET=(str, ""),
    PAYMENT_PROCESSING_SANDBOX_BASE_URL=(
        str,
        "https://sandbox-api.paddle.com",
    ),
    PAYMENT_PROCESSING_PRODUCTION_BASE_URL=(str, "https://api.paddle.com"),
    # Payment Product IDs (Sandbox)
    PAYMENT_PRICE_ID_PRO_SANDBOX=(str, ""),
    PAYMENT_PRICE_ID_TEAM_SMALL_SANDBOX=(str, ""),
    PAYMENT_PRICE_ID_TEAM_MEDIUM_SANDBOX=(str, ""),
    PAYMENT_PRICE_ID_TEAM_LARGE_SANDBOX=(str, ""),
    PAYMENT_PRICE_ID_ORGANIZATION_SANDBOX=(str, ""),
    PAYMENT_PRICE_ID_ENTERPRISE_SANDBOX=(str, ""),
    # Production
    PAYMENT_PRICE_ID_PRO_PRODUCTION=(str, ""),
    PAYMENT_PRICE_ID_TEAM_SMALL_PRODUCTION=(str, ""),
    PAYMENT_PRICE_ID_TEAM_MEDIUM_PRODUCTION=(str, ""),
    PAYMENT_PRICE_ID_TEAM_LARGE_PRODUCTION=(str, ""),
    PAYMENT_PRICE_ID_ORGANIZATION_PRODUCTION=(str, ""),
    PAYMENT_PRICE_ID_ENTERPRISE_PRODUCTION=(str, ""),
)

BASE_DIR = Path(__file__).resolve().parent.parent
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(env_file)

DEBUG = env("DEBUG")
SECRET_KEY = env("SECRET_KEY") or os.urandom(32)
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# Self-hosted mode - gives all users Enterprise features
SELF_HOSTED = env.bool("SELF_HOSTED", default=False)

DATABASES = {
    "default": env.db("DATABASE_URL"),
}

# Branding and theming settings
BRAND_TITLE = env("BRAND_TITLE")
BRAND_ICON_URL = env("BRAND_ICON_URL") or None
BRAND_ICON_URL_DARK = env("BRAND_ICON_URL_DARK") or None
BRAND_ICON_ALT = env("BRAND_ICON_ALT") or None
BRAND_ICON_TITLE = env("BRAND_ICON_TITLE") or None
BRAND_ICON_SIZE_CLASS = env("BRAND_ICON_SIZE_CLASS") or None
BRAND_ICON_SIZE = env("BRAND_ICON_SIZE") or None
BRAND_THEME = env("BRAND_THEME")
BRAND_THEME_PRESET_LIGHT = env("BRAND_THEME_PRESET_LIGHT")
BRAND_THEME_PRESET_DARK = env("BRAND_THEME_PRESET_DARK")
BRAND_FONT_HEADING = env("BRAND_FONT_HEADING")
BRAND_FONT_BODY = env("BRAND_FONT_BODY")
BRAND_FONT_CSS_URL = env("BRAND_FONT_CSS_URL")
BRAND_THEME_CSS_LIGHT = env("BRAND_THEME_CSS_LIGHT") or None
BRAND_THEME_CSS_DARK = env("BRAND_THEME_CSS_DARK") or None
SITE_URL = "http://localhost:8000" if DEBUG else env("SITE_URL")

# Payment Processing Configuration
# Use sandbox in DEBUG mode, production otherwise
PAYMENT_API_KEY = (
    env("PAYMENT_PROCESSING_SANDBOX_API_KEY")
    if DEBUG
    else env("PAYMENT_PROCESSING_PRODUCTION_API_KEY")
)
PAYMENT_BASE_URL = (
    env("PAYMENT_PROCESSING_SANDBOX_BASE_URL")
    if DEBUG
    else env("PAYMENT_PROCESSING_PRODUCTION_BASE_URL")
)
PAYMENT_ENVIRONMENT = "sandbox" if DEBUG else "production"

# Paddle Client-Side Token (for Paddle.js)
# This is different from API key - it's safe to expose in frontend
PAYMENT_CLIENT_TOKEN = (
    env("PAYMENT_PROCESSING_SANDBOX_CLIENT_TOKEN")
    if DEBUG
    else env("PAYMENT_PROCESSING_PRODUCTION_CLIENT_TOKEN")
)

# Paddle Webhook Secret (for signature verification)
# Get this from Paddle Dashboard -> Developer Tools -> Notifications
PAYMENT_WEBHOOK_SECRET = (
    env("PAYMENT_PROCESSING_SANDBOX_WEBHOOK_SECRET")
    if DEBUG
    else env("PAYMENT_PROCESSING_PRODUCTION_WEBHOOK_SECRET")
)

# Paddle Price IDs (environment-specific)
# These are Price IDs (pri_*), not Product IDs (pro_*)
# Automatically selected based on DEBUG setting
PAYMENT_PRICE_IDS = {
    "pro": (
        env("PAYMENT_PRICE_ID_PRO_SANDBOX")
        if DEBUG
        else env("PAYMENT_PRICE_ID_PRO_PRODUCTION")
    ),
    "team_small": (
        env("PAYMENT_PRICE_ID_TEAM_SMALL_SANDBOX")
        if DEBUG
        else env("PAYMENT_PRICE_ID_TEAM_SMALL_PRODUCTION")
    ),
    "team_medium": (
        env("PAYMENT_PRICE_ID_TEAM_MEDIUM_SANDBOX")
        if DEBUG
        else env("PAYMENT_PRICE_ID_TEAM_MEDIUM_PRODUCTION")
    ),
    "team_large": (
        env("PAYMENT_PRICE_ID_TEAM_LARGE_SANDBOX")
        if DEBUG
        else env("PAYMENT_PRICE_ID_TEAM_LARGE_PRODUCTION")
    ),
    "organization": (
        env("PAYMENT_PRICE_ID_ORGANIZATION_SANDBOX")
        if DEBUG
        else env("PAYMENT_PRICE_ID_ORGANIZATION_PRODUCTION")
    ),
    "enterprise": (
        env("PAYMENT_PRICE_ID_ENTERPRISE_SANDBOX")
        if DEBUG
        else env("PAYMENT_PRICE_ID_ENTERPRISE_PRODUCTION")
    ),
}

INSTALLED_APPS = [
    # Use custom AdminConfig to enforce superuser-only access
    "checktick_app.admin.CheckTickAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "corsheaders",
    "axes",
    "csp",
    "rest_framework",
    "rest_framework_simplejwt",
    "mozilla_django_oidc",
    # Local apps
    "checktick_app.core",
    "checktick_app.surveys",
    "checktick_app.api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "csp.middleware.CSPMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "checktick_app.core.middleware.UserLanguageMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "checktick_app.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "checktick_app" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "checktick_app.context_processors.branding",
                "checktick_app.core.context_processors.tier_info",
            ],
        },
    }
]

WSGI_APPLICATION = "checktick_app.wsgi.application"
ASGI_APPLICATION = "checktick_app.asgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Authentication backends: include AxesStandaloneBackend (renamed in django-axes >= 5.0)
AUTHENTICATION_BACKENDS = [
    # OIDC authentication backends
    "checktick_app.core.auth.CustomOIDCAuthenticationBackend",
    # Prefer the default ModelBackend first so authenticate() can work without a request
    # in test helpers like client.login; Axes middleware and backend will still enforce
    # lockouts for request-aware flows.
    "django.contrib.auth.backends.ModelBackend",
    "axes.backends.AxesStandaloneBackend",
]

LANGUAGE_CODE = "en-gb"

# Supported languages
LANGUAGES = [
    ("en", "English"),
    ("en-gb", "English (UK)"),
    ("cy", "Cymraeg (Welsh)"),
    ("fr", "Français (French)"),
    ("es", "Español (Spanish)"),
    ("de", "Deutsch (German)"),
    ("it", "Italiano (Italian)"),
    ("pt", "Português (Portuguese)"),
    ("pl", "Polski (Polish)"),
    ("ar", "العربية (Arabic)"),
    ("zh-hans", "简体中文 (Simplified Chinese)"),
    ("hi", "हिन्दी (Hindi)"),
    ("ur", "اردو (Urdu)"),
]

# Directory for translation files
LOCALE_PATHS = [
    BASE_DIR / "locale",
]

TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "checktick_app" / "static"]

# WhiteNoise configuration
WHITENOISE_USE_FINDERS = True
WHITENOISE_MAX_AGE = 31536000 if not DEBUG else 0

# Use same storage backend in dev and production to avoid manifest caching issues
# CompressedStaticFilesStorage provides compression and proper cache headers
# without the manifest hash that was causing stale CSS issues
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

# Media uploads (used for admin-uploaded icons if configured)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Security headers
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT")
X_FRAME_OPTIONS = "DENY"
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Forms configuration
# Set default URL scheme to HTTPS for Django 6.0+ compatibility
FORMS_URLFIELD_ASSUME_HTTPS = True

# When running behind a reverse proxy (e.g., Northflank), trust forwarded proto/host
# so Django correctly detects HTTPS and constructs absolute URLs without redirect loops.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

CSP_DEFAULT_SRC = ("'self'",)
CSP_STYLE_SRC = (
    "'self'",
    "'unsafe-inline'",
    # Allow Google Fonts stylesheet
    "https://fonts.googleapis.com",
)
CSP_FONT_SRC = (
    "'self'",
    # Fonts served from Google Fonts
    "https://fonts.gstatic.com",
    "data:",
)
CSP_SCRIPT_SRC = (
    "'self'",
    "https://unpkg.com",
    "https://cdn.jsdelivr.net",
    # hCaptcha widget script
    "https://js.hcaptcha.com",
    # Paddle payment processing
    "https://cdn.paddle.com",
)
CSP_INCLUDE_NONCE_IN = ["script-src"]
CSP_IMG_SRC = ("'self'", "data:")
CSP_STYLE_SRC = (
    "'self'",
    "'unsafe-inline'",
    "https://fonts.googleapis.com",
    # Paddle CDN for checkout styles
    "https://sandbox-cdn.paddle.com",
    "https://cdn.paddle.com",
)
CSP_CONNECT_SRC = (
    "'self'",
    "https://hcaptcha.com",
    "https://*.hcaptcha.com",
    # Paddle API endpoints
    "https://sandbox-api.paddle.com",
    "https://api.paddle.com",
    "https://checkout.paddle.com",
    "https://sandbox-checkout.paddle.com",
    # Paddle CDN for source maps and assets
    "https://cdn.paddle.com",
    "https://sandbox-cdn.paddle.com",
)
CSPO_FRAME_SRC = (
    "'self'",
    "https://hcaptcha.com",
    "https://*.hcaptcha.com",
    # Paddle checkout overlay
    "https://sandbox-checkout.paddle.com",
    "https://checkout.paddle.com",
)
CSP_FRAME_SRC = (
    "'self'",
    "https://hcaptcha.com",
    "https://*.hcaptcha.com",
    # Paddle checkout overlays (buy and checkout domains)
    "https://sandbox-buy.paddle.com",
    "https://buy.paddle.com",
    "https://sandbox-checkout.paddle.com",
    "https://checkout.paddle.com",
)
# Allow Paddle checkout to frame our site for payment processing
CSP_FRAME_ANCESTORS = (
    "'self'",
    "http://localhost:8000" if DEBUG else None,  # For local development
    "https://sandbox-buy.paddle.com",
    "https://buy.paddle.com",
    "https://sandbox-checkout.paddle.com",
    "https://checkout.paddle.com",
)
# Remove None values from tuple
CSP_FRAME_ANCESTORS = tuple(x for x in CSP_FRAME_ANCESTORS if x is not None)

# CORS minimal
CORS_ALLOWED_ORIGINS = []

# Axes configuration for brute-force protection
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # hour
AXES_LOCKOUT_PARAMETERS = ["username"]
# Disable axes for OIDC callbacks to avoid interference
AXES_NEVER_LOCKOUT_WHITELIST = True
AXES_IP_WHITELIST = ["127.0.0.1", "localhost"]
# Use custom lockout template
AXES_LOCKOUT_TEMPLATE = "403_lockout.html"

# Ratelimit example (used in views)
RATELIMIT_ENABLE = True

# Auth redirects
LOGIN_REDIRECT_URL = "/surveys/"  # Changed to surveys for healthcare workflow
LOGOUT_REDIRECT_URL = "/"

# DRF defaults
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/minute",
        "user": "120/minute",
        # Recovery API - strict limits for security-sensitive operations
        "recovery_create": "3/hour",  # Creating recovery requests
        "recovery_approval": "10/hour",  # Admin approval/rejection actions
        "recovery_view": "60/minute",  # Viewing recovery status
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
}

# Disable throttling during tests to prevent rate limit errors
if os.environ.get("PYTEST_CURRENT_TEST"):
    REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []
    RATELIMIT_ENABLE = False

# Email backend
# Use in-memory backend during tests to enable assertions against mail.outbox
if os.environ.get("PYTEST_CURRENT_TEST"):
    EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
elif DEBUG:
    # In development (DEBUG=True), print emails to console
    EMAIL_BACKEND = env(
        "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
    )
else:
    # In production (DEBUG=False), use SMTP (Mailgun or other provider)
    EMAIL_BACKEND = env(
        "EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend"
    )

# Email configuration
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-reply@example.com")
SERVER_EMAIL = env("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)

# SMTP settings for production (Mailgun)
EMAIL_HOST = env("EMAIL_HOST", default="smtp.mailgun.org")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")

# Email timeout
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)

# LLM Configuration for AI Survey Generator
LLM_API_KEY = env("LLM_API_KEY", default="")
LLM_URL = env("LLM_URL", default="")
LLM_AUTH_TYPE = env("LLM_AUTH_TYPE", default="apim")  # 'apim' or 'bearer'
LLM_MODEL = env("LLM_MODEL", default="llama3.2")
LLM_ENABLED = bool(LLM_API_KEY and LLM_URL)
LLM_TIMEOUT = env.int("LLM_TIMEOUT", default=30)  # seconds
LLM_MAX_RETRIES = env.int("LLM_MAX_RETRIES", default=2)
LLM_TEMPERATURE = env.float("LLM_TEMPERATURE", default=0.2)  # Low for consistency

# External Dataset API Configuration
EXTERNAL_DATASET_API_URL = os.environ.get(
    "EXTERNAL_DATASET_API_URL", "https://api.rcpch.ac.uk"
)
EXTERNAL_DATASET_API_KEY = os.environ.get("EXTERNAL_DATASET_API_KEY", "")

# Postcodes API Configuration (for postcode validation)
POSTCODES_API_URL = os.environ.get(
    "POSTCODES_API_URL", "https://api.rcpch.ac.uk/postcodes/postcodes/"
)
POSTCODES_API_KEY = os.environ.get("POSTCODES_API_KEY", "")

# Data Governance Configuration
# These settings control data retention and export policies for GDPR/healthcare compliance
CHECKTICK_DEFAULT_RETENTION_MONTHS = int(
    os.environ.get("CHECKTICK_DEFAULT_RETENTION_MONTHS", "6")
)
CHECKTICK_MAX_RETENTION_MONTHS = int(
    os.environ.get("CHECKTICK_MAX_RETENTION_MONTHS", "24")
)
CHECKTICK_DOWNLOAD_LINK_EXPIRY_DAYS = int(
    os.environ.get("CHECKTICK_DOWNLOAD_LINK_EXPIRY_DAYS", "7")
)
# Parse comma-separated list of warning days
CHECKTICK_WARN_BEFORE_DELETION_DAYS = [
    int(d.strip())
    for d in os.environ.get("CHECKTICK_WARN_BEFORE_DELETION_DAYS", "30,7,1").split(",")
    if d.strip()
]

# Logging Configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} {name} {message}",
            "style": "{",
        },
        "simple": {
            "format": "[{levelname}] {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "checktick_app": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        # Email-specific logging
        "checktick_app.core.email_utils": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        # OIDC debugging
        "mozilla_django_oidc": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "checktick_app.core.auth": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

# ===================================================================
# OIDC Configuration for Healthcare SSO (Google + Azure)
# ===================================================================

# Load OIDC credentials from environment
OIDC_RP_CLIENT_ID_AZURE = env("OIDC_RP_CLIENT_ID_AZURE")
OIDC_RP_CLIENT_SECRET_AZURE = env("OIDC_RP_CLIENT_SECRET_AZURE")
OIDC_OP_TENANT_ID_AZURE = env("OIDC_OP_TENANT_ID_AZURE")
OIDC_RP_CLIENT_ID_GOOGLE = env("OIDC_RP_CLIENT_ID_GOOGLE")
OIDC_RP_CLIENT_SECRET_GOOGLE = env("OIDC_RP_CLIENT_SECRET_GOOGLE")
OIDC_RP_SIGN_ALGO = env("OIDC_RP_SIGN_ALGO")
OIDC_OP_JWKS_ENDPOINT_GOOGLE = env("OIDC_OP_JWKS_ENDPOINT_GOOGLE")
OIDC_OP_JWKS_ENDPOINT_AZURE = env("OIDC_OP_JWKS_ENDPOINT_AZURE")

# hCaptcha Configuration
HCAPTCHA_SITEKEY = env("HCAPTCHA_SITEKEY")
HCAPTCHA_SECRET = env("HCAPTCHA_SECRET")

# Dynamic base URL for development vs production
if DEBUG:
    # Local development with Docker
    OIDC_BASE_URL = "http://localhost:8000"
else:
    # Production
    OIDC_BASE_URL = "https://checktick.eatyourpeas.dev"

# OIDC Provider Configuration
OIDC_PROVIDERS = {
    "google": {
        "OIDC_RP_CLIENT_ID": OIDC_RP_CLIENT_ID_GOOGLE,
        "OIDC_RP_CLIENT_SECRET": OIDC_RP_CLIENT_SECRET_GOOGLE,
        "OIDC_OP_AUTHORIZATION_ENDPOINT": "https://accounts.google.com/o/oauth2/v2/auth",
        "OIDC_OP_TOKEN_ENDPOINT": "https://oauth2.googleapis.com/token",
        "OIDC_OP_USER_ENDPOINT": "https://openidconnect.googleapis.com/v1/userinfo",
        "OIDC_OP_JWKS_ENDPOINT": OIDC_OP_JWKS_ENDPOINT_GOOGLE,
        "OIDC_RP_SCOPES": "openid email profile",
    },
    "azure": {
        "OIDC_RP_CLIENT_ID": OIDC_RP_CLIENT_ID_AZURE,
        "OIDC_RP_CLIENT_SECRET": OIDC_RP_CLIENT_SECRET_AZURE,
        "OIDC_OP_AUTHORIZATION_ENDPOINT": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "OIDC_OP_TOKEN_ENDPOINT": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "OIDC_OP_USER_ENDPOINT": "https://graph.microsoft.com/oidc/userinfo",
        "OIDC_OP_JWKS_ENDPOINT": OIDC_OP_JWKS_ENDPOINT_AZURE,
        "OIDC_RP_SCOPES": "openid email profile",
    },
}

# Default OIDC settings (will be overridden by custom backend)
OIDC_RP_CLIENT_ID = OIDC_RP_CLIENT_ID_GOOGLE  # Default to Google
OIDC_RP_CLIENT_SECRET = OIDC_RP_CLIENT_SECRET_GOOGLE
OIDC_OP_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
OIDC_OP_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
OIDC_OP_USER_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"
OIDC_OP_JWKS_ENDPOINT = OIDC_OP_JWKS_ENDPOINT_GOOGLE
OIDC_RP_SCOPES = "openid email profile"
OIDC_RP_SIGN_ALGO = OIDC_RP_SIGN_ALGO

# Dynamic redirect URI based on environment
OIDC_REDIRECT_URI = f"{OIDC_BASE_URL}/oidc/callback/"

# OIDC Behavior Configuration
OIDC_STORE_ACCESS_TOKEN = True
OIDC_STORE_ID_TOKEN = True
OIDC_RENEW_ID_TOKEN_EXPIRY_SECONDS = 15 * 60  # 15 minutes

# Integration with existing encryption system
OIDC_CREATE_USER = True  # Allow creating new users via OIDC

# Use our custom authentication backend for OIDC
OIDC_AUTHENTICATION_BACKEND = "checktick_app.core.auth.CustomOIDCAuthenticationBackend"

# Custom user creation and linking
# OIDC_USERNAME_ALGO = 'checktick_app.core.auth.generate_username'  # Temporarily disable custom username algo

# Login/logout redirect URLs - use surveys page for authenticated clinicians
OIDC_LOGIN_REDIRECT_URL = "/surveys/"  # Redirect to surveys after OIDC login
OIDC_LOGOUT_REDIRECT_URL = "/"  # Where to go after logout

# HashiCorp Vault Configuration
# Required for hierarchical encryption key management
VAULT_ADDR = env("VAULT_ADDR", default="https://vault.checktick.internal:8200")
VAULT_ROLE_ID = env("VAULT_ROLE_ID", default="")
VAULT_SECRET_ID = env("VAULT_SECRET_ID", default="")
PLATFORM_CUSTODIAN_COMPONENT = env("PLATFORM_CUSTODIAN_COMPONENT", default="")
