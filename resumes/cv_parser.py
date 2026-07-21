# This module turns uploaded CV text into structured information.

# Regular expressions locate email addresses and phone-like text patterns.
import re
# Path safely extracts a filename extension on any operating system.
from pathlib import Path

# python-docx reads paragraphs from Word documents; pypdf reads PDF pages.
from docx import Document
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
    for paragraph in document.paragraphs:
        if paragraph.text:
            text.append(paragraph.text)

    return "\n".join(text).strip()


def extract_text_from_cv(file_path):
    """Choose the correct extractor based on the uploaded CV extension."""
    # Normalize case so `.PDF` and `.pdf` use the same branch.
    file_extension = Path(file_path).suffix.lower()

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


def extract_section(text, start_keywords, end_keywords):
    """Capture a section of text between known start and end markers."""
    lines = text.splitlines()
    capture = False
    section_lines = []

    for line in lines:
        clean_line = line.strip()
        lower_line = clean_line.lower()

        # A matching heading starts capture but is not included in the result.
        if any(keyword.lower() in lower_line for keyword in start_keywords):
            capture = True
            continue

        # A later known heading ends the current section.
        if capture and any(keyword.lower() in lower_line for keyword in end_keywords):
            break

        # Preserve non-empty content only while inside the requested section.
        if capture and clean_line:
            section_lines.append(clean_line)

    return "\n".join(section_lines).strip()


def parse_cv_text(text):
    """Parse raw CV text into a simple structured dictionary."""
    # Delegate each output field to a small extraction helper above.
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
