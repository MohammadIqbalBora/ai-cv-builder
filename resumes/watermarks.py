"""Apply the free-plan watermark to every page of a downloadable PDF."""
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas

WATERMARK_TEXT = "AI CV Builder - Free Version"


def watermark_pdf_response(response):
    reader = PdfReader(BytesIO(response.content))
    writer = PdfWriter()
    for page in reader.pages:
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        overlay = BytesIO()
        canvas = Canvas(overlay, pagesize=(width, height))
        canvas.saveState()
        canvas.setFillColorRGB(0.35, 0.4, 0.5)
        canvas.setFillAlpha(0.22)
        canvas.setFont("Helvetica-Bold", 30)
        canvas.translate(width / 2, height / 2)
        canvas.rotate(40)
        for offset in (-220, 0, 220):
            canvas.drawCentredString(0, offset, WATERMARK_TEXT)
        canvas.restoreState()
        canvas.save()
        overlay.seek(0)
        page.merge_page(PdfReader(overlay).pages[0])
        writer.add_page(page)
    output = BytesIO()
    writer.write(output)
    response.content = output.getvalue()
    return response
