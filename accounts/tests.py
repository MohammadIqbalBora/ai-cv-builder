import tempfile
from unittest.mock import patch

import stripe
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from resumes.models import CV, CoverLetter, Subscription


@override_settings(SECURE_SSL_REDIRECT=False, STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class DeleteAccountTests(TestCase):
    def setUp(self):
        media = tempfile.TemporaryDirectory()
        self.addCleanup(media.cleanup)
        override = override_settings(MEDIA_ROOT=media.name)
        override.enable()
        self.addCleanup(override.disable)
        self.user = User.objects.create_user(username="leaving", password="correct-password")
        self.other = User.objects.create_user(username="staying")
        self.cv = CV.objects.create(user=self.user, full_name="Leaving", uploaded_file=SimpleUploadedFile("cv.pdf", b"example"))
        self.other_cv = CV.objects.create(user=self.other, full_name="Staying")
        CoverLetter.objects.create(user=self.user, cv=self.cv, content="Letter", job_description="Role")
        self.client.force_login(self.user)
        self.url = reverse("delete_account")

    def test_get_only_displays_confirmation(self):
        self.assertContains(self.client.get(self.url), "Permanently delete my account")
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_password_and_confirmation_required(self):
        for data in [{"password": "wrong", "confirm": "on"}, {"password": "correct-password"}]:
            self.assertEqual(self.client.post(self.url, data).status_code, 200)
            self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_deletion_removes_owned_data_files_and_session_only(self):
        storage, name = self.cv.uploaded_file.storage, self.cv.uploaded_file.name
        response = self.client.post(self.url, {"password": "correct-password", "confirm": "on", "user_id": self.other.pk})
        self.assertContains(response, "Your account has been deleted")
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(CV.objects.filter(pk=self.cv.pk).exists())
        self.assertFalse(CoverLetter.objects.exists())
        self.assertFalse(storage.exists(name))
        self.assertTrue(User.objects.filter(pk=self.other.pk).exists())
        self.assertTrue(CV.objects.filter(pk=self.other_cv.pk).exists())
        self.assertNotIn("_auth_user_id", self.client.session)

    @patch("accounts.views.stripe.Subscription.cancel")
    def test_subscription_cancelled_before_deletion(self, cancel):
        Subscription.objects.create(user=self.user, stripe_subscription_id="sub_example", is_active=True)
        self.client.post(self.url, {"password": "correct-password", "confirm": "on"})
        self.assertEqual(cancel.call_args.args, ("sub_example",))
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())

    @patch("accounts.views.stripe.Subscription.cancel", side_effect=stripe.APIConnectionError("Unavailable"))
    def test_billing_failure_preserves_account_and_files(self, cancel):
        Subscription.objects.create(user=self.user, stripe_subscription_id="sub_example", is_active=True)
        response = self.client.post(self.url, {"password": "correct-password", "confirm": "on"})
        self.assertContains(response, "Your account has not been deleted")
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertTrue(self.cv.uploaded_file.storage.exists(self.cv.uploaded_file.name))

    def test_authentication_and_csrf_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.url, {"password": "correct-password", "confirm": "on"}).status_code, 403)
