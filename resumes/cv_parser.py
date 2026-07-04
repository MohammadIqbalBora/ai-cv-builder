import re
from pathlib import Path

from docx import Document
from pypdf import PdfReader


def extract_text_from_pdf(file_path):
    text = ""

    reader = PdfReader(file_path)

    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"

    return text.strip()


def extract_text_from_docx(file_path):
    document = Document(file_path)

    text = []
    for paragraph in document.paragraphs:
        if paragraph.text:
            text.append(paragraph.text)

    return "\n".join(text).strip()


def extract_text_from_cv(file_path):
    file_extension = Path(file_path).suffix.lower()

    if file_extension == ".pdf":
        return extract_text_from_pdf(file_path)

    if file_extension == ".docx":
        return extract_text_from_docx(file_path)

    return ""


def extract_email(text):
    match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
    return match.group(0) if match else ""


def extract_phone(text):
    match = re.search(r"(\+?\d[\d\s]{8,}\d)", text)
    return match.group(0).strip() if match else ""


def extract_name(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[0] if lines else ""


def extract_section(text, start_keywords, end_keywords):
    lines = text.splitlines()
    capture = False
    section_lines = []

    for line in lines:
        clean_line = line.strip()
        lower_line = clean_line.lower()

        if any(keyword.lower() in lower_line for keyword in start_keywords):
            capture = True
            continue

        if capture and any(keyword.lower() in lower_line for keyword in end_keywords):
            break

        if capture and clean_line:
            section_lines.append(clean_line)

    return "\n".join(section_lines).strip()


def parse_cv_text(text):
    return {
        "full_name": extract_name(text),
        "email": extract_email(text),
        "phone": extract_phone(text),
        "professional_summary": extract_section(
            text,
            ["Professional Profile", "Profile", "Summary"],
            ["Technical Skills", "Skills", "Experience", "Employment"],
        ),
        "skills": extract_section(
            text,
            ["Technical Skills", "Skills"],
            ["Professional Experience", "Experience", "Employment", "Education"],
        ),
        "experience": extract_section(
            text,
            ["Professional Experience", "Experience", "Employment"],
            ["Professional Training", "Education", "Certifications", "Languages"],
        ),
        "education": extract_section(
            text,
            ["Education", "Professional Training", "Certifications"],
            ["Languages", "Interests"],
        ),
    }
