from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import CV, CoverLetter, Subscription


@override_settings(SECURE_SSL_REDIRECT=False, STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class SavedCoverLetterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner")
        self.other = User.objects.create_user(username="other")
        self.cv = CV.objects.create(user=self.user, full_name="Example Candidate")
        Subscription.objects.create(user=self.user, is_active=True, plan_name="Premium")
        self.client.force_login(self.user)

    @patch("resumes.views.AIService")
    def test_generated_letter_survives_session_and_appears_on_dashboard(self, ai):
        ai.return_value.generate_cover_letter.return_value = "Dear hiring manager, saved letter."
        session = self.client.session
        session["last_job_description"] = "Software engineer role"
        session.save()
        response = self.client.post(reverse("create_cover_letter", args=[self.cv.id]))
        letter = CoverLetter.objects.get()
        self.assertRedirects(response, reverse("create_cover_letter", args=[self.cv.id]) + f"?letter={letter.id}")
        self.assertEqual(letter.user, self.user)
        self.client.logout()
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "My Cover Letters")
        self.assertContains(response, f"?letter={letter.id}")
        response = self.client.get(reverse("create_cover_letter", args=[self.cv.id]) + f"?letter={letter.id}")
        self.assertContains(response, letter.content)
        response = self.client.get(reverse("download_cover_letter_pdf", args=[self.cv.id]) + f"?letter={letter.id}")
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_letters_are_private_and_download_uses_selected_letter(self):
        own = CoverLetter.objects.create(user=self.user, cv=self.cv, content="Own saved letter", job_description="Role")
        other_cv = CV.objects.create(user=self.other, full_name="Private candidate")
        other = CoverLetter.objects.create(user=self.other, cv=other_cv, content="Private content", job_description="Role")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(list(response.context["cover_letters"]), [own])
        for route in ["create_cover_letter", "download_cover_letter_pdf"]:
            response = self.client.get(reverse(route, args=[self.cv.id]) + f"?letter={other.id}")
            self.assertEqual(response.status_code, 404)

    def test_empty_dashboard(self):
        self.cv.delete()
        self.assertContains(self.client.get(reverse("dashboard")), "No CVs Yet")

    def test_dashboard_recovers_legacy_session_letter_once(self):
        session = self.client.session
        session["last_cover_letter"] = "Letter from previous release"
        session["last_cover_letter_cv_id"] = self.cv.id
        session.save()
        self.client.get(reverse("dashboard"))
        self.client.get(reverse("dashboard"))
        self.assertEqual(CoverLetter.objects.filter(user=self.user).count(), 1)
        self.assertNotIn("last_cover_letter", self.client.session)

    def test_dashboard_does_not_recover_another_users_letter(self):
        other_cv = CV.objects.create(user=self.other, full_name="Other candidate")
        session = self.client.session
        session["last_cover_letter"] = "Private letter"
        session["last_cover_letter_cv_id"] = other_cv.id
        session.save()
        self.client.get(reverse("dashboard"))
        self.assertFalse(CoverLetter.objects.exists())
