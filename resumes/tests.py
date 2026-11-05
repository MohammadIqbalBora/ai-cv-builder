from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import CV, CoverLetter, Subscription, FreeDownloadUsage


@override_settings(SECURE_SSL_REDIRECT=False, STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
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

    def test_delete_letter_requires_confirmation_and_ownership(self):
        letter = CoverLetter.objects.create(user=self.user, cv=self.cv, content="Saved letter", job_description="Role")
        url = reverse("delete_cover_letter", args=[letter.pk])
        self.assertContains(self.client.get(url), "Delete Cover Letter")
        self.assertTrue(CoverLetter.objects.filter(pk=letter.pk).exists())
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(self.user)
        response = self.client.post(url)
        self.assertRedirects(response, reverse("dashboard") + f"?cv={self.cv.pk}#dashboard-preview")
        self.assertFalse(CoverLetter.objects.filter(pk=letter.pk).exists())
        self.assertTrue(CV.objects.filter(pk=self.cv.pk).exists())

    def test_edit_letter_saves_and_returns_to_dashboard(self):
        letter = CoverLetter.objects.create(user=self.user, cv=self.cv, content="Original letter", job_description="Role")
        url = reverse("edit_cover_letter", args=[letter.pk])
        self.assertContains(self.client.get(url), "Original letter")
        response = self.client.post(url, {"content": "Updated letter"})
        self.assertRedirects(response, reverse("dashboard") + f"?letter={letter.pk}#dashboard-preview")
        letter.refresh_from_db()
        self.assertEqual(letter.content, "Updated letter")
        self.assertEqual(letter.job_description, "Role")
        self.client.post(url, {"content": "   "})
        letter.refresh_from_db()
        self.assertEqual(letter.content, "Updated letter")
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {"content": "Unauthorized"}).status_code, 404)

    def test_dashboard_displays_selected_letter_and_source_cv(self):
        letter = CoverLetter.objects.create(user=self.user, cv=self.cv, content="Dear team,\nMy saved application.", job_description="Role")
        CV.objects.create(user=self.user, full_name="Another CV")
        response = self.client.get(reverse("dashboard"), {"letter": letter.pk})
        self.assertEqual(response.context["selected_letter"], letter)
        self.assertEqual(response.context["selected_cv"], self.cv)
        self.assertContains(response, letter.content)
        self.assertContains(response, reverse("download_cover_letter_pdf", args=[self.cv.pk]) + f"?letter={letter.pk}")
        response = self.client.get(reverse("dashboard"), {"cv": self.cv.pk})
        self.assertIsNone(response.context["selected_letter"])
        self.assertContains(response, reverse("dashboard") + f"?letter={letter.pk}#dashboard-preview")

    def test_dashboard_rejects_another_users_letter(self):
        other_cv = CV.objects.create(user=self.other, full_name="Private candidate")
        letter = CoverLetter.objects.create(user=self.other, cv=other_cv, content="Private content", job_description="Role")
        response = self.client.get(reverse("dashboard"), {"letter": letter.pk})
        self.assertEqual(response.status_code, 404)

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

class ProfessionAwarePromptTests(TestCase):
    @patch("resumes.ai_service.OpenAI")
    def test_teacher_tailoring_uses_target_profession_and_preserves_evidence(self, client):
        from resumes.ai_service import AIService

        client.return_value.chat.completions.create.return_value.choices[0].message.content = (
            '{"job_title":"English Teacher","skills":"Lesson planning"}'
        )
        source = "English Teacher at Example School, 2022-2025. PGCE. Lesson planning."
        target = "English teacher teaching literature and assessing pupil progress."
        result = AIService().tailor_cv_to_job(source, target)
        prompt = client.return_value.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        self.assertIn(source, prompt)
        self.assertIn(target, prompt)
        self.assertIn("target profession", prompt)
        self.assertIn("Missing qualifications", prompt)
        self.assertNotIn("Emphasise transferable skills from IT support", prompt)
        self.assertNotIn("The candidate has only listed Full Stack", prompt)
        self.assertEqual(result["job_title"], "English Teacher")

    @patch("resumes.ai_service.OpenAI")
    def test_import_does_not_supply_an_it_skills_template(self, client):
        from resumes.ai_service import AIService

        client.return_value.chat.completions.create.return_value.choices[0].message.content = '{}'
        AIService().parse_uploaded_cv("English teacher with a PGCE")
        prompt = client.return_value.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        self.assertIn("candidate's own profession", prompt)
        self.assertNotIn("Red Hat 7", prompt)
        self.assertNotIn("HP Servers", prompt)

