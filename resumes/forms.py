from django import forms
from .models import CV

class CVForm(forms.ModelForm):
    class Meta:
        model = CV
        fields = [
            'full_name',
            'email',
            'phone',
            'summary',
            'experience',
            'education',
            'skills',
            'uploaded_file'
        ]
        