"""
Django settings for RealEstateHub project.
"""

from pathlib import Path
import os

# GDAL_LIBRARY_PATH = r"C:\new\OSGeo4W\bin\gdal312.dll"
# GEOS_LIBRARY_PATH = r"C:\new\OSGeo4W\bin\geos_c.dll"
# os.environ["PATH"] += os.pathsep + r"C:\new\OSGeo4W\bin"

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings
SECRET_KEY = 'django-insecure-k#vqkokik41zeh!2_&%bub^8yi10a&_rvta4gfq=bw71287k*i'
DEBUG = True
ALLOWED_HOSTS = []

# Application definition
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
    'crispy_forms',
    
    # Third-party apps
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.facebook',
    # 'chartjs',
    
    # Local apps
    'estate_app.apps.EstateAppConfig',
    'phonenumber_field',
]

JAZZMIN_SETTINGS = {
    "site_title": "My Admin Panel",
    "site_header": "My Project Admin",
    "site_brand": "MyBrand",
    "welcome_sign": "Welcome to Admin Dashboard",
    "copyright": "My Company",

    # Logo
    "site_logo": "images/logo.png",  # static path
    "login_logo": None,
    "login_logo_dark": None,

    # Theme style
    "theme": "darkly",   # 👈 CHANGE THEME HERE

    # Sidebar
    "show_sidebar": True,
    "navigation_expanded": True,

    # Icons
    "icons": {
        "auth": "fas fa-users",
        "auth.user": "fas fa-user",
        "auth.group": "fas fa-users-cog",
    },
}

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
        'DIRS': [BASE_DIR / 'templates'],  # Add this for global templates
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'RealEstateHub.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation (KEEP ONLY THIS ONE)
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

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static and media files
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Authentication Settings
AUTH_USER_MODEL = 'estate_app.CustomUser'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

# Email Settings (SMTP for production)
# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'  # Commented out for email sending
EMAIL_VERIFICATION_REQUIRED = True

# Site configuration
SITE_ID = 1

# Authentication backends
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Allauth configuration
ACCOUNT_USER_MODEL_USERNAME_FIELD = 'email'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'  # Set to 'optional' for easier testing
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_LOGOUT_REDIRECT_URL = '/'
LOGIN_REDIRECT_URL = '/dashboard/'
ACCOUNT_SESSION_REMEMBER = True

# Social account providers (configure these later)
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

# GeoIP2 settings (for location detection)
GEOIP_PATH = os.path.join(BASE_DIR, 'geoip')

# Site information
SITE_NAME = 'RealEstatePro'
SITE_URL = 'http://localhost:8000'  # Change in production
ADMIN_EMAIL = 'admin@realestatepro.com'

# Cache configuration (simplified for development)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# Session configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.db'  # Simpler for development

# Security settings (less strict for development)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
# Comment these for development:
# CSRF_COOKIE_SECURE = True
# SESSION_COOKIE_SECURE = True
# SECURE_HSTS_SECONDS = 31536000
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# SECURE_HSTS_PRELOAD = True

# Session Settings
SESSION_COOKIE_AGE = 1209600  # 2 weeks in seconds
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True
CSRF_COOKIE_HTTPONLY = False

# File upload settings
MAX_UPLOAD_SIZE = 5242880  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755

# Image upload settings
ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp']
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB

# ==========================
# Razorpay Configuration
# ==========================
RAZORPAY_KEY_ID = 'rzp_test_xxxxxxxxx'
RAZORPAY_KEY_SECRET = 'xxxxxxxxxxxxxxxx'
RAZORPAY_WEBHOOK_SECRET = 'xxxxxxxxxxxxxxxx'
RAZORPAY_LIVE_MODE = False


# ==========================
# Membership Settings
# ==========================
MEMBERSHIP_TRIAL_DAYS = 14
MEMBERSHIP_BASIC_PLAN_SLUG = 'basic'
MEMBERSHIP_PROFESSIONAL_PLAN_SLUG = 'professional'
MEMBERSHIP_ENTERPRISE_PLAN_SLUG = 'enterprise'


# ==========================
# Email Configuration
# ==========================
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'jithujp2999@gmail.com'      # replace with your email
EMAIL_HOST_PASSWORD = 'qrou oeqd klna mkvm '   # use App Password (not Gmail login password)
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
ADMIN_EMAIL = 'admin@yourdomain.com'

# Custom admin site
ADMIN_SITE_HEADER = "BHOOSPARSH Admin"
ADMIN_SITE_TITLE = "BHOOSPARSH Admin Portal"
ADMIN_INDEX_TITLE = "Dashboard"

# Email settings for admin
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-password'
DEFAULT_FROM_EMAIL = 'BHOOSPARSH <noreply@bhoosparsh.com>'

# Membership settings
ENABLE_PACKAGE_SYSTEM = True  # Set to False to allow unlimited listings
FREE_LISTINGS_FOR_NEW_SELLERS = 1
DEFAULT_LISTING_DURATION = 30  # days

# Verification settings
REQUIRE_EMAIL_VERIFICATION = True
REQUIRE_PHONE_VERIFICATION_FOR_SELLERS = True
AUTO_APPROVE_VERIFIED_SELLERS = False

# Currency
DEFAULT_CURRENCY = 'INR'
CURRENCY_SYMBOL = '₹'

# Admin permissions
ADMIN_CAN_IMPERSONATE = True
ADMIN_CAN_MANUAL_APPROVE = True
ADMIN_CAN_BULK_EMAIL = True


# ==========================
# Site Configuration
# ==========================
SITE_NAME = 'RealEstatePro'
SITE_URL = 'http://localhost:8000'


# ==========================
# Security Settings
# ==========================
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'


# ==========================
# Cache Configuration
# ==========================
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'IGNORE_EXCEPTIONS': True,
        }
    }
}

1
# ==========================
# Celery Configuration
# ==========================
CELERY_BROKER_URL = 'redis://127.0.0.1:6379/0'
CELERY_RESULT_BACKEND = 'redis://127.0.0.1:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE


