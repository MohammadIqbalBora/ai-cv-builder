# This module defines forms and validates information entered by users.

# Django's form framework creates inputs and performs validation.
from django import forms

# The ModelForm below creates or updates this database model.
from .models import CV, JobAlertPreference
from .validators import validate_additional_sections
from .widgets import AdditionalSectionsWidget


# ModelForm converts selected CV model fields into HTML form fields.
class CVForm(forms.ModelForm):
    """Form for creating and editing CV records."""

    additional_sections = forms.Field(
        required=False,
        widget=AdditionalSectionsWidget,
        validators=[validate_additional_sections],
    )

    # Meta connects this form class to its model and controls exposed fields.
    # class Meta: is basically a configuration section inside your CVForm class. It tells Django which model this form belongs to and which fields from that model should be included.

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
            "additional_sections",
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


class TailoredCVReviewForm(forms.ModelForm):
    """Editable sections rewritten by Job Match."""

    class Meta:
        model = CV
        fields = ["job_title", "professional_summary", "skills", "experience", "education"]
        widgets = {"job_title": forms.TextInput(attrs={"class": "form-control"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.fields:
            if name != "job_title":
                self.fields[name].widget = forms.Textarea(attrs={"class": "form-control", "rows": 8})


class JobAlertForm(forms.ModelForm):
    radius_miles = forms.TypedChoiceField(
        choices=[(5, "5 miles"), (10, "10 miles"), (25, "25 miles"), (50, "50 miles"), (100, "100 miles")], coerce=int,
        label="Travel radius",
    )
    work_preference = forms.ChoiceField(choices=[("any", "Any working arrangement"), ("remote", "Remote only"), ("hybrid", "Hybrid only")])
    minimum_salary = forms.IntegerField(required=False, min_value=0, max_value=1000000, label="Minimum annual salary (GBP)")
    enabled = forms.BooleanField(required=False, label="Email me job matches (up to five new jobs per email). I can unsubscribe at any time.")

    class Meta:
        model = JobAlertPreference
        fields = ["cv", "target_role", "location", "radius_miles", "minimum_salary", "work_preference", "frequency", "enabled"]
        labels = {"cv": "CV to match against", "target_role": "Target job title", "location": "UK town, city or postcode", "frequency": "Email frequency"}
        help_texts = {"frequency": "Choose daily or weekly emails. Only new matches are sent; no email is sent when there are none."}

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["cv"].queryset = CV.objects.filter(user=user).order_by("-created_at")
        self.fields["cv"].required = True
        self.fields["cv"].empty_label = "Choose a CV"
        self.fields["cv"].label_from_instance = lambda cv: (
            f"{cv.full_name} | {cv.job_title or 'No job title'} | "
            f"{cv.created_at:%d %b %Y} | CV #{cv.pk}"
        )
        for name, field in self.fields.items():
            if name != "enabled":
                field.widget.attrs["class"] = "form-control"

    def clean(self):
        data = super().clean()
        if data.get("enabled") and not self.user.email:
            self.add_error("enabled", "Your account needs an email address before you can receive alerts.")
        return data
