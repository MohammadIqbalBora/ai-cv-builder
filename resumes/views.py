from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

from .models import CV, CoverLetter
from .forms import CVForm

from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from reportlab.lib.styles import getSampleStyleSheet

from .ai_service import improve_cv, generate_cover_letter


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
# EDIT CV
# -------------------------
@login_required
def edit_cv(request, id):
    cv = get_object_or_404(CV, id=id, user=request.user)

    if request.method == "POST":
        form = CVForm(request.POST, request.FILES, instance=cv)
        if form.is_valid():
            form.save()
            return redirect("dashboard")
    else:
        form = CVForm(instance=cv)

    return render(request, "create_cv.html", {"form": form})


# -------------------------
# DOWNLOAD CV PDF
# -------------------------
@login_required
def download_cv_pdf(request, id):
    cv = get_object_or_404(CV, id=id, user=request.user)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{cv.full_name}_CV.pdf"'

    doc = SimpleDocTemplate(response)

    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    title = styles["Title"]

    content = []

    # Name
    content.append(Paragraph(cv.full_name, title))
    content.append(Spacer(1, 12))

    # Contact
    content.append(Paragraph(f"Email: {cv.email}", normal))
    content.append(Paragraph(f"Phone: {cv.phone}", normal))
    content.append(Spacer(1, 12))

    # Summary
    content.append(Paragraph("<b>Summary</b>", normal))
    content.append(Paragraph(cv.summary.replace("\n", "<br/>"), normal))
    content.append(Spacer(1, 12))

    # Skills
    content.append(Paragraph("<b>Skills</b>", normal))

    skills = cv.skills.split("\n")
    for skill in skills:
        if skill.strip():
            content.append(Paragraph(f"• {skill}", normal))

    doc.build(content)

    return response


# -------------------------
# DELETE CV
# -------------------------
@login_required
def delete_cv(request, id):
    cv = get_object_or_404(CV, id=id, user=request.user)

    if request.method == "POST":
        cv.delete()
        return redirect("dashboard")

    return render(request, "delete_cv.html", {"cv": cv})


# -------------------------
# AI CV IMPROVEMENT
# -------------------------
@login_required
def improve_cv_ai(request, id):
    cv = get_object_or_404(CV, id=id, user=request.user)
    result = None

    if request.method == "POST":
        job_description = request.POST.get("job_description")

        cv_text = f"""
Name: {cv.full_name}
Email: {cv.email}
Phone: {cv.phone}
Summary: {cv.summary}
Skills: {cv.skills}
"""

        result = improve_cv(cv_text, job_description)

    return render(request, "improve_cv.html", {"cv": cv, "result": result})


# -------------------------
# COVER LETTER GENERATION
# -------------------------
@login_required
def create_cover_letter(request, id):
    cv = get_object_or_404(CV, id=id, user=request.user)
    result = None

    if request.method == "POST":
        job_description = request.POST.get("job_description")

        cv_text = f"""
Name: {cv.full_name}
Email: {cv.email}
Phone: {cv.phone}
Summary: {cv.summary}
Skills: {cv.skills}
"""

        result = generate_cover_letter(cv_text, job_description)

        CoverLetter.objects.create(
            user=request.user, cv=cv, job_description=job_description, content=result
        )

    return render(request, "cover_letter.html", {"cv": cv, "result": result})

