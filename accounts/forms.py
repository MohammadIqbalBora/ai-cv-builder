from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "password1",
            "password2",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["username"].help_text = None
        self.fields["password1"].help_text = None
        self.fields["password2"].help_text = None

        self.fields["username"].widget.attrs.update(
            {
                "placeholder": "Choose a username",
            }
        )

        self.fields["email"].widget.attrs.update(
            {
                "placeholder": "Enter your email address",
            }
        )

        self.fields["password1"].widget.attrs.update(
            {
                "placeholder": "Create a password",
            }
        )

        self.fields["password2"].widget.attrs.update(
            {
                "placeholder": "Confirm your password",
            }
        )
