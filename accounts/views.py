# This module handles web requests and prepares responses or pages.

# `render` builds an HTML response; `redirect` sends the browser elsewhere.
from django.shortcuts import redirect, render

# This form, defined in accounts/forms.py, validates and creates a user.
from .forms import RegisterForm


# accounts/urls.py calls this function for /accounts/register/ requests.
def register(request):
    # POST indicates that the visitor submitted the form.
    if request.method == "POST":
        # Bind the submitted values to the form so they can be validated.
        form = RegisterForm(request.POST)

        # Continue only when every form validation rule passes.
        if form.is_valid():
            # Save the new user record to the database.
            form.save()
            # Use the route named `login` rather than hard-coding its URL.
            return redirect("login")

    # GET indicates that the visitor is opening the registration page.
    else:
        # An unbound form starts with empty fields and no validation errors.
        form = RegisterForm()

    # For GET, show the empty form. For an invalid POST, show the submitted
    # values and validation errors in templates/registration/register.html.
    return render(
        # Forward request information to Django's template system.
        request,
        # Select the template that produces the registration page.
        "registration/register.html",
        # Expose this Python form to the template under the name `form`.
        {
            "form": form,
        },
    )


from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
import logging
import stripe

from resumes.models import CV, Subscription
from .forms import DeleteAccountForm

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET", "POST"])
def delete_account(request):
    """Delete only the authenticated user's account after password confirmation."""
    form = DeleteAccountForm(request.POST if request.method == "POST" else None, user=request.user)
    if request.method == "POST" and form.is_valid():
        subscription = Subscription.objects.filter(user=request.user).first()
        if subscription and subscription.stripe_subscription_id:
            try:
                stripe.Subscription.cancel(subscription.stripe_subscription_id, api_key=settings.STRIPE_SECRET_KEY)
            except stripe.InvalidRequestError as error:
                # A subscription already removed in Stripe needs no cancellation.
                if error.code != "resource_missing":
                    logger.warning("Account deletion billing cancellation failed for user %s", request.user.pk)
                    form.add_error(None, "We could not cancel your subscription. Your account has not been deleted. Please try again.")
            except stripe.StripeError:
                logger.warning("Account deletion billing cancellation failed for user %s", request.user.pk)
                form.add_error(None, "We could not cancel your subscription. Your account has not been deleted. Please try again.")
        if not form.errors:
            try:
                for cv in CV.objects.filter(user=request.user).exclude(uploaded_file=""):
                    if cv.uploaded_file:
                        cv.uploaded_file.delete(save=False)
            except OSError:
                logger.warning("Account deletion file cleanup failed for user %s", request.user.pk)
                form.add_error(None, "We could not remove an uploaded file. Please try deleting your account again.")
            if not form.errors:
                request.user.delete()
                logout(request)
                return render(request, "registration/account_deleted.html")
    return render(request, "registration/delete_account.html", {"form": form})
