"""Modern CV export with flowing text and evidence-led section ordering."""

import re
from xml.sax.saxutils import escape

from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

from .cv_layout import modern_sections
from .pdf_helpers import linked_paragraph_text

BULLET = re.compile(r"^(?:[\u2022\u25cf\u25aa*\-]|\d+[.)])\s+(.+)")


def render_modern_pdf(cv, watermark=False):
    """Render all CV content without fixed-width truncation or sidebar overflow."""
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{cv.full_name}_Modern_CV.pdf"'
    name = (cv.full_name or "No Name").removesuffix(" - Tailored CV")
    document = SimpleDocTemplate(
        response, pagesize=A4, leftMargin=45, rightMargin=45,
        topMargin=42, bottomMargin=42, title=f"{name} - CV", author=name,
    )
    body = ParagraphStyle(
        "ModernBody", fontName="Helvetica", fontSize=9, leading=12,
        textColor=colors.HexColor("#111827"), spaceAfter=4,
        splitLongWords=True,
    )
    heading = ParagraphStyle(
        "ModernHeading", parent=body, fontName="Helvetica-Bold", fontSize=11,
        leading=15, textColor=colors.HexColor("#2563eb"),
        spaceBefore=10, spaceAfter=6, keepWithNext=True,
    )
    name_style = ParagraphStyle(
        "ModernName", parent=body, fontName="Helvetica-Bold", fontSize=24,
        leading=28, textColor=colors.HexColor("#0f2f57"), spaceAfter=6,
    )
    title_style = ParagraphStyle(
        "ModernTitle", parent=body, fontSize=12, leading=16,
        textColor=colors.HexColor("#2563eb"),
    )
    entry_style = ParagraphStyle(
        "ModernEntry", parent=body, fontName="Helvetica-Bold", keepWithNext=True,
    )
    bullet_style = ParagraphStyle(
        "ModernBullet", parent=body, leftIndent=12, bulletIndent=1,
    )
    story = [Paragraph(escape(name), name_style)]
    if cv.job_title:
        story.append(Paragraph(escape(cv.job_title), title_style))
    contact = " | ".join(str(value).strip() for value in (cv.email, cv.phone, cv.address) if value)
    if contact:
        story.append(Paragraph(escape(contact).replace("\n", "<br/>"), body))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#dbeafe"), spaceAfter=6))

    def section(title, content, entries=False):
        if not content or not str(content).strip():
            return
        story.append(Paragraph(escape(title.upper()), heading))
        lines = str(content).splitlines()
        for index, line in enumerate(lines):
            line = line.strip()
            if not line:
                story.append(Spacer(1, 4))
                continue
            match = BULLET.match(line)
            if match:
                story.append(Paragraph(linked_paragraph_text(match.group(1)), bullet_style, bulletText="\u2022"))
            else:
                # Keep role/project metadata with the first responsibility.
                following_bullet = any(BULLET.match(item.strip()) for item in lines[index + 1:index + 4])
                style = entry_style if entries and following_bullet else body
                story.append(Paragraph(linked_paragraph_text(line), style))

    for item in modern_sections(cv):
        section(item["title"], item["content"], entries=item.get("entries", False))
    document.build(story)
    return response
