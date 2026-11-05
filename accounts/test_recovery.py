import re
from datetime import datetime, timedelta
from unittest.mock import patch
from urllib.parse import urlsplit

from django.contrib.auth.models import User
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse


@override_settings(
    SECURE_SSL_REDIRECT=False,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="alerts@example.com",
    STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
)
class AccountRecoveryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="recover-my-username", email="recover@example.com", password="Original-password-123!",
        )
        self.url = reverse("password_reset")

    def request_link(self):
        response = self.client.post(self.url, {"email": self.user.email}, secure=True)
        self.assertRedirects(response, reverse("password_reset_done"), fetch_redirect_response=False)
        message = mail.outbox[-1]
        link = re.search(r"https://[^\s]+/accounts/reset/[^\s]+", message.body).group(0)
        return urlsplit(link).path

    def test_login_links_to_recovery_and_email_contains_username(self):
        self.assertContains(self.client.get(reverse("login")), f'href="{self.url}"')
        self.request_link()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertIn("Your username: recover-my-username", mail.outbox[0].body)
        self.assertIn("24 hours", mail.outbox[0].body)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Original-password-123!"))

    def test_password_reset_changes_password_and_link_cannot_be_reused(self):
        link = self.request_link()
        response = self.client.get(link, follow=True)
        self.assertContains(response, "Choose a new password")
        form_url = response.request["PATH_INFO"]
        response = self.client.post(form_url, {
            "new_password1": "Replacement-password-987!", "new_password2": "Replacement-password-987!",
        })
        self.assertRedirects(response, reverse("password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Replacement-password-987!"))
        self.assertFalse(self.user.check_password("Original-password-123!"))
        self.assertContains(self.client.get(link, follow=True), "This link is no longer valid")
        self.assertTrue(self.client.login(username=self.user.username, password="Replacement-password-987!"))

    def test_unknown_inactive_and_unusable_accounts_have_same_response(self):
        inactive = User.objects.create_user(username="inactive-recovery", email="inactive@example.com", password="A-password-123!", is_active=False)
        unusable = User.objects.create_user(username="unusable-recovery", email="unusable@example.com")
        for email in ("unknown@example.com", inactive.email, unusable.email):
            with self.subTest(email=email):
                response = self.client.post(self.url, {"email": email})
                self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_expired_and_tampered_links_are_rejected(self):
        link = self.request_link()
        self.assertContains(self.client.get(link.rstrip("/") + "tampered/", follow=True), "This link is no longer valid")
        with patch("django.contrib.auth.tokens.PasswordResetTokenGenerator._now", return_value=datetime.now() + timedelta(days=2)):
            self.assertContains(self.client.get(link, follow=True), "This link is no longer valid")

    def test_mismatched_passwords_do_not_update_account(self):
        link = self.request_link()
        response = self.client.get(link, follow=True)
        response = self.client.post(response.request["PATH_INFO"], {
            "new_password1": "Replacement-password-987!", "new_password2": "Different-password-321!",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("new_password2", response.context["form"].errors)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Original-password-123!"))

    def test_recovery_request_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(self.url, {"email": self.user.email}).status_code, 403)
        self.assertEqual(len(mail.outbox), 0)
