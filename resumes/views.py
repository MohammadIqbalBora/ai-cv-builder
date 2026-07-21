# This module handles web requests and prepares responses or pages.
# Record webhook events and failures without printing sensitive details.
import logging

# Hold a generated PDF in memory instead of creating a temporary disk file.
from io import BytesIO

# Stripe's SDK creates checkout sessions and verifies signed webhook events.
import stripe

# Read API keys and price IDs from config/settings.py.
from django.conf import settings

# Resolve the active User model without hard-coding its class.
from django.contrib.auth import get_user_model

# Redirect anonymous visitors to login before protected views run.
from django.contrib.auth.decorators import login_required

# Build raw responses, including PDFs and webhook status codes.
from django.http import HttpResponse

# Load owned objects safely, redirect by route name, and render templates.
from django.shortcuts import get_object_or_404, redirect, render

# Stripe cannot send a browser CSRF token, so its signed endpoint is exempt.
from django.views.decorators.csrf import csrf_exempt
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

# Import local business logic, parsing, forms, database models, and PDF designs.
from .ai_service import AIService
from .cv_parser import extract_text_from_cv, parse_cv_text
from .forms import CVForm
from .models import CV, Subscription
from .pdf_templates import (
    render_classic_pdf,
    render_executive_pdf,
    render_modern_pdf,
)

# Give log entries this module's name so their source is easy to identify.
logger = logging.getLogger(__name__)


def home(request):
    """Render the public homepage."""
    return render(request, "home.html")


@login_required
def dashboard(request):
    """Render the user's dashboard with their CV list and subscription status."""
    # Fetch only this user's CVs, newest first; this also prevents data leakage.
    cvs = CV.objects.filter(user=request.user).order_by("-created_at")

    selected_cv = None
    # A `?cv=ID` query string lets the page request one selected CV.
    selected_cv_id = request.GET.get("cv")

    # `.first()` returns None rather than raising when the ID is not owned/found.
    if selected_cv_id:
        selected_cv = cvs.filter(id=selected_cv_id).first()

    # Default to the newest CV when no valid explicit selection exists.
    if not selected_cv and cvs.exists():
        selected_cv = cvs.first()

    # Subscription is optional, so retrieve the row without requiring one.
    subscription = Subscription.objects.filter(user=request.user).first()

    is_premium = False
    plan_name = "Free"

    # Convert database state into simple values the template can display.
    if subscription and subscription.is_active:
        is_premium = True
        plan_name = subscription.plan_name

    # Evaluate the QuerySet count in the database for the dashboard statistic.
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
    # For every field, prefer a non-empty parsed value and otherwise retain the
    # value already stored on the CV. This prevents blank AI output erasing data.
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

    # Persist all assignments in one database update.
    cv.save()


def parse_cv_with_ai_or_fallback(extracted_text):
    """Attempt AI parsing first, then fall back to a basic parser on error."""
    try:
        # Construct the API wrapper and ask it for structured CV fields.
        ai = AIService()
        return ai.parse_uploaded_cv(extracted_text)
        # Any AI/network/parsing failure still leaves a local regex parser path.
    except Exception as e:
        print("AI import failed, using basic parser:", e)
        return parse_cv_text(extracted_text)


@login_required
def create_cv(request):
    """Create a new CV record or import an uploaded CV file via AI parsing."""
    if request.method == "POST":
        # The submit button identifies whether this is an import or normal save.
        action = request.POST.get("action")

        # Import CV using AI - do NOT validate empty form fields first
        if action == "import":
            # Uploaded binary files live in request.FILES, not request.POST.
            uploaded_file = request.FILES.get("uploaded_file")

            if not uploaded_file:
                # Bind both dictionaries so the page can redisplay its values.
                form = CVForm(request.POST, request.FILES)
                form.add_error("uploaded_file", "Please choose a CV file to import.")
                return render(request, "create_cv.html", {"form": form})

            # Save the file first because the parser needs its real disk path.
            cv = CV.objects.create(
                user=request.user,
                full_name="",
                uploaded_file=uploaded_file,
                template=request.POST.get("template", "modern"),
            )

            # Convert PDF/DOCX content to text, then structure that text.
            extracted_text = extract_text_from_cv(cv.uploaded_file.path)
            parsed_data = parse_cv_with_ai_or_fallback(extracted_text)

            # Copy detected values into the placeholder CV record.
            import_data_into_cv(cv, parsed_data)

            # Let the user review and correct imported fields.
            return redirect("edit_cv", id=cv.id)

        # Normal save CV
        # Bind normal text fields and an optional uploaded file to CVForm.
        form = CVForm(request.POST, request.FILES)

        if form.is_valid():
            # Delay the insert because the form deliberately does not expose
            # the `user` field; ownership must come from the logged-in request.
            cv = form.save(commit=False)
            cv.user = request.user
            cv.save()
            return redirect("dashboard")

    else:
        # GET requests display a blank creation form.
        form = CVForm()

    return render(request, "create_cv.html", {"form": form})


