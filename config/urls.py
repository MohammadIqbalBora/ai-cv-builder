# This module maps URL paths to the views that handle them.

"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

# Read DEBUG and the media-file locations from config/settings.py.
from django.conf import settings
# Import the development helper that creates URLs for uploaded files.
from django.conf.urls.static import static
# Import Django's built-in administration site.
from django.contrib import admin
# `path` creates a route; `include` delegates routes to another app.
from django.urls import include, path

# Django searches this list from top to bottom for every incoming request.
urlpatterns = [
    # Hand /admin/ URLs to Django's built-in admin application.
    path("admin/", admin.site.urls),
    # Hand root URLs such as /dashboard/ to resumes/urls.py.
    path("", include("resumes.urls")),
    # Prefix every route in accounts/urls.py with /accounts/.
    path("accounts/", include("accounts.urls")),
]


# Only let Django serve uploaded files while developing locally.
if settings.DEBUG:
    # Map the public MEDIA_URL to the MEDIA_ROOT directory on disk.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
