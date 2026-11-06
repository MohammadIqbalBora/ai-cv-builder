# This module defines the data stored in the database.

# Link CV and subscription records to Django's built-in account model.
import uuid

from django.contrib.auth.models import User
# Django model fields describe database columns and relationships.
from django.db import models

from .validators import validate_additional_sections


# Each CV instance becomes one row in the resumes_cv database table.
class CV(models.Model):
    """Stores a user's CV and the selected PDF template."""

    # Store machine-readable values on the left and display labels on the right.
    TEMPLATE_CHOICES = [
        ("modern", "Modern"),
        ("classic", "Classic"),
        ("executive", "Executive"),
    ]

    # A user can own many CVs; deleting the user also deletes those CVs.
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    # The candidate name is mandatory and limited to 200 characters.
    full_name = models.CharField(max_length=200)
    # `blank` permits forms to omit a value; `null` permits database NULL.
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    job_title = models.CharField(max_length=200, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    # Long, free-form CV sections use TextField because their size varies.
    professional_summary = models.TextField(blank=True, null=True)
    skills = models.TextField(blank=True, null=True)
    experience = models.TextField(blank=True, null=True)
    education = models.TextField(blank=True, null=True)
    additional_sections = models.JSONField(default=list, blank=True, validators=[validate_additional_sections])

    # Store the uploaded file path; the file itself goes under media/cv_uploads/.
    uploaded_file = models.FileField(
        upload_to="cv_uploads/",
        blank=True,
        null=True,
    )

    # Restrict the stored template value to TEMPLATE_CHOICES.
    template = models.CharField(
        max_length=20,
        choices=TEMPLATE_CHOICES,
        default="modern",
    )

    section_order = models.JSONField(default=list, blank=True)

    original_content = models.JSONField(default=dict, blank=True)

    # Record the creation time once, when Django first inserts the row.
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def modern_sections(self):
        from .cv_layout import modern_sections
        return modern_sections(self)

    # Admin pages and debugging display a CV using its candidate name.
    def __str__(self):
        return self.full_name


# One Subscription row records one user's current Stripe/plan state.
class Subscription(models.Model):
    """Stores Stripe subscription state for a user."""

    # These pairs provide stored values and human-friendly labels.
    PLAN_CHOICES = [
        ("Free", "Free"),
        ("Premium", "Premium"),
    ]

    # OneToOneField guarantees that each user has at most one subscription row.
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # Stripe IDs connect the local record to objects held by Stripe.
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True)
    # The webhook/payment flow changes this flag when access is active.
    is_active = models.BooleanField(default=False)

    cancel_at_period_end = models.BooleanField(default=False)
    premium_until = models.DateTimeField(blank=True, null=True)

    @property
    def has_premium_access(self):
        from django.utils import timezone
        return self.is_active and (not self.cancel_at_period_end or (
            self.premium_until is not None and self.premium_until > timezone.now()
        ))

    # New users start on the Free plan.
    plan_name = models.CharField(
        max_length=20,
        choices=PLAN_CHOICES,
        default="Free",
    )

    # Preserve both the original creation time and most recent update time.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Display a readable account-and-plan label in Django admin and the shell.
    def __str__(self):
        return f"{self.user.username} - {self.plan_name}"
    


class CoverLetter(models.Model):
    """A saved generated letter belonging to a user and source CV."""

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    cv = models.ForeignKey(CV, on_delete=models.CASCADE)
    job_description = models.TextField()
    content = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def title(self):
        name = self.cv.full_name
        if name.endswith(" - Tailored CV"):
            return f"{name.removesuffix(' - Tailored CV')} - Tailored Cover Letter"
        return f"{name} - Cover Letter"

    def __str__(self):
        return f"Cover letter for {self.cv.full_name}"


class FreeDownloadUsage(models.Model):
    """Lifetime free PDF allowance, independent of saved documents."""

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    downloads = models.PositiveIntegerField(default=0)


class ApplicationPack(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    checkout_session_id = models.CharField(max_length=255, unique=True)
    cv_downloads = models.PositiveIntegerField(default=3)
    letter_downloads = models.PositiveIntegerField(default=3)
    created_at = models.DateTimeField(auto_now_add=True)


class JobAlertPreference(models.Model):
    """One explicit, revocable job-alert subscription per account."""

    FREQUENCY_CHOICES = [("daily", "Daily"), ("weekly", "Weekly")]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    cv = models.ForeignKey(CV, on_delete=models.SET_NULL, null=True, blank=True)
    target_role = models.CharField(max_length=150)
    location = models.CharField(max_length=150)
    radius_miles = models.PositiveSmallIntegerField(default=25)
    minimum_salary = models.PositiveIntegerField(null=True, blank=True)
    work_preference = models.CharField(max_length=10, default="any")
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default="weekly")
    enabled = models.BooleanField(default=False)
    confirmed_email = models.EmailField(blank=True)
    confirmation_email = models.EmailField(blank=True)
    confirmation_sent_at = models.DateTimeField(null=True, blank=True)
    consented_at = models.DateTimeField(null=True, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    email_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)


class SentJobAlert(models.Model):
    preference = models.ForeignKey(JobAlertPreference, on_delete=models.CASCADE)
    provider_job_id = models.CharField(max_length=200)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["preference", "provider_job_id"], name="unique_sent_job_alert")]
