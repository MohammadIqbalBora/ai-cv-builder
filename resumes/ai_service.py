import os
from openai import OpenAI


class AIService:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # --------------------------------------------------
    # MAIN AI: CV IMPROVEMENT
    # --------------------------------------------------
    def improve_cv(self, cv_text, template="modern"):
        prompt = self._build_cv_prompt(cv_text, template)

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional CV writing assistant."},
                {"role": "user", "content": prompt}
            ]
        )

        return response.choices[0].message.content

    # --------------------------------------------------
    # MAIN AI: COVER LETTER
    # --------------------------------------------------
    def generate_cover_letter(self, cv_text, job_description, template="modern"):
        prompt = self._build_cover_letter_prompt(cv_text, job_description, template)

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional cover letter writer."},
                {"role": "user", "content": prompt}
            ]
        )

        return response.choices[0].message.content

    # --------------------------------------------------
    # 🧠 NEW: AI TEMPLATE SELECTOR
    # --------------------------------------------------
    def suggest_template(self, job_title: str, summary: str = "", skills: str = ""):
        """
        Auto-select best CV template based on role.
        Returns: modern | classic | executive
        """

        text = f"{job_title} {summary} {skills}".lower()

        executive_keywords = [
            "manager", "director", "head", "chief", "ceo",
            "lead", "senior manager", "operations", "consultant",
            "executive", "vp"
        ]

        modern_keywords = [
            "developer", "engineer", "software", "data",
            "designer", "ui", "ux", "frontend", "backend",
            "full stack", "programmer", "it"
        ]

        classic_keywords = [
            "admin", "assistant", "clerk", "receptionist",
            "customer service", "support", "entry", "junior",
            "coordinator"
        ]

        if any(k in text for k in executive_keywords):
            return "executive"

        if any(k in text for k in modern_keywords):
            return "modern"

        if any(k in text for k in classic_keywords):
            return "classic"

        return "modern"

    # --------------------------------------------------
    # TEMPLATE-AWARE PROMPTS (CV)
    # --------------------------------------------------
    def _build_cv_prompt(self, cv_text, template):
        if template == "modern":
            style = """
Write a modern ATS-optimised CV.
- concise bullet points
- keyword rich
- no long paragraphs
- focus on skills + achievements
"""
        elif template == "executive":
            style = """
Write a senior executive CV.
- formal tone
- leadership emphasis
- strategic achievements
- impactful language
"""
        else:
            style = """
Write a traditional CV.
- detailed descriptions
- structured paragraphs
- balanced tone
"""

        return f"""
{style}

Improve and rewrite this CV:

{cv_text}
"""

    # --------------------------------------------------
    # TEMPLATE-AWARE PROMPTS (COVER LETTER)
    # --------------------------------------------------
    def _build_cover_letter_prompt(self, cv_text, job_description, template):
        if template == "modern":
            style = "Keep it concise, direct, and ATS-friendly."
        elif template == "executive":
            style = "Use a formal, leadership-focused tone."
        else:
            style = "Use a professional but traditional tone."

        return f"""
Write a cover letter based on this CV and job description.

Style rules:
{style}

CV:
{cv_text}

Job Description:
{job_description}
"""
