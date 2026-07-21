# This module provides Django with configuration for this application.

# AppConfig is Django's base class for application metadata.
from django.apps import AppConfig


# Django loads this configuration because `accounts` is in INSTALLED_APPS.
class AccountsConfig(AppConfig):
    # New database models use 64-bit automatically generated primary keys.
    default_auto_field = "django.db.models.BigAutoField"
    # This is the Python package containing the application.
    name = "accounts"
