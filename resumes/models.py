from django.contrib.auth.models import User
from django.db import models


class CV(models.Model):
    """Stores a user's CV and the selected PDF template."""

    TEMPLATE_CHOICES = [
        ("modern", "Modern"),
        ("classic", "Classic"),
        ("executive", "Executive"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=200)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    job_title = models.CharField(max_length=200, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    professional_summary = models.TextField(blank=True, null=True)
    skills = models.TextField(blank=True, null=True)
    experience = models.TextField(blank=True, null=True)
    education = models.TextField(blank=True, null=True)

    uploaded_file = models.FileField(
        upload_to="cv_uploads/",
        blank=True,
        null=True,
    )

    template = models.CharField(
        max_length=20,
        choices=TEMPLATE_CHOICES,
        default="modern",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name


class Subscription(models.Model):
    """Stores Stripe subscription state for a user."""

    PLAN_CHOICES = [
        ("Free", "Free"),
        ("Premium", "Premium"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=False)

    plan_name = models.CharField(
        max_length=20,
        choices=PLAN_CHOICES,
        default="Free",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.plan_name}"
