# This module maps URL paths to the views that handle them.

# Reuse Django's secure, built-in login and logout views.
from django.contrib.auth import views as auth_views
# Import the function used to connect a URL fragment to a view.
from django.urls import path

# Import the custom registration view from accounts/views.py.
from . import views

# config/urls.py places all of these routes below /accounts/.
urlpatterns = [
    path("delete/", views.delete_account, name="delete_account"),
    # /accounts/login/ displays and processes Django's login form.
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("password-reset/", auth_views.PasswordResetView.as_view(
        email_template_name="registration/password_reset_email.txt",
        subject_template_name="registration/password_reset_subject.txt",
    ), name="password_reset"),
    path("password-reset/sent/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("reset/complete/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    # /accounts/logout/ ends the current authenticated session.
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    # /accounts/register/ calls the custom register function.
    path("register/", views.register, name="register"),
]
