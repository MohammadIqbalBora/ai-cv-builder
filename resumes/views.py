import logging
from io import BytesIO

import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from .ai_service import AIService
from .cv_parser import extract_text_from_cv, parse_cv_text
from .forms import CVForm
from .models import CV, Subscription
from .pdf_templates import (
    render_classic_pdf,
    render_executive_pdf,
    render_modern_pdf,
)

logger = logging.getLogger(__name__)


def home(request):
    """Render the public homepage."""
    return render(request, "home.html")


@login_required
def dashboard(request):
    """Render the user's dashboard with their CV list and subscription status."""
    cvs = CV.objects.filter(user=request.user).order_by("-created_at")

    selected_cv = None
    selected_cv_id = request.GET.get("cv")

    if selected_cv_id:
        selected_cv = cvs.filter(id=selected_cv_id).first()

    if not selected_cv and cvs.exists():
        selected_cv = cvs.first()

    subscription = Subscription.objects.filter(user=request.user).first()

    is_premium = False
    plan_name = "Free"

    if subscription and subscription.is_active:
        is_premium = True
        plan_name = subscription.plan_name

    total_cvs = cvs.count()

    return render(
        request,
        "dashboard.html",
        {
            "cvs": cvs,
            "selected_cv": selected_cv,
            "total_cvs": total_cvs,
            "ai_improvements_used": total_cvs,
            "cover_letters_generated": total_cvs,
            "is_premium": is_premium,
            "plan_name": plan_name,
        },
    )


def import_data_into_cv(cv, parsed_data):
    """Copy parsed CV values into the CV model and save it."""
    cv.full_name = parsed_data.get("full_name") or cv.full_name
    cv.job_title = parsed_data.get("job_title") or cv.job_title
    cv.email = parsed_data.get("email") or cv.email
    cv.phone = parsed_data.get("phone") or cv.phone
    cv.address = parsed_data.get("address") or cv.address

    cv.professional_summary = (
        parsed_data.get("professional_summary") or cv.professional_summary
    )

    cv.skills = parsed_data.get("skills") or cv.skills
    cv.experience = parsed_data.get("experience") or cv.experience
    cv.education = parsed_data.get("education") or cv.education

    cv.save()


def parse_cv_with_ai_or_fallback(extracted_text):
    """Attempt AI parsing first, then fall back to a basic parser on error."""
    try:
        ai = AIService()
        return ai.parse_uploaded_cv(extracted_text)
    except Exception as e:
        print("AI import failed, using basic parser:", e)
        return parse_cv_text(extracted_text)


@login_required
def create_cv(request):
    """Create a new CV record or import an uploaded CV file via AI parsing."""
    if request.method == "POST":
        action = request.POST.get("action")

        # Import CV using AI - do NOT validate empty form fields first
        if action == "import":
            uploaded_file = request.FILES.get("uploaded_file")

            if not uploaded_file:
                form = CVForm(request.POST, request.FILES)
                form.add_error("uploaded_file", "Please choose a CV file to import.")
                return render(request, "create_cv.html", {"form": form})

            cv = CV.objects.create(
                user=request.user,
                full_name="",
                uploaded_file=uploaded_file,
                template=request.POST.get("template", "modern"),
            )

            extracted_text = extract_text_from_cv(cv.uploaded_file.path)
            parsed_data = parse_cv_with_ai_or_fallback(extracted_text)

            import_data_into_cv(cv, parsed_data)

            return redirect("edit_cv", id=cv.id)

        # Normal save CV
        form = CVForm(request.POST, request.FILES)

        if form.is_valid():
            cv = form.save(commit=False)
            cv.user = request.user
            cv.save()
            return redirect("dashboard")

    else:
        form = CVForm()

    return render(request, "create_cv.html", {"form": form})


@login_required
def edit_cv(request, id):
    """Edit an existing CV and show which fields are still missing."""
    cv = get_object_or_404(CV, id=id, user=request.user)

    missing_fields = []

    if not cv.email:
        missing_fields.append("Email")
    if not cv.phone:
        missing_fields.append("Phone")
    if not cv.address:
        missing_fields.append("Address")
    if not cv.job_title:
        missing_fields.append("Job Title")
    if not cv.professional_summary:
        missing_fields.append("Professional Summary")
    if not cv.skills:
        missing_fields.append("Skills")
    if not cv.experience:
        missing_fields.append("Experience")
    if not cv.education:
        missing_fields.append("Education")

    if request.method == "POST":
        form = CVForm(request.POST, request.FILES, instance=cv)

        if form.is_valid():
            form.save()
            return redirect("dashboard")

    else:
        form = CVForm(instance=cv)

    return render(
        request,
        "create_cv.html",
        {
            "form": form,
            "cv": cv,
            "missing_fields": missing_fields,
        },
    )


