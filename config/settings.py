# This module contains the main Django project settings.

# Read secrets and deployment options from environment variables.
import os
# Build operating-system-independent paths such as BASE_DIR / "templates".
from pathlib import Path

# Convert a DATABASE_URL string into Django's DATABASES dictionary format.
import dj_database_url
# Load local development variables from a .env file when one exists.
from dotenv import load_dotenv

# Load values from a .env file into environment variables during local development.
load_dotenv()

# Resolve this file, move from config/ to the repository root, and store that
# shared base path for template, media, and static-file settings below.
BASE_DIR = Path(__file__).resolve().parent.parent


# --------------------------------------------------
# SECURITY
# --------------------------------------------------
# Use an environment variable for the secret key so it does not live in code.
SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-local-development-key-change-in-production",
)

# DEBUG should be False in production. Defaults to True locally.
# Convert the environment string to lowercase and then to a real Boolean.
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# A list of allowed hosts for production deployment.
# Split a comma-separated environment value into individual host names.
ALLOWED_HOSTS = [
    # Remove spaces around each host before Django compares it to a request.
    host.strip()
    # Use local host names when ALLOWED_HOSTS is not defined.
    for host in os.getenv(
        "ALLOWED_HOSTS",
        "localhost,127.0.0.1",
    ).split(",")
    # Discard empty entries, for example a trailing comma.
    if host.strip()
]


# --------------------------------------------------
# INSTALLED APPS
# --------------------------------------------------
# Django initializes every framework component and local app in this list.
INSTALLED_APPS = [
    # Provides the staff-only database administration interface.
    "django.contrib.admin",
    # Provides users, passwords, permissions, login, and logout.
    "django.contrib.auth",
    # Tracks which installed app owns each type of database model.
    "django.contrib.contenttypes",
    # Stores data associated with a visitor's browser session.
    "django.contrib.sessions",
    # Supports one-time notices displayed after a redirect.
    "django.contrib.messages",
    # Finds and serves CSS, JavaScript, and image assets.
    "django.contrib.staticfiles",
    # Loads registration-related code from the local accounts package.
    "accounts",
    # Loads CVs, cover letters, subscriptions, AI tools, and their routes.
    "resumes",
]


# --------------------------------------------------
# MIDDLEWARE
# --------------------------------------------------
# Middleware wraps every request/response in this exact top-to-bottom order.
MIDDLEWARE = [
    # Adds common HTTP security protections.
    "django.middleware.security.SecurityMiddleware",
    # Lets WhiteNoise serve compressed static assets in deployment.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    # Loads session data before views and authentication need it.
    "django.contrib.sessions.middleware.SessionMiddleware",
    # Applies common URL and response conveniences.
    "django.middleware.common.CommonMiddleware",
    # Rejects forged POST requests using CSRF tokens in forms.
    "django.middleware.csrf.CsrfViewMiddleware",
    # Sets request.user from the current authenticated session.
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Makes Django's one-time message system available to views/templates.
    "django.contrib.messages.middleware.MessageMiddleware",
    # Prevents other sites from embedding these pages in a frame.
    # "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# Begin URL matching with the urlpatterns in config/urls.py.
ROOT_URLCONF = "config.urls"


# --------------------------------------------------
# TEMPLATE SETTINGS
# --------------------------------------------------
# Django supports multiple template engines; this project configures one.
TEMPLATES = [
    {
        # Select Django's built-in template language.
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Search the repository-level templates/ directory.
        "DIRS": [BASE_DIR / "templates"],
        # Also search a templates/ directory inside each installed app.
        "APP_DIRS": True,
        "OPTIONS": {
            # Context processors add values to every rendered template.
            "context_processors": [
                # Expose the current request as `request`.
                "django.template.context_processors.request",
                # Expose `user` and permission information.
                "django.contrib.auth.context_processors.auth",
                # Expose one-time messages created by views.
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# WSGI application for serving the project.
# Deployment imports the `application` object built in config/wsgi.py.
WSGI_APPLICATION = "config.wsgi.application"


# --------------------------------------------------
# DATABASE
# --------------------------------------------------
# Django expects named database connections; `default` is used automatically.
DATABASES = {
    "default": dj_database_url.config(
        # Read the database provider, credentials, and location from deployment.
        # Reuse a connection for ten minutes and require encrypted transport.
        default=os.getenv("DATABASE_URL"), conn_max_age=600, ssl_require=True
    )
}


# --------------------------------------------------
# PASSWORD VALIDATORS
# --------------------------------------------------
# These validators run through UserCreationForm, including RegisterForm.
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# --------------------------------------------------
# INTERNATIONALIZATION
# --------------------------------------------------
# Select US English translations for Django's built-in interface text.
LANGUAGE_CODE = "en-us"
# Store and interpret the project's local time zone as UTC.
TIME_ZONE = "UTC"
# Enable Django's translation machinery.
USE_I18N = True
# Store timezone-aware dates instead of naive date/time values.
USE_TZ = True


# --------------------------------------------------
# MEDIA FILES
# --------------------------------------------------
# Uploaded files are requested through URLs beginning with /media/.
MEDIA_URL = "/media/"
# Uploaded file contents are stored in the repository's media/ directory.
MEDIA_ROOT = BASE_DIR / "media"


# --------------------------------------------------
# DEFAULT PRIMARY KEY FIELD TYPE
# --------------------------------------------------
# Models without an explicit primary key receive a 64-bit integer ID.
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --------------------------------------------------
# AUTH REDIRECTS
# --------------------------------------------------
# After login, send the browser to the site home page.
LOGIN_REDIRECT_URL = "/"
# After logout, send the browser back to the account login page.
LOGOUT_REDIRECT_URL = "/accounts/login/"


# --------------------------------------------------
# EXTERNAL SERVICE KEYS
# --------------------------------------------------
# resumes/ai_service.py uses this credential when making OpenAI requests.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Payment views and webhook handling use these Stripe configuration values.
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")


# --------------------------------------------------
# STATIC FILES
# --------------------------------------------------
# Static assets such as static/css/style.css use the /static/ URL prefix.
STATIC_URL = "/static/"
# collectstatic copies deployable assets into this generated directory.
STATIC_ROOT = BASE_DIR / "staticfiles"
# During development, Django also searches the source static/ directory.
STATICFILES_DIRS = [BASE_DIR / "static"]

# Choose separate storage implementations for uploads and static assets.
STORAGES = {
    # Keep user-uploaded files on the local filesystem.
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    # Fingerprint and compress static files so browsers can cache them safely.
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}


# Security settings used in production only.
if not DEBUG:
    # Trust the deployment proxy's header that identifies HTTPS requests.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # Redirect any direct HTTP request to HTTPS.
    SECURE_SSL_REDIRECT = True
    # Send the login session cookie only over encrypted HTTPS connections.
    SESSION_COOKIE_SECURE = True
    # Send the CSRF protection cookie only over HTTPS as well.
    CSRF_COOKIE_SECURE = True


