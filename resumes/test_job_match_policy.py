from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import CV, Subscription


@override_settings(
    SECURE_SSL_REDIRECT=False,
    STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
)
class JobMatchPolicyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="match-policy-owner")
        Subscription.objects.create(user=self.user, is_active=True, plan_name="Premium")
        self.cv = CV.objects.create(user=self.user, full_name="Example", skills="Communication")
        self.client.force_login(self.user)
        self.job = "Teach English and plan lessons."
        self.analyse_url = reverse("job_match", args=[self.cv.pk])
        self.tailor_url = reverse("tailor_cv_to_job", args=[self.cv.pk])

    def analyse(self, ai, score):
        ai.return_value.analyse_job_description.return_value = {
            "match_score": score, "missing_skills": "Classroom management",
        }
        return self.client.post(self.analyse_url, {"job_description": self.job})

    @patch("resumes.views.AIService")
    def test_low_scores_disable_button_and_block_direct_posts(self, ai):
        for score in (0, 5, 10, 39, 39.9, "5%"):
            with self.subTest(score=score):
                response = self.analyse(ai, score)
                self.assertFalse(response.context["can_tailor"])
                self.assertContains(response, 'disabled aria-disabled="true"')
                self.assertContains(response, "Tailoring requires at least 40%")
                # A caller cannot supply a higher score to bypass the rule.
                response = self.client.post(self.tailor_url, {"job_description": self.job, "match_score": 100})
                self.assertEqual(response.status_code, 403)
        ai.return_value.tailor_cv_to_job.assert_not_called()
        self.assertEqual(CV.objects.filter(user=self.user).count(), 1)

    @patch("resumes.views.AIService")
    def test_threshold_boundaries_warn_then_allow(self, ai):
        ai.return_value.tailor_cv_to_job.return_value = {"skills": "Relevant communication"}
        for score in (40, "40", 59, 60, 100):
            with self.subTest(score=score):
                response = self.analyse(ai, score)
                self.assertTrue(response.context["can_tailor"])
                self.assertEqual(response.context["weak_match"], float(score) < 60)
                self.assertNotContains(response, 'disabled aria-disabled="true"')
                if float(score) < 60:
                    self.assertContains(response, "there are gaps in the job requirements")
                else:
                    self.assertNotContains(response, "there are gaps in the job requirements")
                response = self.client.post(self.tailor_url, {"job_description": self.job})
                self.assertEqual(response.status_code, 302)
        self.assertEqual(ai.return_value.tailor_cv_to_job.call_count, 5)
        self.assertEqual(CV.objects.filter(user=self.user).count(), 6)
        # Reuse the existing analysis rather than paying for another analysis call.
        self.assertEqual(ai.return_value.analyse_job_description.call_count, 5)

    @patch("resumes.views.AIService")
    def test_invalid_or_missing_scores_fail_closed(self, ai):
        for score in (None, "unknown", "NaN", "Infinity", -1, 101, True, [], {}):
            with self.subTest(score=score):
                response = self.analyse(ai, score)
                self.assertFalse(response.context["can_tailor"])
                self.assertContains(response, "Score unavailable")
                self.assertContains(response, "Analyse the job description again")
                self.assertEqual(self.client.post(self.tailor_url, {"job_description": self.job}).status_code, 403)
        ai.return_value.tailor_cv_to_job.assert_not_called()
        self.assertEqual(CV.objects.filter(user=self.user).count(), 1)

    @patch("resumes.views.AIService")
    def test_multiline_job_survives_browser_form_line_endings(self, ai):
        self.job = 'Software Developer\r\nPython & Django\r\nBuild "reliable" applications.'
        ai.return_value.tailor_cv_to_job.return_value = {"skills": "Python, Django"}
        self.analyse(ai, 70)
        # Browsers normalise HTML newlines to LF, then submit forms with CRLF.
        for newline in ("\n", "\r\n", "\r"):
            with self.subTest(newline=repr(newline)):
                submitted_job = self.job.replace("\r\n", newline)
                response = self.client.post(self.tailor_url, {"job_description": submitted_job})
                self.assertEqual(response.status_code, 302)
                self.assertIn("review", response.url)
        self.assertEqual(ai.return_value.analyse_job_description.call_count, 1)
        self.assertEqual(ai.return_value.tailor_cv_to_job.call_count, 3)

    @patch("resumes.views.AIService")
    def test_analysis_is_required_before_direct_tailoring(self, ai):
        response = self.client.post(self.tailor_url, {"job_description": self.job})
        self.assertContains(response, "Analyse this CV against this job description", status_code=400)
        ai.assert_not_called()
        self.assertEqual(CV.objects.filter(user=self.user).count(), 1)

    @patch("resumes.views.AIService")
    def test_analysis_cannot_be_reused_for_another_cv_or_job(self, ai):
        self.analyse(ai, 80)
        other_cv = CV.objects.create(user=self.user, full_name=self.cv.full_name, skills=self.cv.skills)
        for url, job in (
            (self.tailor_url, "A different job"),
            (reverse("tailor_cv_to_job", args=[other_cv.pk]), self.job),
        ):
            response = self.client.post(url, {"job_description": job})
            self.assertEqual(response.status_code, 400)
        ai.return_value.tailor_cv_to_job.assert_not_called()

    @patch("resumes.views.AIService")
    def test_editing_cv_invalidates_analysis_including_extra_sections(self, ai):
        self.analyse(ai, 80)
        self.cv.skills = "Different skills"
        self.cv.save()
        self.assertEqual(self.client.post(self.tailor_url, {"job_description": self.job}).status_code, 400)
        self.analyse(ai, 80)
        self.cv.additional_sections = [{"title": "Memberships", "content": "Example institute"}]
        self.cv.save()
        self.assertEqual(self.client.post(self.tailor_url, {"job_description": self.job}).status_code, 400)
        ai.return_value.tailor_cv_to_job.assert_not_called()

    @patch("resumes.views.AIService")
    def test_returning_to_results_keeps_valid_score_and_guidance(self, ai):
        self.analyse(ai, 5)
        response = self.client.get(self.analyse_url)
        self.assertContains(response, "Tailoring requires at least 40%")
        self.assertEqual(response.context["job_description"], self.job)
        self.cv.skills = "Changed"
        self.cv.save()
        response = self.client.get(self.analyse_url)
        self.assertIsNone(response.context["analysis"])

    @patch("resumes.views.AIService")
    def test_other_users_cannot_tailor_this_cv(self, ai):
        self.analyse(ai, 80)
        other = User.objects.create_user(username="other-match-user")
        self.client.force_login(other)
        self.assertEqual(self.client.post(self.tailor_url, {"job_description": self.job}).status_code, 404)
        ai.return_value.tailor_cv_to_job.assert_not_called()
