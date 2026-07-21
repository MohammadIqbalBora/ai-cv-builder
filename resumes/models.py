# This module defines the data stored in the database.

# Link CV and subscription records to Django's built-in account model.
from django.contrib.auth.models import User
# Django model fields describe database columns and relationships.
from django.db import models


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

    # Record the creation time once, when Django first inserts the row.
    created_at = models.DateTimeField(auto_now_add=True)

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
    
