"""Account-owned job alert preferences and email confirmation/opt-out links."""
import logging
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import JobAlertForm
from .job_alert_service import alerts_ready, rank_jobs, search_jobs, send_confirmation, JobSearchUnavailable
from .models import JobAlertPreference, Subscription

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET", "POST"])
def preferences(request):
    subscription = Subscription.objects.filter(user=request.user).first()
    premium = bool(subscription and subscription.has_premium_access)
    preference = JobAlertPreference.objects.filter(user=request.user).first()
    if not premium:
        return render(request, "job_alerts.html", {"premium": False, "preference": preference})
    note, error, jobs = None, None, None
    form = JobAlertForm(request.POST if request.method == "POST" else None, user=request.user, instance=preference)
    if request.method == "POST" and form.is_valid():
        if request.POST.get("action") == "preview":
            preview = form.save(commit=False)
            preview.user = request.user
            try:
                jobs = rank_jobs(preview, search_jobs(preview))
            except JobSearchUnavailable as exc:
                error = str(exc)
        else:
            # Align with the worker lock so opting out cannot race a new digest.
            with transaction.atomic():
                if preference:
                    JobAlertPreference.objects.select_for_update().get(pk=preference.pk)
                preference = form.save(commit=False)
                preference.user = request.user
                if preference.enabled and (not preference.consented_at or "enabled" in form.changed_data):
                    preference.consented_at = timezone.now()
                preference.save()
            note = "Your job alert preferences have been saved." if preference.enabled else "Job alert emails are paused."
            if preference.enabled and alerts_ready():
                try:
                    send_confirmation(preference)
                except Exception:
                    # Suppress SMTP/provider exception bodies, which may contain personal data.
                    logger.warning("Job alert confirmation delivery failed for preference %s", preference.pk)
                    error = "Preferences saved, but the confirmation email could not be sent. Please try again later."
    return render(request, "job_alerts.html", {
        "premium": premium, "form": form, "preference": preference,
        "ready": alerts_ready(), "note": note, "error": error, "jobs": jobs,
        "needs_confirmation": preference and preference.enabled and preference.confirmed_email != request.user.email,
    })


@require_http_methods(["GET", "POST"])
def confirm_email(request, token):
    preference = get_object_or_404(JobAlertPreference.objects.select_related("user"), email_token=token)
    valid = bool(preference.enabled and preference.confirmation_email == preference.user.email
                 and preference.confirmation_sent_at
                 and preference.confirmation_sent_at > timezone.now() - timedelta(days=7))
    done = False
    if request.method == "POST" and valid:
        preference.confirmed_email = preference.user.email
        preference.save(update_fields=["confirmed_email"])
        done = True
    return render(request, "job_alert_confirmation.html", {"valid": valid, "done": done})


@require_http_methods(["GET", "POST"])
def unsubscribe(request, token):
    # GET is a confirmation page so mail scanners cannot change preferences.
    preference = get_object_or_404(JobAlertPreference, email_token=token)
    done = False
    if request.method == "POST":
        with transaction.atomic():
            preference = JobAlertPreference.objects.select_for_update().get(pk=preference.pk)
            preference.enabled = False
            preference.save(update_fields=["enabled"])
        done = True
    return render(request, "job_alert_unsubscribe.html", {"done": done})
