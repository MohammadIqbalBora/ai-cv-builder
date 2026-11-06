from django.test import SimpleTestCase

from .models import CV
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