@login_required
def delete_cv(request, id):
    cv = get_object_or_404(CV, id=id, user=request.user)

    if request.method == "POST":
        cv.delete()
        return redirect("dashboard")

    return render(request, "delete_cv.html", {"cv": cv})


def user_has_active_subscription(user):
    """Return True when the user has an active premium subscription."""
    return Subscription.objects.filter(user=user, is_active=True).exists()


@login_required
def improve_cv_ai(request, id):
    """Improve a CV using AI and show the rewritten result."""
    if not user_has_active_subscription(request.user):
        return redirect("subscribe")

    cv = get_object_or_404(CV, id=id, user=request.user)

    ai = AIService()

    cv_text = f"""
Name: {cv.full_name}
Job Title: {cv.job_title}
Summary: {cv.professional_summary}
Skills: {cv.skills}
Experience: {cv.experience}
Education: {cv.education}
"""

    improved_cv = ai.improve_cv(cv_text)

    return render(request, "improve_cv.html", {"cv": cv, "improved_cv": improved_cv})


@login_required
def create_cover_letter(request, id):
    """Generate or display a cover letter for a CV based on the last job description."""
    if not user_has_active_subscription(request.user):
        return redirect("subscribe")

    cv = get_object_or_404(CV, id=id, user=request.user)

    cover_letter = None
    job_description = request.session.get("last_job_description", "")

    if request.method == "POST":
        if not job_description:
            return redirect("job_match", id=cv.id)

        ai = AIService()

        cv_text = f"""
Name: {cv.full_name}
Job Title: {cv.job_title}
Summary: {cv.professional_summary}
Skills: {cv.skills}
Experience: {cv.experience}
"""

        cover_letter = ai.generate_cover_letter(cv_text, job_description)
        request.session["last_cover_letter"] = cover_letter
        request.session["last_cover_letter_cv_id"] = cv.id

    return render(
        request,
        "cover_letter.html",
        {
            "cv": cv,
            "cover_letter": cover_letter,
            "job_description": job_description,
        },
    )


@login_required
def download_cv_pdf(request, id):
    """Return the selected CV as a downloadable PDF based on the chosen template."""
    if not user_has_active_subscription(request.user):
        return redirect("subscribe")

    cv = get_object_or_404(CV, id=id, user=request.user)

    template = request.GET.get("template", cv.template)

    if template == "modern":
        return render_modern_pdf(cv)

    if template == "classic":
        return render_classic_pdf(cv)

    if template == "executive":
        return render_executive_pdf(cv)

    return render_modern_pdf(cv)


@login_required
def download_cover_letter_pdf(request, id):
    """Render the latest generated cover letter as a downloadable PDF."""
    if not user_has_active_subscription(request.user):
        return redirect("subscribe")

    cv = get_object_or_404(CV, id=id, user=request.user)

    cover_letter = request.session.get("last_cover_letter")

    if not cover_letter:
        return redirect("create_cover_letter", id=cv.id)

    buffer = BytesIO()

    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Cover Letter", styles["Title"]))
    story.append(Spacer(1, 20))

    for line in cover_letter.split("\n"):
        if line.strip():
            story.append(Paragraph(line.strip(), styles["Normal"]))
            story.append(Spacer(1, 8))

    doc.build(story)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="cover_letter.pdf"'

    return response


@login_required
def cv_preview(request, id):
    cv = get_object_or_404(CV, id=id, user=request.user)
    return render(request, "cv_preview.html", {"cv": cv})


@login_required
def pricing(request):
    subscription = Subscription.objects.filter(user=request.user).first()

    is_premium = False

    if subscription and subscription.is_active:
        is_premium = True

    return render(request, "pricing.html", {"is_premium": is_premium})


@login_required
def create_checkout_session(request):
    stripe.api_key = settings.STRIPE_SECRET_KEY

    checkout_session = stripe.checkout.Session.create(
        customer_email=request.user.email,
        payment_method_types=["card"],
        line_items=[
            {
                "price": settings.STRIPE_PRICE_ID,
                "quantity": 1,
            }
        ],
        mode="subscription",
        success_url=request.build_absolute_uri("/stripe/success/"),
        cancel_url=request.build_absolute_uri("/stripe/cancel/"),
        metadata={
            "user_id": request.user.id,
        },
    )

    return redirect(checkout_session.url)


@login_required
def stripe_success(request):
    return render(request, "stripe_success.html")


@login_required
def stripe_cancel(request):
    return render(request, "stripe_cancel.html")