@login_required
def edit_cv(request, id):
    """Edit an existing CV and show which fields are still missing."""
    # Filtering by both ID and user prevents one account editing another's CV.
    cv = get_object_or_404(CV, id=id, user=request.user)

    # Build human-readable reminders for every empty optional section.
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
        # `instance=cv` changes ModelForm.save() from INSERT to UPDATE.
        form = CVForm(request.POST, request.FILES, instance=cv)

        if form.is_valid():
            form.save()
            return redirect("dashboard")

    else:
        # Prepopulate the form fields from the existing database object.
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
    """Confirm and then delete one CV owned by the logged-in user."""
    # Ownership filtering prevents deleting a CV by guessing another ID.
    cv = get_object_or_404(CV, id=id, user=request.user)

    # Only POST performs the destructive action; GET merely shows confirmation.
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
    # Premium-only tools send free users to Stripe subscription checkout.
    if not user_has_active_subscription(request.user):
        return redirect("subscribe")

    cv = get_object_or_404(CV, id=id, user=request.user)

    ai = AIService()

    # Combine model fields into the plain text expected by AIService.
    cv_text = f"""
Name: {cv.full_name}
Job Title: {cv.job_title}
Summary: {cv.professional_summary}
Skills: {cv.skills}
Experience: {cv.experience}
Education: {cv.education}
"""

    # The service returns rewritten content without changing this CV record.
    improved_cv = ai.improve_cv(cv_text)

    return render(request, "improve_cv.html", {"cv": cv, "improved_cv": improved_cv})


@login_required
def create_cover_letter(request, id):
    """Generate or display a cover letter for a CV based on the last job description."""
    if not user_has_active_subscription(request.user):
        return redirect("subscribe")

    cv = get_object_or_404(CV, id=id, user=request.user)

    cover_letter = None
    # Job matching stores the most recent description in this browser session.
    job_description = request.session.get("last_job_description", "")

    if request.method == "POST":
        # A cover letter needs a target job; return to the input page if absent.
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
        # Save generated text in the session so the PDF download view can use it.
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

    # A query-string preview choice overrides the model's saved template.
    template = request.GET.get("template", cv.template)

    # Dispatch to one of the renderer modules imported through pdf_templates.py.
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

    # Reuse text generated by create_cover_letter for this browser session.
    cover_letter = request.session.get("last_cover_letter")

    if not cover_letter:
        return redirect("create_cover_letter", id=cv.id)

    # ReportLab writes the document into this in-memory byte buffer.
    buffer = BytesIO()

    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Cover Letter", styles["Title"]))
    story.append(Spacer(1, 20))

    # Convert each non-empty text line into a styled PDF paragraph.
    for line in cover_letter.split("\n"):
        if line.strip():
            story.append(Paragraph(line.strip(), styles["Normal"]))
            story.append(Spacer(1, 8))

    # Finalize the document and rewind so HttpResponse reads from byte zero.
    doc.build(story)
    buffer.seek(0)

    # Mark the response as a PDF attachment to trigger a browser download.
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="cover_letter.pdf"'

    return response


@login_required
def cv_preview(request, id):
    """Display an owned CV in the browser preview template."""
    cv = get_object_or_404(CV, id=id, user=request.user)
    return render(request, "cv_preview.html", {"cv": cv})


