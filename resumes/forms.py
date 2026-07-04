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
        