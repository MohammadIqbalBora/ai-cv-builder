# This module defines forms and validates information entered by users.

# Import Django's form field and widget classes.
from django import forms

# Start with Django's secure form for creating a username and two passwords.
from django.contrib.auth.forms import UserCreationForm

# Use Django's built-in database model for registered users.
from django.contrib.auth.models import User


# Inheriting UserCreationForm keeps Django's password matching and validation.
class RegisterForm(UserCreationForm):
    # Add a required email field because the parent form does not require one.
    email = forms.EmailField(required=True)

    # Meta tells this model-backed form which model and fields it represents.
    class Meta:
        # Successful form.save() creates an instance of Django's User model.
        model = User
        # This tuple also controls the order in which fields appear.
        fields = (
            "username",
            "email",
            "password1",
            "password2",
        )

    # Django passes submitted data and other options through args and kwargs.
    def __init__(self, *args, **kwargs):
        # Let UserCreationForm construct its fields before customizing them.
        super().__init__(*args, **kwargs)

        # Remove Django's long default help text for a cleaner page design.
        self.fields["username"].help_text = None
        self.fields["password1"].help_text = None
        self.fields["password2"].help_text = None

        # Add HTML placeholder text to the username input widget.
        self.fields["username"].widget.attrs.update(
            {
                "placeholder": "Choose a username",
            }
        )

        # Add HTML placeholder text to the email input widget.
        self.fields["email"].widget.attrs.update(
            {
                "placeholder": "Enter your email address",
            }
        )

        # Explain the purpose of the first password input inside the field.
        self.fields["password1"].widget.attrs.update(
            {
                "placeholder": "Create a password",
            }
        )

        # Remind the visitor to repeat the same password for verification.
        self.fields["password2"].widget.attrs.update(
            {
                "placeholder": "Confirm your password",
            }
        )


class DeleteAccountForm(forms.Form):
    password = forms.CharField(
        label="Current password",
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "current-password"}),
    )
    confirm = forms.BooleanField(label="I understand that my account and saved documents will be permanently deleted.")

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("Your password is incorrect.")
        return password
