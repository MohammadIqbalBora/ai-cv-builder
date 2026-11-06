"""Section ordering changes without replacing any template design."""
from io import BytesIO

from django.template.loader import render_to_string
from django.test import SimpleTestCase
from pypdf import PdfReader

from .classic_pdf import render_classic_pdf
from .executive_pdf import render_executive_pdf
from .models import CV
from .modern_pdf import render_modern_pdf


class ProjectOrderTests(SimpleTestCase):
    def test_ranked_project_evidence_appears_once_in_each_original_design(self):
        for projects_first in (True, False):
            order = ["additional:0", "experience"] if projects_first else ["experience", "additional:0"]
            cv = CV(full_name="Candidate", experience="Employment evidence", skills="Python",
                    professional_summary="Profile evidence", education="Qualification evidence",
                    section_order=order, additional_sections=[
                        {"title": "Projects", "content": "Project evidence"},
                        {"title": "Interests", "content": "Interest evidence"}])
            for renderer in (render_modern_pdf, render_classic_pdf, render_executive_pdf):
                with self.subTest(renderer=renderer.__name__, projects_first=projects_first):
                    reader = PdfReader(BytesIO(renderer(cv).content))
                    text = "\n".join(page.extract_text() for page in reader.pages)
                    self.assertEqual(text.count("Project evidence"), 1)
                    self.assertEqual(text.count("Interest evidence"), 1)
                    self.assertEqual(text.index("Project evidence") < text.index("Employment evidence"), projects_first)
            for template in ("cv_detail.html", "cv_preview.html"):
                for design in ("modern", "classic", "executive"):
                    cv.template = design
                    cv.pk = 1
                    html = render_to_string(template, {"cv": cv})
                    self.assertEqual(html.count("Project evidence"), 1)
                    self.assertEqual(html.index("Project evidence") < html.index("Employment evidence"), projects_first)

    def test_unranked_or_invalid_order_preserves_legacy_default(self):
        for order in ([], ["additional:0"], ["invented", {"bad": "value"}]):
            cv = CV(section_order=order, additional_sections=[{"title": "Projects", "content": "Evidence"}])
            self.assertFalse(cv.projects_first)
            self.assertEqual(cv.leading_projects, [])
            self.assertEqual(cv.trailing_sections, cv.additional_sections)
        self.assertTrue(CV().classic_projects_first)
