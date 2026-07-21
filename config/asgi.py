# This module exposes the Django application to asynchronous web servers.

"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

# `os` provides access to the process's environment variables.
import os

# This helper constructs the callable used by an asynchronous web server.
from django.core.asgi import get_asgi_application

# Point Django at config/settings.py, unless deployment already set a value.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# An ASGI server imports this callable and passes requests into Django; Django
# then uses config/urls.py to decide which application view handles each one.
application = get_asgi_application()
