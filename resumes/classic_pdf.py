"""Compact, single-column Classic CV matching the document preview."""

import re
from xml.sax.saxutils import escape

from django.http import HttpResponse
from .pdf_helpers import linked_paragraph_text
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

NAVY = "#193b56"


def render_classic_pdf(cv, watermark=False):
    """Render a compact A4 CV with projects on the opening page."""
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="{cv.full_name}_Classic_CV.pdf"'
    )
    document = SimpleDocTemplate(
        response, pagesize=A4, rightMargin=52, leftMargin=52,
        topMargin=48, bottomMargin=48,
        title=f"{cv.full_name} - CV", author=cv.full_name or "",
    )
    body = ParagraphStyle(
        "ClassicBody", fontName="Helvetica", fontSize=8.2, leading=12,
        textColor=colors.HexColor("#161616"), spaceAfter=1,
    )
    heading = ParagraphStyle(
        "ClassicHeading", parent=body, fontName="Helvetica-Bold",
        textColor=colors.HexColor(NAVY), spaceBefore=9, spaceAfter=4,
        keepWithNext=True,
    )
    name = ParagraphStyle(
        "ClassicName", parent=body, fontName="Helvetica-Bold",
        fontSize=17, leading=21, textColor=colors.HexColor(NAVY),
        spaceAfter=4,
    )
    bullet = ParagraphStyle(
        "ClassicBullet", parent=body, leftIndent=13, firstLineIndent=0,
        bulletIndent=5, spaceAfter=0,
    )
    story = [Paragraph(escape((cv.full_name or "No Name").replace(" - Tailored CV", "")), name)]
    story.append(HRFlowable(
        width="100%", thickness=0.6, color=colors.HexColor("#3979d6"),
        spaceAfter=4,
    ))
    contact = " | ".join(str(item).strip() for item in [cv.address, cv.phone, cv.email] if item)
    if contact:
        story.append(Paragraph(escape(contact).replace("\n", " "), body))

    def section(title, content, entries=False):
        if not content or not str(content).strip():
            return
        story.append(Paragraph(escape(title), heading))
        lines = str(content).splitlines()
        for index, line in enumerate(lines):
            line = line.strip()
            if not line:
                story.append(Spacer(1, 5))
                continue
            match = re.match(r"^(?:[\u2022\u25cf\u25aa*\-]|\d+[.)])\s+(.+)", line)
            if match:
                story.append(Paragraph(linked_paragraph_text(match.group(1)), bullet, bulletText="\u2022"))
            else:
                text = linked_paragraph_text(line)
                # A role/project line immediately preceding bullets is an entry heading.
                if entries and index + 1 < len(lines) and re.match(
                    r"\s*(?:[\u2022\u25cf\u25aa*\-]|\d+[.)])\s+", lines[index + 1]
                ):
                    text = f"<b>{text}</b>"
                story.append(Paragraph(text, body))

    section("Professional Profile", cv.professional_summary)
    section("Technical Skills", cv.skills)
    projects = []
    remaining = []
    for extra in cv.additional_sections or []:
        if extra["title"].strip().casefold() in {"projects", "personal projects", "selected projects"}:
            projects.append(extra)
        else:
            remaining.append(extra)
    for extra in projects:
        section(extra["title"], extra["content"], entries=True)
    if projects and cv.experience and any(str(extra["content"]).strip() for extra in projects):
        story.append(PageBreak())
    section("Professional Experience", cv.experience, entries=True)
    section("Education and Certifications", cv.education)
    for extra in remaining:
        section(extra["title"], extra["content"], entries=True)
    document.build(story)
    return response
