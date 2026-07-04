from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from .cv_parser import extract_text_from_cv, parse_cv_text

import stripe

from .ai_service import AIService
from .forms import CVForm
from .models import CV, Subscription
from .pdf_templates import (
    render_classic_pdf,
    render_executive_pdf,
    render_modern_pdf,
)


def home(request):
    return render(request, "home.html")


@login_required
def dashboard(request):
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
    ai_improvements_used = total_cvs
    cover_letters_generated = total_cvs

    return render(
        request,
        "dashboard.html",
        {
            "cvs": cvs,
            "selected_cv": selected_cv,
            "total_cvs": total_cvs,
            "ai_improvements_used": ai_improvements_used,
            "cover_letters_generated": cover_letters_generated,
            "is_premium": is_premium,
            "plan_name": plan_name,
        },
    )


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


@login_required
def delete_cv(request, id):
    cv = get_object_or_404(CV, id=id, user=request.user)

    if request.method == "POST":
        cv.delete()
        return redirect("dashboard")

    return render(request, "delete_cv.html", {"cv": cv})


def user_has_active_subscription(user):
    return Subscription.objects.filter(user=user, is_active=True).exists()


@login_required
def improve_cv_ai(request, id):
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
    if not user_has_active_subscription(request.user):
        return redirect("subscribe")

    cv = get_object_or_404(CV, id=id, user=request.user)

    cover_letter = None

    if request.method == "POST":
        job_description = request.POST.get("job_description")

        ai = AIService()

        cv_text = f"""
Name: {cv.full_name}
Job Title: {cv.job_title}
Summary: {cv.professional_summary}
Skills: {cv.skills}
Experience: {cv.experience}
"""

        cover_letter = ai.generate_cover_letter(cv_text, job_description)

    return render(
        request,
        "cover_letter.html",
        {"cv": cv, "cover_letter": cover_letter},
    )


@login_required
def download_cv_pdf(request, id):
    if not user_has_active_subscription(request.user):
        return redirect("subscribe")

    cv = get_object_or_404(CV, id=id, user=request.user)

    if cv.template == "modern":
        return render_modern_pdf(cv)

    if cv.template == "classic":
        return render_classic_pdf(cv)

    if cv.template == "executive":
        return render_executive_pdf(cv)

    return render_modern_pdf(cv)


@login_required
def cv_preview(request, id):
    cv = get_object_or_404(CV, id=id, user=request.user)
    return render(request, "cv_preview.html", {"cv": cv})


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

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        metadata = session.get("metadata") or {}
        user_id = metadata.get("user_id")

        print("SESSION METADATA:", metadata)
        print("USER ID:", user_id)

        if user_id:
            subscription, _created = Subscription.objects.get_or_create(user_id=user_id)

            subscription.stripe_customer_id = session.get("customer")
            subscription.stripe_subscription_id = session.get("subscription")
            subscription.is_active = True
            subscription.plan_name = "Premium"
            subscription.save()

    return HttpResponse(status=200)


@login_required
def import_uploaded_cv(request, id):
    cv = get_object_or_404(CV, id=id, user=request.user)

    extracted_text = ""

    if cv.uploaded_file:
        extracted_text = extract_text_from_cv(cv.uploaded_file.path)

        if request.method == "POST":
            parsed_data = parse_cv_text(extracted_text)

            cv.full_name = parsed_data.get("full_name") or cv.full_name
            cv.email = parsed_data.get("email") or cv.email
            cv.phone = parsed_data.get("phone") or cv.phone
            cv.professional_summary = (
                parsed_data.get("professional_summary") or cv.professional_summary
            )
            cv.skills = parsed_data.get("skills") or cv.skills
            cv.experience = parsed_data.get("experience") or cv.experience
            cv.education = parsed_data.get("education") or cv.education

            cv.save()
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