@override_settings(SECURE_SSL_REDIRECT=False, STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class CVUploadTests(TestCase):
    def setUp(self):
        import tempfile
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        override = override_settings(MEDIA_ROOT=self.media.name)
        override.enable()
        self.addCleanup(override.disable)
        self.user = User.objects.create_user(username="upload-owner")
        self.client.force_login(self.user)

    def upload(self):
        from io import BytesIO
        from docx import Document
        from django.core.files.uploadedfile import SimpleUploadedFile
        document = Document()
        document.add_paragraph("Alex Example")
        document.add_paragraph("Skills")
        document.add_paragraph("Lesson planning")
        document.add_paragraph("Education")
        document.add_paragraph("PGCE")
        buffer = BytesIO()
        document.save(buffer)
        return SimpleUploadedFile("teacher.docx", buffer.getvalue())

    @patch("resumes.views.AIService")
    def test_docx_import_saves_parsed_cv(self, ai):
        ai.return_value.parse_uploaded_cv.return_value = {"full_name": "Alex Example", "job_title": "English Teacher", "skills": "Lesson planning"}
        response = self.client.post(reverse("create_cv"), {"action": "import", "uploaded_file": self.upload()})
        cv = CV.objects.get(user=self.user)
        self.assertRedirects(response, reverse("edit_cv", args=[cv.id]))
        self.assertEqual(cv.job_title, "English Teacher")
        self.assertEqual(cv.skills, "Lesson planning")

    @patch("resumes.views.AIService")
    def test_import_falls_back_if_ai_is_unavailable(self, ai):
        ai.return_value.parse_uploaded_cv.side_effect = RuntimeError("Unavailable")
        response = self.client.post(reverse("create_cv"), {"action": "import", "uploaded_file": self.upload()})
        self.assertEqual(response.status_code, 302)
        cv = CV.objects.get(user=self.user)
        self.assertEqual(cv.full_name, "Alex Example")
        self.assertIn("Lesson planning", cv.skills)

    def test_corrupt_upload_shows_error_without_creating_cv(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        response = self.client.post(reverse("create_cv"), {"action": "import", "uploaded_file": SimpleUploadedFile("broken.docx", b"broken")})
        self.assertContains(response, "This file could not be read")
        self.assertFalse(CV.objects.exists())

    @patch("resumes.views.AIService")
    def test_pdf_import_saves_parsed_cv(self, ai):
        from io import BytesIO
        from reportlab.pdfgen.canvas import Canvas
        from django.core.files.uploadedfile import SimpleUploadedFile
        buffer = BytesIO()
        canvas = Canvas(buffer)
        canvas.drawString(50, 750, "Alex Example - Plumber")
        canvas.save()
        ai.return_value.parse_uploaded_cv.return_value = {"full_name": "Alex Example", "job_title": "Plumber"}
        response = self.client.post(reverse("create_cv"), {"action": "import", "uploaded_file": SimpleUploadedFile("plumber.pdf", buffer.getvalue())})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CV.objects.get().job_title, "Plumber")

@override_settings(SECURE_SSL_REDIRECT=False, STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class TailoredCVReviewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="review-owner")
        self.client.force_login(self.user)
        self.source = CV.objects.create(user=self.user, full_name="Alex", job_title="Teacher", skills="Lesson planning", experience="Taught English")

    @patch("resumes.views.AIService")
    def test_tailoring_redirects_to_editable_comparison_and_preserves_source(self, ai):
        ai.return_value.tailor_cv_to_job.return_value = {"job_title": "English Teacher", "skills": "Lesson planning and assessment"}
        ai.return_value.analyse_job_description.return_value = {"match_score": 70}
        self.client.post(reverse("job_match", args=[self.source.id]), {"job_description": "English teacher"})
        response = self.client.post(reverse("tailor_cv_to_job", args=[self.source.id]), {"job_description": "English teacher"})
        tailored = CV.objects.exclude(id=self.source.id).get()
        self.assertRedirects(response, reverse("review_tailored_cv", args=[tailored.id]))
        self.assertEqual(tailored.original_content["skills"], "Lesson planning")
        response = self.client.get(reverse("review_tailored_cv", args=[tailored.id]))
        self.assertContains(response, "<mark>and assessment</mark>", html=True)
        self.assertContains(response, "Unchanged")
        response = self.client.post(reverse("review_tailored_cv", args=[tailored.id]), {"job_title": "English Teacher", "skills": "My corrected skills", "experience": "Taught English"})
        self.assertRedirects(response, reverse("dashboard"))
        tailored.refresh_from_db()
        self.source.refresh_from_db()
        self.assertEqual(tailored.skills, "My corrected skills")
        self.assertEqual(self.source.skills, "Lesson planning")
        self.assertEqual(tailored.original_content["skills"], "Lesson planning")

    def test_review_is_private_and_comparison_escapes_html(self):
        self.source.original_content = {"skills": "<script>alert(1)</script>"}
        self.source.skills = "<img src=x onerror=alert(1)>"
        self.source.save()
        response = self.client.get(reverse("review_tailored_cv", args=[self.source.id]))
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertNotContains(response, "<img src=x onerror=alert(1)>")
        other = User.objects.create_user(username="other-reviewer")
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("review_tailored_cv", args=[self.source.id])).status_code, 404)
        self.assertEqual(self.client.post(reverse("review_tailored_cv", args=[self.source.id]), {"skills": "Changed"}).status_code, 404)

