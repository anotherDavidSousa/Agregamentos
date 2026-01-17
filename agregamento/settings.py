"""
Django settings for agregamento project.
"""

from pathlib import Path
import os
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost').split(',')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'agregamento.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'agregamento.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Se você tiver uma pasta static/ com arquivos adicionais
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
] if os.path.exists(os.path.join(BASE_DIR, 'static')) else []

# Configuração do Whitenoise para servir arquivos estáticos
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files (uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Login settings
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

#if not DEBUG:
#    SECURE_SSL_REDIRECT = False  # Mude para True quando tiver HTTPS
#    SESSION_COOKIE_SECURE = True  # Mude para True quando tiver HTTPS
#    CSRF_COOKIE_SECURE = True  # Mude para True quando tiver HTTPS
#    SECURE_BROWSER_XSS_FILTER = True
#    SECURE_CONTENT_TYPE_NOSNIFF = True
#    SECURE_HSTS_SECONDS = 31536000
#    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
#    SECURE_HSTS_PRELOAD = True
#    X_FRAME_OPTIONS = 'DENY'

CSRF_TRUSTED_ORIGINS = [
    'https://agregamentoipatinga.com',
    'https://www.agregamentoipatinga.com',
]

# ============================================================================
# CONFIGURAÇÕES DO GOOGLE SHEETS
# ============================================================================
# Para sincronizar a lista de cavalos com Google Sheets

# Habilita/desabilita a sincronização automática
# Coloque False para desabilitar temporariamente
GOOGLE_SHEETS_ENABLED = config('GOOGLE_SHEETS_ENABLED', default=False, cast=bool)

# Caminho para o arquivo JSON da Service Account do Google
# Exemplo: os.path.join(BASE_DIR, 'credentials', 'service-account.json')
# IMPORTANTE: Coloque o arquivo JSON na pasta do projeto e ajuste o caminho
GOOGLE_SHEETS_CREDENTIALS_PATH = config(
    'GOOGLE_SHEETS_CREDENTIALS_PATH',
    default=os.path.join(BASE_DIR, 'google_credentials.json')
)

# ID da planilha do Google Sheets
# Você encontra o ID na URL da planilha:
# https://docs.google.com/spreadsheets/d/SEU_ID_AQUI/edit
GOOGLE_SHEETS_SPREADSHEET_ID = config('GOOGLE_SHEETS_SPREADSHEET_ID', default='')

# Nome da aba na planilha (padrão: 'Cavalos')
# Se a aba não existir, será criada automaticamente
GOOGLE_SHEETS_WORKSHEET_NAME = config('GOOGLE_SHEETS_WORKSHEET_NAME', default='Cavalos')
