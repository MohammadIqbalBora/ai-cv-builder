from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import CV, CoverLetter, Subscription


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
