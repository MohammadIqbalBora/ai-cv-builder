# cv_parser.py reads an uploaded PDF or Word CV, extracts its text,
# and then identifies information such as the name, email, phone number,
# summary, skills, experience and education and puts them into structured fields.

# This module turns uploaded CV text into structured information.

# Regular expressions locate email addresses and phone-like text patterns.
import re

# Path safely extracts a filename extension on any operating system.
from pathlib import Path

# python-docx reads paragraphs from Word documents; pypdf reads PDF pages.
from docx import Document
from docx.table import Table
from pypdf import PdfReader


def extract_text_from_pdf(file_path):
    """Read all text from a PDF file and return it as a single string."""
    text = ""

    # PdfReader parses the document and exposes its pages in order.
    reader = PdfReader(file_path)

    # Some PDF pages contain no extractable text, so skip empty results.
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"

    return text.strip()


def extract_text_from_docx(file_path):
    """Read all text from a DOCX file and return it as one string."""
    # Word documents expose their text as an ordered paragraph collection.
    document = Document(file_path)

    text = []
    for block in document.iter_inner_content():
        if isinstance(block, Table):
            for row in block.rows:
                seen = set()
                for cell in row.cells:
                    if cell._tc not in seen:
                        seen.add(cell._tc)
                        text.extend(p.text for p in cell.paragraphs if p.text)
        elif block.text:
            text.append(block.text)

    return "\n".join(text).strip()


def extract_text_from_cv(file_path):
    """Choose the correct extractor based on the uploaded CV extension."""
    # Normalize case so `.PDF` and `.pdf` use the same branch.
    file_extension = Path(file_path if isinstance(file_path, (str, Path)) else file_path.name).suffix.lower()

    if file_extension == ".pdf":
        return extract_text_from_pdf(file_path)

    if file_extension == ".docx":
        return extract_text_from_docx(file_path)

    # Unsupported file types deliberately return no extracted text.
    return ""


def extract_email(text):
    """Find the first email address in raw CV text."""
    # Return the complete match or an empty string when none exists.
    match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
    return match.group(0) if match else ""


def extract_phone(text):
    """Find the first phone number-like string in raw CV text."""
    # Allow an optional country prefix and spaces between digit groups.
    match = re.search(r"(\+?\d[\d\s]{8,}\d)", text)
    return match.group(0).strip() if match else ""


def extract_name(text):
    """Return the first non-empty line as the candidate name."""
    # Remove whitespace/blank lines before treating line one as the name.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[0] if lines else ""


ADDITIONAL_HEADINGS = {
    "projects", "personal projects", "key projects", "technical projects",
    "professional projects", "interests", "interests and hobbies", "hobbies",
    "professional memberships", "memberships", "languages", "volunteering",
    "volunteer experience", "awards", "publications", "references",
    "selected projects", "academic projects", "portfolio", "achievements",
    "key achievements", "awards and achievements", "honours and awards",
    "honors and awards", "research", "research experience", "presentations",
    "conferences", "professional development", "training", "courses",
    "licenses", "licences", "licenses and certifications", "licences and certifications",
    "professional affiliations", "affiliations", "voluntary work", "community involvement",
    "interests & hobbies", "hobbies and interests", "language skills",
}
STANDARD_HEADINGS = {
    "professional_summary": {"professional profile", "profile", "summary", "professional summary", "personal profile", "career summary", "career objective", "objective"},
    "skills": {"technical skills", "skills", "key skills", "core skills", "core competencies", "skills and expertise"},
    "experience": {"professional experience", "experience", "employment", "work experience", "employment history", "work history", "career history", "relevant experience"},
    "education": {"education", "professional training", "certifications", "qualifications", "education and qualifications", "education & qualifications", "education and certifications", "education & certifications", "academic qualifications", "certificates"},
}
CORE_HEADINGS = set().union(*STANDARD_HEADINGS.values())


def extract_additional_sections(text):
    """Preserve extra sections between standalone CV headings."""
    sections = []
    current = None
    for line in text.splitlines():
        line = line.strip()
        heading = line.rstrip(":").casefold()
        if heading in ADDITIONAL_HEADINGS | CORE_HEADINGS:
            current = None
            if heading in ADDITIONAL_HEADINGS:
                current = {"title": line.rstrip(":"), "content": ""}
                sections.append(current)
        elif current is not None and line:
            current["content"] += ("\n" if current["content"] else "") + line
    return [section for section in sections if section["content"]]


def parse_cv_text(text):
    """Parse raw CV text into a simple structured dictionary."""
    # Delegate each output field to a small extraction helper above.
    result = {
        "full_name": extract_name(text),
        "email": extract_email(text),
        "phone": extract_phone(text),
        "additional_sections": extract_additional_sections(text),
    }
    fields = {heading: field for field, headings in STANDARD_HEADINGS.items() for heading in headings}
    content = {field: [] for field in STANDARD_HEADINGS}
    current = None
    for line in text.splitlines():
        line = line.strip()
        heading = line.rstrip(":").casefold()
        if heading in fields:
            current = fields[heading]
            # Retain labels when several source sections share one stored field.
            if content[current]:
                content[current].extend(["", line.rstrip(":")])
        elif heading in ADDITIONAL_HEADINGS:
            current = None
        elif current and line:
            content[current].append(line)
    result.update({field: "\n".join(lines) for field, lines in content.items()})
    return result
