from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load only this project's .env to prevent accidental parent-directory overrides.
if os.environ.get("RENDER", "").lower() != "true":
    load_dotenv(BASE_DIR / ".env")


def _env_list(name, default=""):
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _env_bool(name, default=False):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _host_to_csrf_origins(host):
    clean_host = host.strip()
    if not clean_host:
        return []

    wildcard = clean_host.startswith(".")
    if wildcard:
        clean_host = f"*{clean_host}"

    if clean_host in {"localhost", "127.0.0.1"}:
        return [f"http://{clean_host}", f"https://{clean_host}"]

    return [f"https://{clean_host}"]

# 🔐 Segurança
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-dev-key')

DEBUG = os.environ.get("DEBUG", "False").lower() == "true"
APP_LOG_LEVEL = os.environ.get("APP_LOG_LEVEL", "INFO").upper()

ALLOWED_HOSTS = _env_list(
    "ALLOWED_HOSTS",
    "localhost,127.0.0.1",
)

render_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
if render_hostname and render_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_hostname)

# 🔐 CSRF + COOKIES
IS_RENDER = bool(os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip())

CSRF_TRUSTED_ORIGINS = _env_list(
    "CSRF_TRUSTED_ORIGINS",
    "https://easyschedule-0j0e.onrender.com,https://*.onrender.com,http://localhost:8000,http://127.0.0.1:8000",
)

CSRF_COOKIE_SECURE = IS_RENDER
SESSION_COOKIE_SECURE = IS_RENDER

CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"

# 🔧 Aplicações
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'empresas',
    'pessoa',
    'servicos',
    'profissionais',
    'agendamentos',
    'relatorios',
    'dashboard',
    'core',
    'produtos',
]


# 🧠 Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'core.middleware.RequestContextMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # ✅ ESSENCIAL

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',

    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'empresas.middleware.AdminOnlyPlanProfessionalAccessMiddleware',

    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


ROOT_URLCONF = 'easyschedule.urls'


# 🖥️ Templates
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
            BASE_DIR / 'easyschedule' / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'empresas.context_processors.empresa_context',
            ],
        },
    },
]


WSGI_APPLICATION = 'easyschedule.wsgi.application'


# 🗄️ Banco (Render usa DATABASE_URL automaticamente)
DATABASES = {
    'default': dj_database_url.parse(
        os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
    )
}


# 🔐 Senhas
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# 🌍 Idioma
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True


# 📁 Arquivos estáticos (PRODUÇÃO)
STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / 'easyschedule' / 'static',
]

STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# 📁 Uploads
MEDIA_URL = '/media/'


def _ensure_writable_dir(path_obj):
    try:
        path_obj.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None

    if os.access(path_obj, os.W_OK):
        return path_obj
    return None


def _resolve_media_root():
    fallback_local = BASE_DIR / "media"

    explicit_media_root = os.environ.get("MEDIA_ROOT", "").strip()
    if explicit_media_root:
        writable = _ensure_writable_dir(Path(explicit_media_root))
        if writable:
            return writable

    render_media_root = os.environ.get("RENDER_MEDIA_ROOT", "").strip()
    if render_media_root:
        writable = _ensure_writable_dir(Path(render_media_root))
        if writable:
            return writable

    render_disk_path = os.environ.get("RENDER_DISK_PATH", "").strip()
    if render_disk_path:
        writable = _ensure_writable_dir(Path(render_disk_path) / "media")
        if writable:
            return writable

    # Only use Render's default persistent path when it is actually writable.
    if IS_RENDER and _ensure_writable_dir(Path("/var/data/media")):
        return Path("/var/data/media")

    # Safe fallback prevents 500 on upload when persistent disk is not mounted.
    return _ensure_writable_dir(fallback_local) or fallback_local


MEDIA_ROOT = _resolve_media_root()


# 🔑 Login / Logout
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/accounts/login-redirect/'    
LOGOUT_REDIRECT_URL = '/accounts/login/'

AUTHENTICATION_BACKENDS = [
    'core.auth_backends.EmailOrUsernameModelBackend',
    'django.contrib.auth.backends.ModelBackend',
]


# 🔢 PK padrão
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# 📧 Email
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', '')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = _env_bool('EMAIL_USE_TLS', True)
EMAIL_USE_SSL = _env_bool('EMAIL_USE_SSL', False)
EMAIL_TIMEOUT = int(os.getenv('EMAIL_TIMEOUT', '15'))
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@easyschedule.local')
SERVER_EMAIL = os.getenv('SERVER_EMAIL', DEFAULT_FROM_EMAIL)


# 📲 Integrações
WHATSAPP_WEBHOOK_URL = os.getenv('WHATSAPP_WEBHOOK_URL', '')


# 💳 Stripe
STRIPE_PUBLIC_KEY = os.getenv('STRIPE_PUBLIC_KEY', 'pk_not_configured')
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', 'sk_not_configured')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', 'whsec_not_configured')
STRIPE_API_VERSION = '2026-03-25.dahlia'
STRIPE_DOMAIN_URL = os.getenv('STRIPE_DOMAIN_URL', 'http://localhost:8000')
STRIPE_DEFAULT_CURRENCY = os.getenv('STRIPE_DEFAULT_CURRENCY', 'brl')
SLOT_HOLD_MINUTES = int(os.getenv('SLOT_HOLD_MINUTES', '10'))


# 🔐 Segurança extra (produção)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = IS_RENDER
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'request_context': {
            '()': 'core.logging_filters.RequestContextFilter',
        },
    },
    'formatters': {
        'standard': {
            'format': '%(asctime)s %(levelname)s [%(name)s] [request_id=%(request_id)s] %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'filters': ['request_context'],
            'formatter': 'standard',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': APP_LOG_LEVEL,
    },
}


SENTRY_DSN = os.getenv("SENTRY_DSN", "").strip()
SENTRY_TRACES_SAMPLE_RATE = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0"))

if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
        send_default_pii=False,
    )
