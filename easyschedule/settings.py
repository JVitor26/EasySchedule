from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# 🔐 Segurança
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-dev-key')

DEBUG = False

ALLOWED_HOSTS = ['easyschedule-0j0e.onrender.com']

CSRF_TRUSTED_ORIGINS = [
    'https://easyschedule-0j0e.onrender.com'
]


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
MEDIA_ROOT = BASE_DIR / 'media'


# 🔑 Login / Logout
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'


# 🔢 PK padrão
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# 📧 Email
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@easyschedule.local')


# 📲 Integrações
WHATSAPP_WEBHOOK_URL = os.getenv('WHATSAPP_WEBHOOK_URL', '')


# 💳 Stripe
STRIPE_PUBLIC_KEY = os.getenv('STRIPE_PUBLIC_KEY', 'pk_not_configured')
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', 'sk_not_configured')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', 'whsec_not_configured')
STRIPE_API_VERSION = '2026-03-25.dahlia'
STRIPE_DOMAIN_URL = os.getenv('STRIPE_DOMAIN_URL', 'https://easyschedule-0j0e.onrender.com')
STRIPE_DEFAULT_CURRENCY = os.getenv('STRIPE_DEFAULT_CURRENCY', 'brl')


# 🔐 Segurança extra (produção)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