@login_required
def pricing(request):
    """Show plan information and whether the current user is premium."""
    subscription = Subscription.objects.filter(user=request.user).first()

    is_premium = False

    if subscription and subscription.is_active:
        is_premium = True

    return render(request, "pricing.html", {"is_premium": is_premium})


@login_required
def create_checkout_session(request):
    """Create a Stripe subscription checkout and redirect the browser to it."""
    # Configure Stripe's SDK using the secret loaded in config/settings.py.
    stripe.api_key = settings.STRIPE_SECRET_KEY

    # Stripe hosts payment collection; this object describes what it should sell.
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
        # Metadata returns in the webhook so payment maps back to a Django user.
        metadata={
            "user_id": request.user.id,
        },
    )

    return redirect(checkout_session.url)


@login_required
def stripe_success(request):
    """Display the successful-checkout landing page."""
    return render(request, "stripe_success.html")


@login_required
def stripe_cancel(request):
    """Display the cancelled-checkout landing page."""
    return render(request, "stripe_cancel.html")


@csrf_exempt
def stripe_webhook(request):
    """Verify and process server-to-server event notifications from Stripe."""
    stripe.api_key = settings.STRIPE_SECRET_KEY

    # Use the exact raw request bytes and signature for cryptographic checking.
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        # Reject forged or malformed events before trusting their contents.
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            endpoint_secret,
        )

    except Exception as e:
        print("Webhook verification error:", e)
        return HttpResponse(status=400)

    try:
        # This event means Stripe successfully created the checkout session.
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]

            # Recover the Django user ID placed in checkout metadata earlier.
            metadata = getattr(session, "metadata", None)
            user_id = getattr(metadata, "user_id", None) if metadata else None

            logger.info("Stripe webhook user_id: %s", user_id)

            if user_id:
                # Resolve the configured Django account model and matching row.
                User = get_user_model()
                user = User.objects.filter(id=user_id).first()

                logger.info("Matching Django user found: %s", bool(user))

                if user:
                    # Reuse an existing subscription or create its first row.
                    subscription, _created = Subscription.objects.get_or_create(
                        user=user
                    )

                    # Store Stripe identifiers for later billing reconciliation.
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

                    # Grant premium access locally after verified checkout.
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
    """Preview an uploaded file and import its parsed values after confirmation."""
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
    """Display all saved fields for one CV owned by the current user."""
    cv = get_object_or_404(CV, id=id, user=request.user)
    return render(request, "cv_detail.html", {"cv": cv})


@login_required
def select_pdf_template(request, id):
    """Show premium PDF design choices for an owned CV."""
    if not user_has_active_subscription(request.user):
        return redirect("subscribe")

    cv = get_object_or_404(CV, id=id, user=request.user)

    return render(request, "pdf_templates.html", {"cv": cv})


@login_required
def job_match(request, id):
    """Compare an owned CV with pasted or uploaded job-description text."""
    cv = get_object_or_404(CV, id=id, user=request.user)

    analysis = None
    job_description = ""

    if request.method == "POST":
        # Accept either pasted text or an uploaded document.
        job_description = request.POST.get("job_description", "").strip()
        job_file = request.FILES.get("job_file")

        if job_file:
            # Reuse the CV upload/parser pipeline through a short-lived record.
            temp_cv = CV.objects.create(
                user=request.user,
                full_name="Temporary Job Description File",
                uploaded_file=job_file,
            )

            job_description = extract_text_from_cv(temp_cv.uploaded_file.path)
            # Delete the database row and its temporary association after parsing.
            temp_cv.delete()

        if job_description:
            # Keep the latest job context available to cover-letter generation.
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

            # AIService returns a comparison that the template renders directly.
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
    """Create a new CV variant rewritten for a supplied job description."""
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
        # Never overwrite the source CV: request tailored structured field data.
        tailored_data = ai.tailor_cv_to_job(cv_text, job_description)

        # Avoid repeatedly appending the suffix when tailoring an existing copy.
        base_name = cv.full_name.split(" - Tailored CV")[0]

        # Insert a separate CV, preserving contact details and falling back to
        # original sections whenever the AI omits a value.
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
