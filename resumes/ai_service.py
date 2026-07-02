from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def improve_cv(cv_text, job_description):
    prompt = f"""
You are a professional CV writer.

Rewrite and improve this CV to match the job description.

CV:
{cv_text}

Job Description:
{job_description}

Return:
- Improved CV
- Better formatting
- ATS-friendly wording
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful CV writing assistant."},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content

def generate_cover_letter(cv_text, job_description):
    from openai import OpenAI
    from django.conf import settings

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    prompt = f"""
You are a professional cover letter writer.

Write a strong cover letter based on:

CV:
{cv_text}

Job Description:
{job_description}

Make it professional, concise, and tailored.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content
