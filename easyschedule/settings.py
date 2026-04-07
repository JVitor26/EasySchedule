from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# 🔐 Segurança (local)
SECRET_KEY = 'django-insecure-!5=_&b*w43*7g8oid=)_4ldm#p((cte)6i2)2w!0-&fk196&9f'

DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1', 'localhost']


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


# 🧠 Middleware (corrigido)
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',

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


# 🗄️ Banco (local)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
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


# 📁 Arquivos estáticos
STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / 'easyschedule' / 'static',
]

# ⚠️ não precisa de STATIC_ROOT no local


# 📁 Uploads
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# 🔑 Login / Logout
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'


# 🔢 PK padrão
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@easyschedule.local')
WHATSAPP_WEBHOOK_URL = os.getenv('WHATSAPP_WEBHOOK_URL', '')