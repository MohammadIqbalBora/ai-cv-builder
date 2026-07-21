# This module exposes the Django application to traditional web servers.

"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

# `os` provides access to environment variables.
import os

# This helper builds the callable used by a synchronous WSGI web server.
from django.core.wsgi import get_wsgi_application

# Tell Django where the project settings live unless deployment overrides it.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# A WSGI server imports this callable and forwards HTTP requests into Django.
application = get_wsgi_application()