@override_settings(SECURE_SSL_REDIRECT=False, STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class FreeDocumentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="free-reader")
        self.cv = CV.objects.create(user=self.user, full_name="Free Candidate", experience="Work experience")
        self.letter = CoverLetter.objects.create(user=self.user, cv=self.cv, job_description="Role", content="Dear Hiring Manager,\n" + "Relevant professional experience.\n" * 120)
        self.client.force_login(self.user)

    def pdf_pages(self, response):
        from io import BytesIO
        from pypdf import PdfReader
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        return PdfReader(BytesIO(response.content)).pages

    def test_free_downloads_watermark_every_page_for_every_template(self):
        for template in ["modern", "classic", "executive", "unknown"]:
            FreeDownloadUsage.objects.filter(user=self.user).delete()
            response = self.client.get(reverse("download_cv_pdf", args=[self.cv.id]), {"template": template, "is_premium": "true"})
            for page in self.pdf_pages(response):
                self.assertIn("AI CV Builder - Free Version", page.extract_text())
        FreeDownloadUsage.objects.filter(user=self.user).delete()
        response = self.client.get(reverse("download_cover_letter_pdf", args=[self.cv.id]))
        pages = self.pdf_pages(response)
        self.assertGreater(len(pages), 1)
        for page in pages:
            self.assertIn("AI CV Builder - Free Version", page.extract_text())

    def test_premium_downloads_have_no_free_watermark(self):
        Subscription.objects.create(user=self.user, is_active=True, plan_name="Premium")
        for route in ["download_cv_pdf", "download_cover_letter_pdf"]:
            for page in self.pdf_pages(self.client.get(reverse(route, args=[self.cv.id]))):
                self.assertNotIn("AI CV Builder - Free Version", page.extract_text())

    @patch("resumes.views.AIService")
    def test_free_users_can_generate_letters_and_open_templates(self, ai):
        ai.return_value.generate_cover_letter.return_value = "A new letter"
        session = self.client.session
        session["last_job_description"] = "A new role"
        session.save()
        response = self.client.post(reverse("create_cover_letter", args=[self.cv.id]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(CoverLetter.objects.filter(content="A new letter", user=self.user).exists())
        self.assertContains(self.client.get(reverse("select_pdf_template", args=[self.cv.id])), "include a watermark")
        self.assertContains(self.client.get(reverse("cv_preview", args=[self.cv.id])), "free-document")
        Subscription.objects.create(user=self.user, is_active=True, plan_name="Premium")
        self.assertNotContains(self.client.get(reverse("cv_preview", args=[self.cv.id])), "free-document")

    def test_downloads_remain_private(self):
        other = User.objects.create_user(username="another-reader")
        self.client.force_login(other)
        for route in ["download_cv_pdf", "download_cover_letter_pdf"]:
            self.assertEqual(self.client.get(reverse(route, args=[self.cv.id])).status_code, 404)

@override_settings(SECURE_SSL_REDIRECT=False, STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class FreeCVLimitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="limited-user")
        self.client.force_login(self.user)
        self.cvs = [CV.objects.create(user=self.user, full_name=f"CV {i}") for i in range(3)]

    @patch("resumes.views.AIService")
    def test_limit_blocks_manual_upload_and_tailoring_before_ai(self, ai):
        from django.core.files.uploadedfile import SimpleUploadedFile
        attempts = [
            (reverse("create_cv"), {"full_name": "Fourth"}),
            (reverse("create_cv"), {"action": "import", "uploaded_file": SimpleUploadedFile("cv.pdf", b"example")}),
            (reverse("tailor_cv_to_job", args=[self.cvs[0].id]), {"job_description": "Role"}),
        ]
        for url, data in attempts:
            response = self.client.post(url, data)
            self.assertContains(response, "Free plan CV limit reached", status_code=403)
        self.assertEqual(CV.objects.filter(user=self.user).count(), 3)
        ai.assert_not_called()

    def test_deleting_a_cv_allows_a_replacement(self):
        self.cvs[-1].delete()
        response = self.client.post(reverse("create_cv"), {"full_name": "Replacement", "template": "modern"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CV.objects.filter(user=self.user).count(), 3)

    def test_premium_can_create_more_than_three(self):
        Subscription.objects.create(user=self.user, is_active=True, plan_name="Premium")
        response = self.client.post(reverse("create_cv"), {"full_name": "Fourth", "template": "modern"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CV.objects.filter(user=self.user).count(), 4)

    def test_existing_documents_remain_accessible_above_limit(self):
        CV.objects.create(user=self.user, full_name="Existing fourth CV")
        for route in ["edit_cv", "download_cv_pdf"]:
            self.assertEqual(self.client.get(reverse(route, args=[self.cvs[0].id])).status_code, 200)
        self.assertEqual(self.client.get(reverse("create_cv")).status_code, 403)

@override_settings(SECURE_SSL_REDIRECT=False, STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class DownloadLimitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="download-limit")
        self.client.force_login(self.user)
        self.cv = CV.objects.create(user=self.user, full_name="Example")
        CoverLetter.objects.create(user=self.user, cv=self.cv, content="Letter", job_description="Role")

    def test_three_combined_downloads_then_repeat_is_blocked(self):
        for route in ["download_cv_pdf", "download_cover_letter_pdf", "download_cv_pdf"]:
            self.assertEqual(self.client.get(reverse(route, args=[self.cv.id])).status_code, 200)
        self.client.logout()
        self.client.force_login(self.user)
        response = self.client.get(reverse("download_cover_letter_pdf", args=[self.cv.id]))
        self.assertContains(response, "Free download limit reached", status_code=403)
        self.assertEqual(FreeDownloadUsage.objects.get(user=self.user).downloads, 3)
        self.cv.delete()
        replacement = CV.objects.create(user=self.user, full_name="Replacement")
        self.assertEqual(self.client.get(reverse("download_cv_pdf", args=[replacement.id])).status_code, 403)

    def test_missing_letter_redirect_does_not_consume_allowance(self):
        CoverLetter.objects.all().delete()
        self.assertEqual(self.client.get(reverse("download_cover_letter_pdf", args=[self.cv.id])).status_code, 302)
        self.assertEqual(FreeDownloadUsage.objects.get(user=self.user).downloads, 0)

    def test_premium_bypasses_exhausted_allowance(self):
        FreeDownloadUsage.objects.create(user=self.user, downloads=3)
        sub = Subscription.objects.create(user=self.user, is_active=True, plan_name="Premium")
        for _ in range(4):
            self.assertEqual(self.client.get(reverse("download_cv_pdf", args=[self.cv.id])).status_code, 200)
        self.assertEqual(FreeDownloadUsage.objects.get(user=self.user).downloads, 3)
        sub.is_active = False
        sub.save()
        self.assertEqual(self.client.get(reverse("download_cv_pdf", args=[self.cv.id])).status_code, 403)

@override_settings(SECURE_SSL_REDIRECT=False, STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class CancelSubscriptionTests(TestCase):
    def setUp(self):
        from django.utils import timezone
        from datetime import timedelta
        self.user = User.objects.create_user(username="cancel-owner")
        self.client.force_login(self.user)
        self.sub = Subscription.objects.create(user=self.user, is_active=True, plan_name="Premium", stripe_subscription_id="sub_own")
        self.end = timezone.now() + timedelta(days=10)
        self.cv = CV.objects.create(user=self.user, full_name="Saved")

    @patch("resumes.views.stripe.Subscription.modify")
    def test_confirmation_then_cancellation_keeps_account_and_access(self, modify):
        import stripe
        modify.return_value = stripe.Subscription.construct_from({"cancel_at": int(self.end.timestamp())}, "test-key")
        self.assertContains(self.client.get(reverse("cancel_subscription")), "Confirm cancellation")
        modify.assert_not_called()
        self.assertRedirects(self.client.post(reverse("cancel_subscription")), reverse("pricing"))
        self.sub.refresh_from_db()
        self.assertTrue(self.sub.cancel_at_period_end)
        self.assertTrue(self.sub.has_premium_access)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertTrue(CV.objects.filter(pk=self.cv.pk).exists())
        self.assertEqual(modify.call_args.args, ("sub_own",))
        self.client.post(reverse("cancel_subscription"))
        self.assertEqual(modify.call_count, 1)

    def test_premium_expires_without_webhook(self):
        from django.utils import timezone
        from datetime import timedelta
        from resumes.views import user_has_active_subscription
        self.sub.cancel_at_period_end = True
        self.sub.premium_until = timezone.now() - timedelta(seconds=1)
        self.sub.save()
        self.assertFalse(user_has_active_subscription(self.user))
        self.assertContains(self.client.get(reverse("cv_preview", args=[self.cv.pk])), "free-document")

    @patch("resumes.views.stripe.Subscription.modify")
    def test_failure_does_not_claim_cancellation(self, modify):
        import stripe
        modify.side_effect = stripe.APIConnectionError("Unavailable")
        self.assertContains(self.client.post(reverse("cancel_subscription")), "could not confirm")
        self.sub.refresh_from_db()
        self.assertFalse(self.sub.cancel_at_period_end)

    @patch("resumes.views.stripe.Subscription.modify")
    def test_free_user_cannot_cancel_someone_elses_plan(self, modify):
        other = User.objects.create_user(username="cancel-other")
        self.client.force_login(other)
        self.client.post(reverse("cancel_subscription"), {"subscription_id": "sub_own"})
        modify.assert_not_called()


    @patch("resumes.views.stripe.Subscription.modify")
    def test_stripe_item_period_end_is_supported(self, modify):
        import stripe
        modify.return_value = stripe.Subscription.construct_from({
            "cancel_at": None,
            "items": {"data": [{"current_period_end": int(self.end.timestamp())}]},
        }, "test-key")
        self.assertRedirects(self.client.post(reverse("cancel_subscription")), reverse("pricing"))
        self.sub.refresh_from_db()
        self.assertTrue(self.sub.cancel_at_period_end)
        self.assertEqual(int(self.sub.premium_until.timestamp()), int(self.end.timestamp()))

@override_settings(SECURE_SSL_REDIRECT=False, STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class ApplicationPackTests(TestCase):
    def setUp(self):
        from .models import ApplicationPack
        self.Pack = ApplicationPack
        self.user = User.objects.create_user(username="pack-owner")
        self.client.force_login(self.user)
        self.cv = CV.objects.create(user=self.user, full_name="Pack Candidate")
        CoverLetter.objects.create(user=self.user, cv=self.cv, content="Saved letter", job_description="Role")
        FreeDownloadUsage.objects.create(user=self.user, downloads=3)
        self.session = {"id": "cs_pack_example", "mode": "payment", "payment_status": "paid", "currency": "gbp", "amount_total": 199, "metadata": {"purchase": "application_pack", "user_id": str(self.user.pk)}}

    def test_fulfilment_is_paid_validated_and_idempotent(self):
        from .payments import fulfil_application_pack
        for override in [{"payment_status": "unpaid"}, {"amount_total": 1}, {"currency": "usd"}, {"mode": "subscription"}]:
            self.assertFalse(fulfil_application_pack(dict(self.session, **override)))
        self.assertFalse(self.Pack.objects.exists())
        self.assertTrue(fulfil_application_pack(self.session))
        self.assertTrue(fulfil_application_pack(self.session))
        self.assertEqual(self.Pack.objects.count(), 1)

    def test_separate_allowances_and_clean_downloads(self):
        from .payments import fulfil_application_pack
        from io import BytesIO
        from pypdf import PdfReader
        fulfil_application_pack(self.session)
        for _ in range(3):
            response = self.client.get(reverse("download_cv_pdf", args=[self.cv.pk]))
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("AI CV Builder - Free Version", PdfReader(BytesIO(response.content)).pages[0].extract_text())
        self.assertEqual(self.client.get(reverse("download_cv_pdf", args=[self.cv.pk])).status_code, 403)
        pack = self.Pack.objects.get()
        self.assertEqual(pack.letter_downloads, 3)
        for _ in range(3):
            self.assertEqual(self.client.get(reverse("download_cover_letter_pdf", args=[self.cv.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("download_cover_letter_pdf", args=[self.cv.pk])).status_code, 403)
        self.assertEqual(FreeDownloadUsage.objects.get(user=self.user).downloads, 3)

    @patch("resumes.views.stripe.checkout.Session.create")
    def test_checkout_uses_fixed_one_off_price(self, create):
        create.return_value.url = "https://checkout.stripe.com/example"
        self.assertEqual(self.client.get(reverse("buy_application_pack")).status_code, 405)
        self.assertEqual(self.client.post(reverse("buy_application_pack"), {"amount": 1}).status_code, 302)
        args = create.call_args.kwargs
        self.assertEqual(args["mode"], "payment")
        self.assertEqual(args["line_items"][0]["price_data"]["unit_amount"], 199)
        self.assertEqual(args["metadata"]["user_id"], str(self.user.pk))

    @patch("resumes.views.stripe.Webhook.construct_event")
    def test_pack_webhook_never_activates_premium(self, event):
        import stripe
        event.return_value = stripe.Event.construct_from({"type": "checkout.session.completed", "data": {"object": self.session}}, "test-key")
        for _ in range(2):
            self.assertEqual(self.client.post(reverse("stripe_webhook"), data=b"{}", content_type="application/json").status_code, 200)
        self.assertEqual(self.Pack.objects.count(), 1)
        self.assertFalse(Subscription.objects.filter(user=self.user).exists())

    @patch("resumes.views.stripe.checkout.Session.retrieve")
    def test_success_cannot_claim_another_users_payment(self, retrieve):
        import stripe
        other = User.objects.create_user(username="pack-intruder")
        self.client.force_login(other)
        retrieve.return_value = stripe.checkout.Session.construct_from(self.session, "test-key")
        self.client.get(reverse("application_pack_success"), {"session_id": self.session["id"]})
        self.assertFalse(self.Pack.objects.exists())
