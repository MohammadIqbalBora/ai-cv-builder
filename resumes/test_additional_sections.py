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
    PROJECT_TEXT = """Example Candidate
Education
Web Development Bootcamp
Projects
AI CV Builder | Django | PostgreSQL | OpenAI API
• Built and deployed a CV application.
• Integrated Stripe subscription payments.
Currency & Weather Hub | JavaScript | REST APIs
• Used Fetch API to update content dynamically.
Halal Bites | HTML5 | CSS3 | Bootstrap
• Added a contact form and embedded location map.
Languages
English
"""
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

    @patch("resumes.views.AIService")
    def test_uploaded_docx_recovers_projects_omitted_by_ai(self, ai):
        from docx import Document
        from django.utils.html import escape
        ai.return_value.parse_uploaded_cv.return_value = {"full_name": "Example Candidate"}
        document = Document()
        for line in self.PROJECT_TEXT.splitlines():
            document.add_paragraph(line)
        stream = BytesIO()
        document.save(stream)
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            response = self.client.post(reverse("create_cv"), {
                "action": "import",
                "uploaded_file": SimpleUploadedFile("cv.docx", stream.getvalue()),
            })
            cv = CV.objects.get(user=self.user)
            self.assertRedirects(response, reverse("edit_cv", args=[cv.pk]))
            projects = next(section for section in cv.additional_sections if section["title"] == "Projects")
            for name in ["AI CV Builder", "Currency & Weather Hub", "Halal Bites"]:
                self.assertIn(name, projects["content"])
                self.assertContains(self.client.get(reverse("dashboard")), escape(name))
            for template, _ in CV.TEMPLATE_CHOICES:
                with self.subTest(template=template):
                    pdf = self.client.get(reverse("download_cv_pdf", args=[cv.pk]), {"template": template})
                    self.assertEqual(pdf.status_code, 200)
                    text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages)
                    self.assertIn("projects", text.casefold())
                    for name in ["AI CV Builder", "Currency & Weather Hub", "Halal Bites"]:
                        self.assertIn(name, text)

    @patch("resumes.views.AIService")
    def test_fallback_preserves_projects_separately_from_education(self, ai):
        from resumes.views import parse_cv_with_ai_or_fallback
        ai.return_value.parse_uploaded_cv.side_effect = RuntimeError("Unavailable")
        data = parse_cv_with_ai_or_fallback(self.PROJECT_TEXT)
        self.assertEqual(data["education"], "Web Development Bootcamp")
        self.assertEqual(data["additional_sections"][0]["title"], "Projects")
        self.assertIn("Halal Bites", data["additional_sections"][0]["content"])
        self.assertNotIn("English", data["additional_sections"][0]["content"])

    @patch("resumes.views.AIService")
    def test_import_preserves_employers_roles_and_dates_in_all_templates(self, ai):
        from docx import Document
        experience = (
            "DXC Technologies\nMobile IT Field Engineer (Contract)\nJune 2025 - August 2025\n"
            "Provided onsite technical support.\n"
            "London Fire Brigade (LFB)\nBridge Engineer (Contract)\nMay 2024 - August 2024\n"
            "Monitored critical services."
        )
        ai.return_value.parse_uploaded_cv.return_value = {
            "full_name": "Example Candidate",
            "experience": "June 2025 - August 2025\nProvided onsite technical support.",
        }
        document = Document()
        for line in ("Example Candidate\nWork Experience\n" + experience + "\nEducation\nDiploma").splitlines():
            document.add_paragraph(line)
        stream = BytesIO()
        document.save(stream)
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            response = self.client.post(reverse("create_cv"), {
                "action": "import", "uploaded_file": SimpleUploadedFile("cv.docx", stream.getvalue()),
            })
            cv = CV.objects.get(user=self.user)
            self.assertRedirects(response, reverse("edit_cv", args=[cv.pk]))
            self.assertEqual(cv.experience, experience)
            for template, _ in CV.TEMPLATE_CHOICES:
                with self.subTest(template=template):
                    response = self.client.get(reverse("download_cv_pdf", args=[cv.pk]), {"template": template})
                    self.assertEqual(response.status_code, 200)
                    text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)
                    for expected in ["DXC Technologies", "Mobile IT Field Engineer (Contract)",
                                     "June 2025 - August 2025", "London Fire Brigade (LFB)",
                                     "Bridge Engineer (Contract)", "May 2024 - August 2024"]:
                        self.assertIn(expected, text)

    def test_word_tables_are_extracted_in_document_order(self):
        from docx import Document
        from resumes.cv_parser import extract_text_from_docx
        document = Document()
        document.add_paragraph("Example Candidate")
        table = document.add_table(rows=2, cols=1)
        table.cell(0, 0).text = "Professional Memberships"
        table.cell(1, 0).text = "Member of Example Institute"
        document.add_paragraph("Achievements")
        document.add_paragraph("Completed an accessibility improvement project")
        stream = BytesIO()
        document.save(stream)
        stream.seek(0)
        self.assertEqual(extract_text_from_docx(stream).splitlines(), [
            "Example Candidate", "Professional Memberships", "Member of Example Institute",
            "Achievements", "Completed an accessibility improvement project",
        ])

    @patch("resumes.views.AIService")
    def test_hidden_demo_links_survive_word_pdf_import_and_all_exports(self, ai):
        from docx import Document
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from docx.opc.constants import RELATIONSHIP_TYPE
        from reportlab.pdfgen import canvas
        projects = [
            ("AI CV Builder", "https://cv.example.com/demo"),
            ("Weather Hub", "https://weather.example.com/?city=London&units=metric"),
        ]
        ai.return_value.parse_uploaded_cv.return_value = {
            "full_name": "Example Candidate", "additional_sections": [
                {"title": "Projects", "content": "AI CV Builder | Live demo\nWeather Hub | Live demo"},
            ],
        }
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            for extension in ["docx", "pdf"]:
                stream = BytesIO()
                if extension == "docx":
                    document = Document()
                    document.add_paragraph("Example Candidate")
                    document.add_paragraph("Projects")
                    for name, url in projects:
                        paragraph = document.add_paragraph(name + " | ")
                        link = OxmlElement("w:hyperlink")
                        link.set(qn("r:id"), paragraph.part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True))
                        run = OxmlElement("w:r")
                        text = OxmlElement("w:t")
                        text.text = "Live demo"
                        run.append(text)
                        link.append(run)
                        paragraph._p.append(link)
                    document.save(stream)
                else:
                    pdf = canvas.Canvas(stream)
                    pdf.drawString(50, 780, "Example Candidate")
                    pdf.drawString(50, 750, "Projects")
                    for index, (name, url) in enumerate(projects):
                        y = 720 - index * 30
                        pdf.drawString(50, y, name + " |")
                        pdf.drawString(200, y, "Live demo")
                        pdf.linkURL(url, (200, y - 2, 280, y + 12))
                    pdf.save()
                response = self.client.post(reverse("create_cv"), {
                    "action": "import", "uploaded_file": SimpleUploadedFile("cv." + extension, stream.getvalue()),
                })
                self.assertEqual(response.status_code, 302)
                cv = CV.objects.filter(user=self.user).latest("pk")
                for name, url in projects:
                    self.assertIn(f"{name} | Live demo ({url})", " ".join(cv.additional_sections[0]["content"].split()))
                for template, _ in CV.TEMPLATE_CHOICES:
                    with self.subTest(upload=extension, template=template):
                        response = self.client.get(reverse("download_cv_pdf", args=[cv.pk]), {"template": template})
                        pages = PdfReader(BytesIO(response.content)).pages
                        urls = {annotation.get_object().get("/A", {}).get("/URI")
                                for page in pages for annotation in page.get("/Annots", [])}
                        for _, url in projects:
                            self.assertIn(url, urls)

    def test_other_sections_and_heading_variants_survive_all_pdf_templates(self):
        from resumes.cv_parser import parse_cv_text
        from resumes.views import import_data_into_cv
        extra = [
            ("Achievements", "Improved accessibility"),
            ("Professional Memberships", "Member of Example Institute"),
            ("Voluntary Work", "Community support volunteer"),
            ("Languages", "English and French"),
            ("Awards", "Service award recipient"),
            ("Publications", "Published research article"),
            ("Interests & Hobbies", "Hiking and photography"),
            ("References", "Available on request"),
        ]
        text = "\n".join([
            "Example Candidate", "Professional Summary:", "Experienced developer",
            "Key Skills", "Python and Django", "Career History", "Software Developer at Example",
            "Qualifications", "Web Development Diploma", "Certifications", "Cloud Practitioner Certificate",
        ] + [line for section in extra for line in section])
        data = parse_cv_text(text)
        self.assertEqual(data["professional_summary"], "Experienced developer")
        self.assertEqual(data["skills"], "Python and Django")
        self.assertEqual(data["experience"], "Software Developer at Example")
        self.assertIn("Web Development Diploma", data["education"])
        self.assertIn("Cloud Practitioner Certificate", data["education"])
        self.assertEqual(data["additional_sections"], [{"title": title, "content": content} for title, content in extra])
        cv = CV.objects.create(user=self.user, full_name="Example Candidate")
        import_data_into_cv(cv, data)
        for template, _ in CV.TEMPLATE_CHOICES:
            with self.subTest(template=template):
                response = self.client.get(reverse("download_cv_pdf", args=[cv.pk]), {"template": template})
                self.assertEqual(response.status_code, 200)
                pdf_text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)
                for title, content in extra:
                    self.assertIn(title.casefold(), pdf_text.casefold())
                    self.assertIn(content, pdf_text)
                self.assertIn("Web Development Diploma", pdf_text)
                self.assertIn("Cloud Practitioner Certificate", pdf_text)

    @patch("resumes.views.AIService")
    def test_ai_sections_stay_structured_and_manual_sections_take_precedence(self, ai):
        from resumes.views import parse_cv_with_ai_or_fallback, import_data_into_cv
        ai.return_value.parse_uploaded_cv.return_value = {"additional_sections": self.sections}
        data = parse_cv_with_ai_or_fallback("Example Candidate")
        self.assertEqual(data["additional_sections"], self.sections)
        manual = {"title": "Interests and hobbies", "content": "Reading"}
        cv = CV.objects.create(user=self.user, full_name="Example", additional_sections=[manual])
        import_data_into_cv(cv, data)
        cv.refresh_from_db()
        self.assertEqual(cv.additional_sections, [manual, self.sections[1]])

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
