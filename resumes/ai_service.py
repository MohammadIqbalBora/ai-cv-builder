import json
import os

from openai import OpenAI


def make_plain_text(value):
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, list):
        lines = []

        for item in value:
            item_text = make_plain_text(item)

            if item_text:
                lines.append(item_text)

        return "\n".join(lines)

    if isinstance(value, dict):
        lines = []

        company = (
            value.get("Company Name")
            or value.get("company_name")
            or value.get("company")
        )
        job_title = (
            value.get("Job Title") or value.get("job_title") or value.get("title")
        )
        dates = value.get("Dates") or value.get("dates")
        responsibilities = (
            value.get("Responsibilities")
            or value.get("responsibilities")
            or value.get("Responsibility")
        )

        if company:
            lines.append(make_plain_text(company))

        if job_title:
            lines.append(make_plain_text(job_title))

        if dates:
            lines.append(make_plain_text(dates))

        if responsibilities:
            lines.append("")

            if isinstance(responsibilities, list):
                for responsibility in responsibilities:
                    clean_item = (
                        make_plain_text(responsibility).replace("•", "").strip()
                    )
                    if clean_item:
                        lines.append(f"•  {clean_item}")
            else:
                clean_item = make_plain_text(responsibilities).replace("•", "").strip()
                if clean_item:
                    lines.append(f"•  {clean_item}")

        if lines:
            return "\n".join(lines)

        for key, item in value.items():
            lines.append(str(key))
            item_text = make_plain_text(item)
            if item_text:
                lines.append(item_text)

        return "\n".join(lines)

    return str(value).strip()


def clean_ai_cv_data(data):
    return {
        "job_title": make_plain_text(data.get("job_title")),
        "professional_summary": make_plain_text(data.get("professional_summary")),
        "skills": make_plain_text(data.get("skills")),
        "experience": make_plain_text(data.get("experience")),
        "education": make_plain_text(data.get("education")),
    }


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

    def analyse_job_description(self, job_description):
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "You analyse job descriptions and return valid JSON only.",
                },
                {
                    "role": "user",
                    "content": f"""
Analyse this job description.

Return JSON only with these exact keys:

job_title
required_skills
responsibilities
keywords
experience_level
qualifications

Rules:
- Every value must be plain text.
- Do not return lists or dictionaries.
- Put each skill on a new line.
- Put each responsibility on a new line.
- Put each keyword on a new line.
- If something is not found, return an empty string.

Job description:

{job_description}
""",
                },
            ],
        )

        return json.loads(response.choices[0].message.content)

    def tailor_cv_to_job(self, cv_text, job_description):
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional CV writer. " "Return valid JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": f"""
Rewrite this CV so it is tailored to the job description.

Return JSON only with these exact keys:

job_title
professional_summary
skills
experience
education

Important rules:
- Do not invent jobs, companies, dates, qualifications, or experience.
- Keep facts truthful.
- Emphasise relevant existing skills and experience.
- Keep technical keywords from the job description where they honestly match the CV.
- Rewrite bullet points professionally.
- Do not include markdown.
- Every value must be plain text only.
- Skills should be grouped clearly.
- Experience should keep this format:

Company Name
Job Title
Dates
•  Responsibility or achievement
•  Responsibility or achievement
•  Responsibility or achievement

CV:
{cv_text}

Job Description:
{job_description}
""",
                },
            ],
        )

        raw_data = json.loads(response.choices[0].message.content)
        return clean_ai_cv_data(raw_data)

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
