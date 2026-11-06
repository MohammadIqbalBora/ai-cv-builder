from io import BytesIO

from django.test import SimpleTestCase
from pypdf import PdfReader

from .models import CV
from .modern_pdf import render_modern_pdf
from .tailoring_guard import protect_source_sections


class TailoringGuardTests(SimpleTestCase):
    def test_projects_cannot_replace_employment_or_drop_skills_and_qualifications(self):
        cv = CV(experience="Engineer at Cerco, June 2025. Supported hardware.",
                skills="Python, Django, PostgreSQL, Chrome DevTools", education="Solaris Certification",
                professional_summary="Built personal applications.", additional_sections=[
                    {"title": "Projects", "content": "AI CV Builder | Django | Live demo"}])
        result, restored = protect_source_sections(cv, {
            "experience": "AI CV Builder | Django | Live demo", "skills": "Django",
            "education": "", "professional_summary": "Recognized for innovative projects."})
        for field in ("experience", "skills", "education", "professional_summary"):
            self.assertEqual(result[field], getattr(cv, field))
            self.assertIn(field, restored)

    def test_project_duplication_is_rejected_even_when_employment_is_retained(self):
        cv = CV(experience="Teacher at School 2024", additional_sections=[
            {"title": "Projects", "content": "Weather Hub | JavaScript"}])
        result, _ = protect_source_sections(cv, {"experience": cv.experience + "\nWeather Hub | JavaScript"})
        self.assertEqual(result["experience"], cv.experience)

    def test_source_faithful_rewrite_and_explicit_recognition_are_allowed(self):
        cv = CV(experience="Engineer at Example 2024", skills="Python", education="Degree",
                professional_summary="Recognized for service.")
        proposed = {"experience": "Example: Engineer (2024)", "skills": "Languages: Python",
                    "education": "Degree", "professional_summary": "Recognized for service."}
        result, restored = protect_source_sections(cv, proposed)
        self.assertEqual(result, proposed)
        self.assertEqual(restored, [])

    def test_modern_skills_wrap_without_losing_comma_separated_or_overflow_entries(self):
        skills = ["HTML5", "CSS3", "JavaScript", "Django", "PostgreSQL", "OpenAI API", "Chrome DevTools"]
        cv = CV(full_name="Applicant", email="long.email.address.with.many.characters@example.com",
                skills=", ".join(skills) + "\n" + "\n".join(f"Skill number {i}" for i in range(100)))
        reader = PdfReader(BytesIO(render_modern_pdf(cv).content))
        text = "\n".join(page.extract_text() for page in reader.pages)
        for skill in skills:
            self.assertIn(skill, text)
        self.assertIn("Skill number 99", text)
        self.assertIn("CONTINUED", text)
