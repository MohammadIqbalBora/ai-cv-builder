# This module provides Django with configuration for this application.

# AppConfig is Django's base class for application metadata.
from django.apps import AppConfig


# Django initializes this app because `resumes` appears in INSTALLED_APPS.
class ResumesConfig(AppConfig):
    # Give new models 64-bit automatically generated primary keys by default.
    default_auto_field = "django.db.models.BigAutoField"
    # Point this configuration at the local resumes Python package.
    name = "resumes"
