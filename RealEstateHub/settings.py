"""
Django settings for RealEstateHub project.
Optimized for performance - Removed all unused/dead configurations
"""

from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ===================================================================
# SECURITY WARNING: keep the secret key used in production secret!
# ===================================================================
SECRET_KEY = 'django-insecure-k#vqkokik41zeh!2_&%bub^8yi10a&_rvta4gfq=bw71287k*i'

# ===================================================================
# DEBUG - Set to False in production!
# ===================================================================
DEBUG = True
ALLOWED_HOSTS = ['*']  # Restrict this in production!

# ===================================================================
# APPLICATION DEFINITION
# ===================================================================
INSTALLED_APPS = [
    'jazzmin',
    
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.humanize',
    
    # Third-party apps - ONLY ACTIVE ONES
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.facebook',
    
    # Local apps
    'estate_app.apps.EstateAppConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'RealEstateHub.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'estate_app.context_processors.user_context',
            ],
        },
    },  
]

WSGI_APPLICATION = 'RealEstateHub.wsgi.application'

# ===================================================================
# DATABASE - SQLite for development, switch to MySQL for production
# ===================================================================
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'nassonline_bhoosparsh',
        'USER': 'nassonline_django',
        'PASSWORD': 'Nassarudeen@2025',
        'HOST': 'localhost',
        'PORT': '3306',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

# ===================================================================
# PASSWORD VALIDATION
# ===================================================================
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# ===================================================================
# INTERNATIONALIZATION
# ===================================================================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ===================================================================
# STATIC & MEDIA FILES
# ===================================================================
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# ===================================================================
# AUTHENTICATION SETTINGS
# ===================================================================
AUTH_USER_MODEL = 'estate_app.CustomUser'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

# Site configuration
SITE_ID = 1

# Authentication backends
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# ===================================================================
# DJANGO-ALLAUTH CONFIGURATION
# ===================================================================
ACCOUNT_USER_MODEL_USERNAME_FIELD = 'email'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_LOGOUT_REDIRECT_URL = '/'
ACCOUNT_SESSION_REMEMBER = True

# Social account providers
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    },
    'facebook': {
        'METHOD': 'oauth2',
        'SCOPE': ['email', 'public_profile'],
        'AUTH_PARAMS': {'auth_type': 'reauthenticate'},
        'FIELDS': ['id', 'first_name', 'last_name', 'email'],
        'EXCHANGE_TOKEN': True,
        'VERSION': 'v13.0',
    }
}

# ===================================================================
# SITE INFORMATION
# ===================================================================
SITE_NAME = 'BHOOSPARSH'
SITE_URL = 'https://bhoosparsh.orobiz.net/'  # Change in production
DEFAULT_FROM_EMAIL = 'jithujp2999@gmail.com'
ADMIN_EMAIL = 'admin@yourdomain.com'

# ===================================================================
# JAZZMIN ADMIN CONFIGURATION
# ===================================================================
JAZZMIN_SETTINGS = {
    "site_title": "BHOOSPARSH Admin",
    "site_header": "BHOOSPARSH Admin Portal",
    "site_brand": "BHOOSPARSH",
    "welcome_sign": "Welcome to BHOOSPARSH Admin Dashboard",
    "copyright": "BHOOSPARSH",
    "site_logo": "images/logo.png",
    "login_logo": None,
    "login_logo_dark": None,
    "theme": "default",
    "show_sidebar": True,
    "navigation_expanded": True,
    "icons": {
        "auth": "fas fa-users",
        "auth.user": "fas fa-user",
        "auth.group": "fas fa-users-cog",
    },
}

# ===================================================================
# EMAIL CONFIGURATION - SMTP for production
# ===================================================================
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = 'smtp.gmail.com'
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = 'jithujp2999@gmail.com'
# EMAIL_HOST_PASSWORD = 'qrou oeqd klna mkvm'
# DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'orobiz.net' 
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'support@orobiz.net'
EMAIL_HOST_PASSWORD = 'Nassonline@2025'
DEFAULT_FROM_EMAIL = 'support@orobiz.net'
SERVER_EMAIL = 'support@orobiz.net'

# Email verification setting - SINGLE SOURCE OF TRUTH
EMAIL_VERIFICATION_REQUIRED = True

# ===================================================================
# SESSION CONFIGURATION
# ===================================================================
SESSION_COOKIE_AGE = 1209600  # 2 weeks in seconds
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = True
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
CSRF_COOKIE_HTTPONLY = False

# ===================================================================
# FILE UPLOAD SETTINGS
# ===================================================================
MAX_UPLOAD_SIZE = 5242880  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755

ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp']
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB

# ===================================================================
# MEMBERSHIP SETTINGS
# ===================================================================
MEMBERSHIP_TRIAL_DAYS = 14
MEMBERSHIP_BASIC_PLAN_SLUG = 'basic'
MEMBERSHIP_PROFESSIONAL_PLAN_SLUG = 'professional'
MEMBERSHIP_ENTERPRISE_PLAN_SLUG = 'enterprise'
ENABLE_PACKAGE_SYSTEM = True
FREE_LISTINGS_FOR_NEW_SELLERS = 1
DEFAULT_LISTING_DURATION = 30  # days

# ===================================================================
# VERIFICATION SETTINGS
# ===================================================================
REQUIRE_PHONE_VERIFICATION_FOR_SELLERS = True
AUTO_APPROVE_VERIFIED_SELLERS = False

# ===================================================================
# CURRENCY
# ===================================================================
DEFAULT_CURRENCY = 'INR'
CURRENCY_SYMBOL = '₹'

# ===================================================================
# SECURITY SETTINGS - Development friendly
# ===================================================================
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# ===================================================================
# CACHE CONFIGURATION - Redis for production
# ===================================================================
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# Uncomment for Redis in production:
# CACHES = {
#     'default': {
#         'BACKEND': 'django_redis.cache.RedisCache',
#         'LOCATION': 'redis://127.0.0.1:6379/1',
#         'OPTIONS': {
#             'CLIENT_CLASS': 'django_redis.client.DefaultClient',
#             'IGNORE_EXCEPTIONS': True,
#         }
#     }
# }

# ===================================================================
# PRODUCTION SETTINGS - Uncomment when deploying
# ===================================================================
# SECURE_SSL_REDIRECT = True
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True
# SECURE_HSTS_SECONDS = 31536000
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# SECURE_HSTS_PRELOAD = True
# SITE_URL = 'https://yourdomain.com'

# ===================================================================
# DATABASE CONFIGURATION FOR PRODUCTION - Uncomment when ready
# ===================================================================
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.mysql',
#         'NAME': 'nassonline_bhoosparsh',
#         'USER': 'nassonline_django',
#         'PASSWORD': 'Nassarudeen@2025',
#         'HOST': 'localhost',
#         'PORT': '3306',
#         'OPTIONS': {
#             'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
#         },
#     }
# }