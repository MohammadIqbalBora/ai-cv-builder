# This module maps URL paths to the views that handle them.

# Reuse Django's secure, built-in login and logout views.
from django.contrib.auth import views as auth_views
# Import the function used to connect a URL fragment to a view.
from django.urls import path

# Import the custom registration view from accounts/views.py.
from . import views

# config/urls.py places all of these routes below /accounts/.
urlpatterns = [
    # /accounts/login/ displays and processes Django's login form.
    path("login/", auth_views.LoginView.as_view(), name="login"),
    # /accounts/logout/ ends the current authenticated session.
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    # /accounts/register/ calls the custom register function.
    path("register/", views.register, name="register"),
]
