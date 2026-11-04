from datetime import timedelta
from io import StringIO
from unittest.mock import patch

import requests
from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command, CommandError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .job_alert_service import alerts_ready, rank_jobs, search_jobs, send_confirmation, send_weekly_digest, JobSearchUnavailable
from .models import CV, JobAlertPreference, SentJobAlert, Subscription


ALERT_SETTINGS = {
    "SECURE_SSL_REDIRECT": False,
    "JOB_ALERTS_ENABLED": True, "ADZUNA_APP_ID": "example-id", "ADZUNA_APP_KEY": "example-key",
    "EMAIL_HOST": "smtp.example.com", "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    "DEFAULT_FROM_EMAIL": "alerts@example.com", "SITE_URL": "https://cv.example.com",
    "STORAGES": {"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
}


@override_settings(**ALERT_SETTINGS)
class JobAlertTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alert-owner", email="owner@example.com")
        self.other = User.objects.create_user(username="alert-other", email="other@example.com")
        self.cv = CV.objects.create(user=self.user, full_name="Private Name", email="private@example.com", phone="07123456789", address="Private Address", job_title="English Teacher", skills="Lesson planning, assessment, literature")
        self.other_cv = CV.objects.create(user=self.other, full_name="Other CV")
        self.sub = Subscription.objects.create(user=self.user, is_active=True, plan_name="Premium")
        self.pref = JobAlertPreference.objects.create(user=self.user, cv=self.cv, target_role="English teacher", location="London", enabled=True, confirmed_email=self.user.email, consented_at=timezone.now())
        self.client.force_login(self.user)
        self.job = {"id": "job-1", "title": "English Teacher", "description": "Plan English literature lessons and assessment in a hybrid role.", "company": {"display_name": "Example School"}, "location": {"display_name": "London"}, "salary_min": 40000, "redirect_url": "https://www.adzuna.co.uk/jobs/details/123"}

    def form_data(self, **updates):
        data = {"cv": self.cv.pk, "target_role": "English teacher", "location": "London", "radius_miles": 25, "work_preference": "any", "enabled": "on"}
        data.update(updates)
        return data

    def test_preferences_are_private_and_require_premium(self):
        self.assertContains(self.client.get(reverse("job_alert_preferences")), "Your search preferences")
        response = self.client.post(reverse("job_alert_preferences"), self.form_data(cv=self.other_cv.pk))
        self.assertContains(response, "Select a valid choice")
        self.pref.refresh_from_db()
        self.assertEqual(self.pref.cv_id, self.cv.pk)
        self.client.force_login(self.other)
        self.assertContains(self.client.get(reverse("job_alert_preferences")), "Job alerts are a Premium feature")
        self.client.post(reverse("job_alert_preferences"), self.form_data())
        self.assertFalse(JobAlertPreference.objects.filter(user=self.other).exists())

    @override_settings(JOB_ALERTS_ENABLED=False)
    def test_service_off_saves_preferences_without_network_or_mail(self):
        with patch("resumes.job_alert_service.requests.get") as request:
            response = self.client.post(reverse("job_alert_preferences"), self.form_data())
        self.assertContains(response, "preferences have been saved")
        self.assertContains(response, "being prepared")
        request.assert_not_called()
        self.assertEqual(len(mail.outbox), 0)

    def test_unchecking_email_pauses_alerts(self):
        self.client.post(reverse("job_alert_preferences"), self.form_data(enabled=""))
        self.pref.refresh_from_db()
        self.assertFalse(self.pref.enabled)

    def test_csrf_and_login_are_required_for_preferences(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse("job_alert_preferences"), self.form_data()).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("job_alert_preferences")).status_code, 302)

    @patch("resumes.job_alert_service.requests.get")
    def test_api_receives_preferences_but_no_cv_or_contact_data(self, request):
        request.return_value.json.return_value = {"results": [self.job]}
        self.pref.minimum_salary = 30000
        self.assertEqual(search_jobs(self.pref), [self.job])
        self.assertEqual(request.call_args.args[0], "https://api.adzuna.com/v1/api/jobs/gb/search/1")
        params = request.call_args.kwargs["params"]
        self.assertEqual(params["what"], "English teacher")
        self.assertEqual(params["where"], "London")
        self.assertEqual(params["salary_min"], 30000)
        self.assertEqual(params["distance"], 40)
        transmitted = str(params)
        for private in [self.cv.full_name, self.cv.email, self.cv.phone, self.cv.address, self.cv.skills]:
            self.assertNotIn(private, transmitted)

    @patch("resumes.job_alert_service.requests.get", side_effect=requests.Timeout("secret provider URL"))
    def test_provider_errors_do_not_expose_credentials(self, request):
        with self.assertRaises(JobSearchUnavailable) as caught:
            search_jobs(self.pref)
        self.assertNotIn("secret", str(caught.exception))

    def test_ranking_deduplicates_and_rejects_irrelevant_and_unsafe_jobs(self):
        plumber = dict(self.job, id="plumber", title="Plumber", description="Plumbing")
        unsafe = dict(self.job, id="unsafe", redirect_url="javascript:alert(1)")
        foreign = dict(self.job, id="foreign", redirect_url="https://adzuna.co.uk.attacker.example/job")
        math = dict(self.job, id="math", title="Maths Teacher", description="Teach maths lessons")
        results = rank_jobs(self.pref, [self.job, self.job, plumber, unsafe, foreign, math])
        self.assertEqual([job["id"] for job in results], ["job-1"])
        self.assertIn("assessment", results[0]["reason"])
        self.assertEqual(rank_jobs(self.pref, [self.job], ["job-1"]), [])
        self.assertEqual(len(rank_jobs(self.pref, [dict(self.job, id=str(i)) for i in range(9)])), 5)

    def test_remote_hybrid_salary_filters(self):
        self.pref.work_preference = "remote"
        self.assertEqual(rank_jobs(self.pref, [self.job]), [])
        remote = dict(self.job, description="Remote English literature teaching and assessment")
        self.assertEqual(len(rank_jobs(self.pref, [remote])), 1)
        self.pref.work_preference = "hybrid"
        self.assertEqual(len(rank_jobs(self.pref, [self.job])), 1)
        self.pref.minimum_salary = 50000
        self.assertEqual(rank_jobs(self.pref, [self.job]), [])

    @patch("resumes.job_alert_service.search_jobs")
    def test_weekly_digest_and_sent_job_deduplication(self, search):
        search.return_value = [self.job]
        self.assertEqual(send_weekly_digest(self.pref), "sent")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertIn(self.job["redirect_url"], mail.outbox[0].body)
        self.assertIn("Adzuna", mail.outbox[0].body)
        self.assertIn("Stop job alert emails", mail.outbox[0].body)
        self.assertEqual(SentJobAlert.objects.count(), 1)
        self.assertEqual(send_weekly_digest(self.pref), "skipped")
        self.pref.last_checked_at = timezone.now() - timedelta(days=8)
        self.pref.last_attempt_at = timezone.now() - timedelta(days=8)
        self.pref.save()
        self.assertEqual(send_weekly_digest(self.pref), "no_matches")
        self.assertEqual(len(mail.outbox), 1)

    @patch("resumes.job_alert_service.search_jobs")
    def test_inactive_paused_expired_or_deleted_cv_sends_nothing(self, search):
        self.sub.is_active = False
        self.sub.save()
        self.assertEqual(send_weekly_digest(self.pref), "skipped")
        self.sub.is_active = True
        self.sub.cancel_at_period_end = True
        self.sub.premium_until = timezone.now() - timedelta(days=1)
        self.sub.save()
        self.pref = JobAlertPreference.objects.get(pk=self.pref.pk)
        self.assertEqual(send_weekly_digest(self.pref), "skipped")
        self.pref.enabled = False
        self.assertEqual(send_weekly_digest(self.pref), "skipped")
        self.cv.delete()
        self.pref.refresh_from_db()
        self.assertIsNone(self.pref.cv)
        self.assertEqual(send_weekly_digest(self.pref), "skipped")
        search.assert_not_called()

    def test_email_confirmation_required_and_get_is_read_only(self):
        self.pref.confirmed_email = ""
        self.pref.save()
        self.assertTrue(send_confirmation(self.pref))
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(send_confirmation(self.pref))
        url = reverse("confirm_job_alerts", args=[self.pref.email_token])
        self.assertContains(self.client.get(url), "Confirm my job alerts")
        self.pref.refresh_from_db()
        self.assertEqual(self.pref.confirmed_email, "")
        self.assertContains(self.client.post(url), "Email confirmed")
        self.pref.refresh_from_db()
        self.assertEqual(self.pref.confirmed_email, self.user.email)

    def test_changed_email_cannot_be_confirmed_by_old_link(self):
        self.pref.confirmed_email = ""
        self.pref.save()
        send_confirmation(self.pref)
        self.user.email = "changed@example.com"
        self.user.save()
        response = self.client.post(reverse("confirm_job_alerts", args=[self.pref.email_token]))
        self.assertContains(response, "no longer active")
        self.pref.refresh_from_db()
        self.assertEqual(self.pref.confirmed_email, "")

    def test_unsubscribe_without_login_and_account_deletion(self):
        url = reverse("unsubscribe_job_alerts", args=[self.pref.email_token])
        self.client.logout()
        self.client.get(url)
        self.pref.refresh_from_db()
        self.assertTrue(self.pref.enabled)
        self.assertContains(self.client.post(url), "Job alerts paused")
        self.pref.refresh_from_db()
        self.assertFalse(self.pref.enabled)
        self.assertTrue(CV.objects.filter(pk=self.cv.pk).exists())
        self.user.delete()
        self.assertFalse(JobAlertPreference.objects.filter(pk=self.pref.pk).exists())

    @override_settings(JOB_ALERTS_ENABLED=False)
    def test_worker_refuses_to_run_without_configuration(self):
        self.assertFalse(alerts_ready())
        with self.assertRaises(CommandError):
            call_command("send_job_alerts", stdout=StringIO())

    @patch("resumes.job_alert_service.search_jobs")
    def test_worker_command_and_configuration_check(self, search):
        search.return_value = [self.job]
        call_command("send_job_alerts", check=True, stdout=StringIO())
        search.assert_not_called()
        call_command("send_job_alerts", stdout=StringIO())
        call_command("send_job_alerts", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)

    @patch("resumes.job_alert_service.search_jobs", side_effect=JobSearchUnavailable("Unavailable"))
    def test_worker_failure_keeps_jobs_unsent_and_delays_retry(self, search):
        call_command("send_job_alerts", stdout=StringIO())
        self.pref.refresh_from_db()
        self.assertIsNotNone(self.pref.last_attempt_at)
        self.assertIsNone(self.pref.last_sent_at)
        self.assertFalse(SentJobAlert.objects.exists())
        call_command("send_job_alerts", stdout=StringIO())
        self.assertEqual(search.call_count, 1)


    def test_pending_confirmation_is_not_emailed_repeatedly_by_worker(self):
        self.pref.confirmed_email = ""
        self.pref.save()
        call_command("send_job_alerts", stdout=StringIO())
        self.pref.refresh_from_db()
        self.pref.confirmation_sent_at = timezone.now() - timedelta(days=2)
        self.pref.save()
        call_command("send_job_alerts", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)

    def test_expired_confirmation_cannot_enable_email(self):
        self.pref.confirmed_email = ""
        self.pref.confirmation_email = self.user.email
        self.pref.confirmation_sent_at = timezone.now() - timedelta(days=8)
        self.pref.save()
        self.assertContains(self.client.post(reverse("confirm_job_alerts", args=[self.pref.email_token])), "no longer active")
        self.pref.refresh_from_db()
        self.assertEqual(self.pref.confirmed_email, "")

    @patch("resumes.job_alert_service.EmailMultiAlternatives.send", return_value=0)
    @patch("resumes.job_alert_service.search_jobs")
    def test_rejected_delivery_is_not_marked_as_sent(self, search, send):
        search.return_value = [self.job]
        call_command("send_job_alerts", stdout=StringIO())
        self.pref.refresh_from_db()
        self.assertIsNone(self.pref.last_sent_at)
        self.assertIsNone(self.pref.last_checked_at)
        self.assertFalse(SentJobAlert.objects.exists())
