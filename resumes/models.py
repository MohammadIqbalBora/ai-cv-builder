from django.db import models
from django.contrib.auth.models import User


class CV(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)

    summary = models.TextField(blank=True)
    experience = models.TextField(blank=True)
    education = models.TextField(blank=True)
    skills = models.TextField(blank=True)

    uploaded_file = models.FileField(upload_to="cv_uploads/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name


class CoverLetter(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    cv = models.ForeignKey("CV", on_delete=models.CASCADE)

    job_description = models.TextField()
    content = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    