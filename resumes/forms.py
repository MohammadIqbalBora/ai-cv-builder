from django import forms

from .models import CV


class CVForm(forms.ModelForm):
    """Form for creating and editing CV records."""

    class Meta:
        model = CV
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Require only the candidate name while allowing partial CV values.
        self.fields["full_name"].required = True

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

        for field in optional_fields:
            self.fields[field].required = False
