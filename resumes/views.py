from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from reportlab.pdfgen import canvas

from .models import CV
from .forms import CVForm


# -------------------------
# HOME PAGE
# -------------------------
@login_required
def home(request):
    return render(request, "home.html")


# -------------------------
# DASHBOARD
# -------------------------
@login_required
def dashboard(request):
    cvs = CV.objects.filter(user=request.user)
    return render(request, "dashboard.html", {"cvs": cvs})


# -------------------------
# CREATE CV
# -------------------------
@login_required
def create_cv(request):
    if request.method == "POST":
        form = CVForm(request.POST, request.FILES)
        if form.is_valid():
            cv = form.save(commit=False)
            cv.user = request.user
            cv.save()
            return redirect("dashboard")
    else:
        form = CVForm()

    return render(request, "create_cv.html", {"form": form})


# -------------------------
# PDF EXPORT CV
# -------------------------
@login_required
def download_cv_pdf(request, id):
    cv = CV.objects.get(id=id, user=request.user)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{cv.full_name}_CV.pdf"'

    p = canvas.Canvas(response)

    # Header
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 800, cv.full_name)

    # Contact
    p.setFont("Helvetica", 12)
    p.drawString(100, 770, f"Email: {cv.email}")
    p.drawString(100, 755, f"Phone: {cv.phone}")

    # Summary
    p.setFont("Helvetica-Bold", 12)
    p.drawString(100, 720, "Summary:")
    p.setFont("Helvetica", 11)
    p.drawString(120, 705, cv.summary[:300])

    # Skills
    p.setFont("Helvetica-Bold", 12)
    p.drawString(100, 670, "Skills:")
    p.setFont("Helvetica", 11)
    p.drawString(120, 655, cv.skills[:300])

    p.showPage()
    p.save()

    return response
