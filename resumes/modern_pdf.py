# This file helps build or display printable PDF versions of a CV.

"""Modern CV PDF rendering utilities."""

from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .pdf_helpers import draw_footer, draw_section, draw_wrapped_text


def draw_sidebar(pdf, cv, width, height, sidebar_width):
    """Render the left sidebar of the modern CV template."""
    pdf.setFillColor(colors.HexColor("#0f2f57"))
    pdf.rect(0, 0, sidebar_width, height, fill=True, stroke=False)

    x = 20
    y = height - 55

    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(x, y, "CONTACT")

    y -= 26
    pdf.setFont("Helvetica", 8.5)

    overflow = []

    def sidebar_text(text, font="Helvetica", size=8.2):
        nonlocal y
        pdf.setFont(font, size)
        # Measure characters as well as words so long emails/URLs cannot overflow.
        line = ""
        for char in str(text):
            if pdf.stringWidth(line + char, font, size) > sidebar_width - 40:
                if y >= 45:
                    pdf.drawString(x, y, line)
                    y -= 12
                else:
                    overflow.append(line)
                line = ""
            line += char
        if line:
            if y >= 45:
                pdf.drawString(x, y, line)
                y -= 12
            else:
                overflow.append(line)

    for item in [cv.email, cv.phone, cv.address]:
        if item:
            for line in str(item).splitlines():
                sidebar_text(line, size=8.5)
            y -= 4
    y -= 18
    if y >= 65:
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(x, y, "SKILLS")
        y -= 24
    if not cv.skills:
        sidebar_text("N/A")
    else:
        for line in str(cv.skills).splitlines():
            clean = line.strip().lstrip("\u2022- ")
            if not clean:
                y -= 6
                continue
            if clean.endswith(":"):
                sidebar_text(clean, "Helvetica-Bold", 8.7)
            else:
                # Comma-separated AI lists become readable individual skill entries.
                for skill in clean.split(","):
                    if skill.strip():
                        sidebar_text("- " + skill.strip())
    return "\n".join(overflow)


def draw_modern_experience(pdf, text, x, y, max_width, width, height):
    """Render the experience section for the modern layout."""
    if not text:
        return y

    pdf.setFillColor(colors.HexColor("#2563eb"))
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(x, y, "EXPERIENCE")

    y -= 8
    pdf.setStrokeColor(colors.HexColor("#d1d5db"))
    pdf.line(x, y, x + max_width, y)

    y -= 22

    lines = [line.strip() for line in str(text).split("\n") if line.strip()]
    role_line_position = 0

    for line in lines:
        if y < 80:
            pdf.showPage()
            y = height - 55
            pdf.setFont("Helvetica", 9)

        is_bullet = line.startswith("•") or line.startswith("-")

        if is_bullet:
            clean_line = line.replace("•", "", 1).replace("-", "", 1).strip()

            pdf.setFillColor(colors.HexColor("#111827"))
            pdf.setFont("Helvetica", 9)
            pdf.drawString(x, y, "•")

            y = draw_wrapped_text(
                pdf,
                clean_line,
                x + 13,
                y,
                max_width - 13,
                font_name="Helvetica",
                font_size=9,
                line_height=12,
                height=height,
            )

            y -= 5
            continue

        if role_line_position == 0:
            y -= 8
            pdf.setFillColor(colors.HexColor("#0f172a"))
            y = draw_wrapped_text(
                pdf,
                line,
                x,
                y,
                max_width,
                font_name="Helvetica-Bold",
                font_size=10,
                line_height=13,
                height=height,
            )
            y -= 6
            role_line_position = 1

        elif role_line_position == 1:
            pdf.setFillColor(colors.HexColor("#111827"))
            y = draw_wrapped_text(
                pdf,
                line,
                x,
                y,
                max_width,
                font_name="Helvetica-Bold",
                font_size=9,
                line_height=12,
                height=height,
            )
            y -= 6
            role_line_position = 2

        elif role_line_position == 2:
            pdf.setFillColor(colors.HexColor("#475569"))
            y = draw_wrapped_text(
                pdf,
                line,
                x,
                y,
                max_width,
                font_name="Helvetica",
                font_size=9,
                line_height=12,
                height=height,
            )
            y -= 8
            role_line_position = 3

        else:
            y -= 10
            pdf.setFillColor(colors.HexColor("#0f172a"))
            y = draw_wrapped_text(
                pdf,
                line,
                x,
                y,
                max_width,
                font_name="Helvetica-Bold",
                font_size=10,
                line_height=13,
                height=height,
            )
            y -= 6
            role_line_position = 1

    return y - 14


def render_modern_pdf(cv, watermark=False):
    """Render the modern CV design into a PDF response."""
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="{cv.full_name}_Modern_CV.pdf"'
    )

    pdf = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    sidebar_width = 175
    margin = 34

    sidebar_overflow = draw_sidebar(pdf, cv, width, height, sidebar_width)

    main_x = sidebar_width + margin
    main_width = width - main_x - margin
    y = height - 55

    pdf.setFillColor(colors.HexColor("#0f172a"))
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawString(
        main_x,
        y,
        (cv.full_name or "No Name").replace(" - Tailored CV", ""),
    )

    if cv.job_title:
        y -= 24
        pdf.setFont("Helvetica", 12)
        pdf.setFillColor(colors.HexColor("#2563eb"))
        pdf.drawString(main_x, y, cv.job_title)

    y -= 24
    pdf.setStrokeColor(colors.HexColor("#dbeafe"))
    pdf.setLineWidth(2)
    pdf.line(main_x, y, width - margin, y)

    y -= 24

    y = draw_section(
        pdf,
        "Professional Profile",
        cv.professional_summary,
        main_x,
        y,
        main_width,
        title_color="#2563eb",
    )

    if sidebar_overflow:
        y = draw_section(pdf, "Contact / Skills (continued)", sidebar_overflow,
                         main_x, y, main_width, title_color="#2563eb")

    for item in cv.leading_projects:
        y = draw_section(pdf, item["title"], item["content"], main_x, y, main_width, title_color="#2563eb")

    y = draw_modern_experience(
        pdf,
        cv.experience,
        main_x,
        y,
        main_width,
        width,
        height,
    )

    y = draw_section(
        pdf,
        "Education",
        cv.education,
        main_x,
        y,
        main_width,
        title_color="#2563eb",
    )

    for item in cv.trailing_sections:
        y = draw_section(pdf, item["title"], item["content"], main_x, y, main_width, title_color="#2563eb")
    draw_footer(pdf, width, "Generated by AI CV Builder - Modern Template")
    pdf.save()

    return response
