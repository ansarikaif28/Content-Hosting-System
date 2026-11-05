"""
Django settings for the Content Hosting System.

All sensitive values are loaded from environment variables via python-dotenv.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from django.contrib.messages import constants as message_constants


BASE_DIR = Path(__file__).resolve().parent.parent


load_dotenv(BASE_DIR / '.env')


SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-*=zlfjz7h380ez2@olu6(j=6gsb77h)@x#@2e&s0_)5)k@&*5t'
)

DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = os.environ.get(
    'DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1'
).split(',')


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'django_htmx',
    # Local apps
    'users.apps.UsersConfig',
    'content.apps.ContentConfig',
    'audit.apps.AuditConfig',
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
    'django_htmx.middleware.HtmxMiddleware',
]

ROOT_URLCONF = 'config.urls'

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

WSGI_APPLICATION = 'config.wsgi.application'


_db_engine = os.environ.get('DATABASE_ENGINE', 'django.db.backends.sqlite3')
_db_name = os.environ.get('DATABASE_NAME', str(BASE_DIR / 'db.sqlite3'))

DATABASES = {
    'default': {
        'ENGINE': _db_engine,
        'NAME': _db_name if 'sqlite' in _db_engine else _db_name,
        'USER': os.environ.get('DATABASE_USER', ''),
        'PASSWORD': os.environ.get('DATABASE_PASSWORD', ''),
        'HOST': os.environ.get('DATABASE_HOST', ''),
        'PORT': os.environ.get('DATABASE_PORT', ''),
    }
}


AUTH_USER_MODEL = 'users.CustomUser'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/login/'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

#Url

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

#Dir

STORAGE_ROOT = BASE_DIR / os.environ.get('STORAGE_ROOT', 'storage')
WORKING_DIR = BASE_DIR / os.environ.get('WORKING_DIR', 'storage/working')
ARCHIVE_DIR = BASE_DIR / os.environ.get('ARCHIVE_DIR', 'storage/archive')

#Salt value

SALT_VALUE = os.environ.get(
    'SALT_VALUE',
    'default-dev-salt-change-me-in-production' #this can be change when in production
)

#Upload 
MAX_UPLOAD_SIZE_MB = int(os.environ.get('MAX_UPLOAD_SIZE_MB', '500'))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

ALLOWED_FILE_EXTENSIONS = os.environ.get(
    'ALLOWED_FILE_EXTENSIONS',
    '.html,.css,.js,.jpg,.jpeg,.png,.gif,.svg,.ico,.json,.xml,.txt'
).split(',')

#automatic pruning logic default set to 1 yaer
PRUNE_LOG_DAYS = int(os.environ.get('PRUNE_LOG_DAYS', '365'))
PRUNE_ARCHIVE_DAYS = int(os.environ.get('PRUNE_ARCHIVE_DAYS', '365'))

#Email....right now using my personal mail - ansarikaif048@gmail.com

EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend'
)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() in ('true', '1')
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')


MESSAGE_TAGS = {
    message_constants.DEBUG: 'alert-secondary',
    message_constants.INFO: 'alert-info',
    message_constants.SUCCESS: 'alert-success',
    message_constants.WARNING: 'alert-warning',
    message_constants.ERROR: 'alert-danger',
}


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
