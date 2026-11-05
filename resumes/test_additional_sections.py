from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfReader

from .forms import CVForm
from .models import CV, Subscription


@override_settings(
    SECURE_SSL_REDIRECT=False,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class AdditionalSectionsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="extra-sections-owner")
        Subscription.objects.create(user=self.user, is_active=True, plan_name="Premium")
        self.client.force_login(self.user)
        self.sections = [
            {"title": "Interests and hobbies", "content": "Hiking\nPhotography"},
            {"title": "Professional memberships", "content": "Member of Example Institute"},
        ]

    def payload(self, sections=None):
        sections = self.sections if sections is None else sections
        return {
            "full_name": "Example Candidate", "template": "modern", "action": "save",
            "additional_sections_title": [section["title"] for section in sections],
            "additional_sections_content": [section["content"] for section in sections],
        }

    def test_create_edit_remove_and_reload(self):
        self.assertContains(self.client.get(reverse("create_cv")), "Add section")
        response = self.client.post(reverse("create_cv"), self.payload())
        self.assertRedirects(response, reverse("dashboard"))
        cv = CV.objects.get(user=self.user)
        self.assertEqual(cv.additional_sections, self.sections)
        edit_url = reverse("edit_cv", args=[cv.pk])
        response = self.client.get(edit_url)
        self.assertContains(response, "Member of Example Institute")
        self.assertContains(response, 'value="Professional memberships"')
        changed = [{"title": "Languages", "content": "English and French"}]
        self.assertRedirects(self.client.post(edit_url, self.payload(changed)), reverse("dashboard"))
        cv.refresh_from_db()
        self.assertEqual(cv.additional_sections, changed)
        self.client.post(edit_url, self.payload([]))
        cv.refresh_from_db()
        self.assertEqual(cv.additional_sections, [])

    def test_blank_rows_are_ignored_and_partial_rows_redisplayed(self):
        blank = [{"title": " ", "content": "\n"}]
        form = CVForm(data=self.payload(blank))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["additional_sections"], [])
        response = self.client.post(reverse("create_cv"), self.payload([{"title": "Keep this heading", "content": ""}]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("additional_sections", response.context["form"].errors)
        self.assertContains(response, 'value="Keep this heading"')
        self.assertFalse(CV.objects.filter(user=self.user).exists())

    def test_section_count_and_lengths_are_validated_on_server(self):
        for sections in (
            [{"title": "Section", "content": "Details"}] * 11,
            [{"title": "x" * 81, "content": "Details"}],
            [{"title": "Heading", "content": "x" * 5001}],
        ):
            with self.subTest(sections=len(sections)):
                form = CVForm(data=self.payload(sections))
                self.assertFalse(form.is_valid())
                self.assertIn("additional_sections", form.errors)

    def test_previews_escape_custom_content_and_keep_line_breaks(self):
        cv = CV.objects.create(user=self.user, full_name="Example", additional_sections=[
            {"title": "<script>Heading</script>", "content": "<img src=x onerror=alert(1)>\nSecond line"},
        ])
        for template in ("modern", "classic", "executive"):
            cv.template = template
            cv.save()
            for route in ("cv_preview", "cv_detail"):
                with self.subTest(template=template, route=route):
                    response = self.client.get(reverse(route, args=[cv.pk]))
                    self.assertContains(response, "&lt;script&gt;Heading&lt;/script&gt;")
                    self.assertContains(response, "<br>Second line")
                    self.assertNotContains(response, "<img src=x")

    def test_all_pdf_templates_include_extra_sections_across_pages(self):
        cv = CV.objects.create(user=self.user, full_name="Example", additional_sections=self.sections + [
            {"title": "Volunteer experience", "content": ("Helping the community every weekend.\n" * 90) + "Final volunteer entry"},
        ])
        for template in ("modern", "classic", "executive"):
            with self.subTest(template=template):
                response = self.client.get(reverse("download_cv_pdf", args=[cv.pk]), {"template": template})
                pages = PdfReader(BytesIO(response.content)).pages
                self.assertGreater(len(pages), 1)
                text = "\n".join(page.extract_text() for page in pages)
                self.assertIn("interests and hobbies", text.lower())
                self.assertIn("Member of Example Institute", text)
                self.assertIn("Final volunteer entry", text)

    @patch("resumes.views.AIService")
    def test_tailored_copy_preserves_extra_sections(self, ai):
        cv = CV.objects.create(user=self.user, full_name="Example", additional_sections=self.sections)
        ai.return_value.tailor_cv_to_job.return_value = {"skills": "Communication"}
        ai.return_value.analyse_job_description.return_value = {"match_score": 70}
        self.client.post(reverse("job_match", args=[cv.pk]), {"job_description": "Example role"})
        response = self.client.post(reverse("tailor_cv_to_job", args=[cv.pk]), {"job_description": "Example role"})
        self.assertEqual(response.status_code, 302)
        tailored = CV.objects.exclude(pk=cv.pk).get(user=self.user)
        self.assertEqual(tailored.additional_sections, self.sections)
        cv.refresh_from_db()
        self.assertEqual(cv.additional_sections, self.sections)

    @patch("resumes.views.parse_cv_with_ai_or_fallback", return_value={"full_name": "Imported Candidate"})
    @patch("resumes.cv_parser.extract_text_from_pdf", return_value="Candidate details")
    def test_import_preserves_manually_entered_sections(self, extract, parse):
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            data = self.payload()
            data.update(action="import", full_name="", uploaded_file=SimpleUploadedFile("cv.pdf", b"example"))
            response = self.client.post(reverse("create_cv"), data)
            cv = CV.objects.get(user=self.user)
            self.assertRedirects(response, reverse("edit_cv", args=[cv.pk]))
            self.assertEqual(cv.additional_sections, self.sections)

    def test_edit_is_restricted_to_owner(self):
        cv = CV.objects.create(user=self.user, full_name="Example", additional_sections=self.sections)
        other = User.objects.create_user(username="other-sections-user")
        self.client.force_login(other)
        response = self.client.post(reverse("edit_cv", args=[cv.pk]), self.payload([]))
        self.assertEqual(response.status_code, 404)
        cv.refresh_from_db()
        self.assertEqual(cv.additional_sections, self.sections)
