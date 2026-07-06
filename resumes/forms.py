from django import forms
from .models import CV


class CVForm(forms.ModelForm):
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

        # Only Full Name is required
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
            