import json
import os

from openai import OpenAI


class AIService:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def improve_cv(self, cv_text, template="modern"):
        prompt = self._build_cv_prompt(cv_text, template)

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional CV writing assistant.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )

        return response.choices[0].message.content

    def generate_cover_letter(self, cv_text, job_description, template="modern"):
        prompt = self._build_cover_letter_prompt(
            cv_text,
            job_description,
            template,
        )

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional cover letter writer.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )

        return response.choices[0].message.content

    def parse_uploaded_cv(self, extracted_text):
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional CV writer and recruiter. "
                        "Return valid JSON only. Every value must be plain text."
                    ),
                },
                {
                    "role": "user",
                    "content": f"""
Act as a professional CV writer and editor.

I will provide raw text extracted from an uploaded CV.

Your task is to:
1. Restructure the CV into clean professional sections.
2. Create a strong professional summary if the original is missing or weak.
3. Remove duplicate repeated job descriptions.
4. Group skills logically.
5. Rewrite experience bullet points using strong action verbs.
6. Keep facts accurate. Do not invent jobs, companies, dates or qualifications.
7. Use clear UK CV formatting.

Return JSON only with these exact keys:

full_name
job_title
email
phone
address
professional_summary
skills
experience
education

Rules:
- Every value must be a plain text string.
- Do not return lists, arrays or dictionaries.
- Do not include markdown.
- If a field is missing, return an empty string.
- Address must be empty if no address is found.

professional_summary:
Write 2-3 strong sentences based on the candidate's background.

skills:
Group skills clearly like this:
Operating Systems:
• Red Hat 7
• Solaris 7-10

Hardware:
• HP Servers
• Dell Hardware

Tools:
• VMware
• ITIL
• CMDB

experience:
Use this format for each role:

Company Name
Job Title
Dates
• Action-focused responsibility or achievement
• Action-focused responsibility or achievement
• Action-focused responsibility or achievement

education:
Include courses, certifications and qualifications only.
One item per line.

CV TEXT:
{extracted_text}
""",
                },
            ],
        )

        return json.loads(response.choices[0].message.content)

    def suggest_template(self, job_title="", summary="", skills=""):
        text = f"{job_title} {summary} {skills}".lower()

        if any(word in text for word in ["manager", "director", "executive", "lead"]):
            return "executive"

        if any(word in text for word in ["developer", "engineer", "software", "it"]):
            return "modern"

        return "classic"

    def _build_cv_prompt(self, cv_text, template):
        return f"""
Improve this CV professionally.
Use clear sections and bullet points.

CV:
{cv_text}
"""

    def _build_cover_letter_prompt(self, cv_text, job_description, template):
        return f"""
Write a professional cover letter.

CV:
{cv_text}

Job Description:
{job_description}
"""
