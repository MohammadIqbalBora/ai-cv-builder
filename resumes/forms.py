# This module defines forms and validates information entered by users.

# Django's form framework creates inputs and performs validation.
from django import forms

# The ModelForm below creates or updates this database model.
from .models import CV


# ModelForm converts selected CV model fields into HTML form fields.
class CVForm(forms.ModelForm):
    """Form for creating and editing CV records."""

    # Meta connects this form class to its model and controls exposed fields.
    class Meta:
        # form.save() returns a new or updated CV instance.
        model = CV
        # This list controls which model fields appear and in what order.
        fields = [
            "full_name",
            "email",
            "phone",
            "job_title",
            "address",
            "professional_summary",
            "skills",
            "experience",
            "education",
            "uploaded_file",
            "template",
        ]

    # Accept submitted data, uploaded files, or an existing CV through kwargs.
    def __init__(self, *args, **kwargs):
        # Build all fields using Django's ModelForm implementation first.
        super().__init__(*args, **kwargs)

        # Require only the candidate name while allowing partial CV values.
        self.fields["full_name"].required = True

        # Keep the optional field names together so one loop can configure them.
        optional_fields = [
            "email",
            "phone",
            "job_title",
            "address",
            "professional_summary",
            "skills",
            "experience",
            "education",
            "uploaded_file",
            "template",
        ]

        # Look up each generated field by name and allow it to be empty.
        for field in optional_fields:
            self.fields[field].required = False