@csrf_exempt
def stripe_webhook(request):
    stripe.api_key = settings.STRIPE_SECRET_KEY

    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            endpoint_secret,
        )

    except Exception as e:
        print("Webhook verification error:", e)
        return HttpResponse(status=400)

    try:
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]

            metadata = getattr(session, "metadata", None)
            user_id = getattr(metadata, "user_id", None) if metadata else None

            logger.info("Stripe webhook user_id: %s", user_id)

            if user_id:
                User = get_user_model()
                user = User.objects.filter(id=user_id).first()

                logger.info("Matching Django user found: %s", bool(user))

                if user:
                    subscription, _created = Subscription.objects.get_or_create(
                        user=user
                    )

                    subscription.stripe_customer_id = getattr(
                        session,
                        "customer",
                        None,
                    )
                    subscription.stripe_subscription_id = getattr(
                        session,
                        "subscription",
                        None,
                    )

                    subscription.is_active = True
                    subscription.plan_name = "Premium"
                    subscription.save()

                    logger.info(
                        "Subscription activated for user ID %s",
                        user_id,
                    )

    except Exception:
        logger.exception("Stripe webhook processing failed")
        return HttpResponse(status=500)

    return HttpResponse(status=200)

    return HttpResponse(status=200)


@login_required
def import_uploaded_cv(request, id):
    cv = get_object_or_404(CV, id=id, user=request.user)

    extracted_text = ""

    if cv.uploaded_file:
        extracted_text = extract_text_from_cv(cv.uploaded_file.path)

        if request.method == "POST":
            parsed_data = parse_cv_with_ai_or_fallback(extracted_text)

            import_data_into_cv(cv, parsed_data)

            return redirect("edit_cv", id=cv.id)

    return render(
        request,
        "import_cv.html",
        {
            "cv": cv,
            "extracted_text": extracted_text,
        },
    )


@login_required
def cv_detail(request, id):
    cv = get_object_or_404(CV, id=id, user=request.user)
    return render(request, "cv_detail.html", {"cv": cv})


@login_required
def select_pdf_template(request, id):
    if not user_has_active_subscription(request.user):
        return redirect("subscribe")

    cv = get_object_or_404(CV, id=id, user=request.user)

    return render(request, "pdf_templates.html", {"cv": cv})


@login_required
def job_match(request, id):
    cv = get_object_or_404(CV, id=id, user=request.user)

    analysis = None
    job_description = ""

    if request.method == "POST":
        job_description = request.POST.get("job_description", "").strip()
        job_file = request.FILES.get("job_file")

        if job_file:
            temp_cv = CV.objects.create(
                user=request.user,
                full_name="Temporary Job Description File",
                uploaded_file=job_file,
            )

            job_description = extract_text_from_cv(temp_cv.uploaded_file.path)
            temp_cv.delete()

        if job_description:
            request.session["last_job_description"] = job_description
            request.session["last_job_cv_id"] = cv.id

            ai = AIService()

            cv_text = f"""
Name: {cv.full_name}
Job Title: {cv.job_title}
Email: {cv.email}
Phone: {cv.phone}
Address: {cv.address}
Professional Summary: {cv.professional_summary}
Skills: {cv.skills}
Experience: {cv.experience}
Education: {cv.education}
"""

            analysis = ai.analyse_job_description(cv_text, job_description)

            request.session["last_job_analysis"] = analysis

            return render(
                request,
                "job_match.html",
                {
                    "cv": cv,
                    "analysis": analysis,
                    "job_description": job_description,
                    "message": "Job description analysed successfully.",
                },
            )

        return render(
            request,
            "job_match.html",
            {
                "cv": cv,
                "message": "Please paste or upload a job description first.",
            },
        )

    return render(
        request,
        "job_match.html",
        {
            "cv": cv,
            "analysis": analysis,
            "job_description": job_description,
        },
    )


@login_required
def tailor_cv_to_job(request, id):
    cv = get_object_or_404(CV, id=id, user=request.user)

    if request.method == "POST":
        job_description = request.POST.get("job_description", "").strip()

        if not job_description:
            return redirect("job_match", id=cv.id)

        cv_text = f"""
Name: {cv.full_name}
Job Title: {cv.job_title}
Email: {cv.email}
Phone: {cv.phone}
Summary: {cv.professional_summary}
Skills: {cv.skills}
Experience: {cv.experience}
Education: {cv.education}
"""

        ai = AIService()
        tailored_data = ai.tailor_cv_to_job(cv_text, job_description)

        base_name = cv.full_name.split(" - Tailored CV")[0]

        CV.objects.create(
            user=request.user,
            full_name=f"{base_name} - Tailored CV",
            email=cv.email,
            phone=cv.phone,
            address=cv.address,
            job_title=tailored_data.get("job_title") or cv.job_title,
            professional_summary=tailored_data.get("professional_summary")
            or cv.professional_summary,
            skills=tailored_data.get("skills") or cv.skills,
            experience=tailored_data.get("experience") or cv.experience,
            education=tailored_data.get("education") or cv.education,
            template=cv.template,
        )

        return redirect("dashboard")

    return redirect("job_match", id=cv.id)
