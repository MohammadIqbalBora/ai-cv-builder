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
