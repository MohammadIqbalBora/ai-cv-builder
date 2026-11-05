"""UK job search and daily or weekly digests; no CV data is sent to the provider."""
import logging
import re
from datetime import timedelta
from urllib.parse import urlsplit

import requests
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags

from .models import SentJobAlert

logger = logging.getLogger(__name__)
STOP_WORDS = set("a an and are as at be by for from in is it of on or the to with you your our we this that role job work experience skills required will have can all full time part position years year looking seeking opportunity successful candidate".split())


class JobSearchUnavailable(Exception):
    pass


def alerts_ready():
    return bool(settings.JOB_ALERTS_ENABLED and settings.ADZUNA_APP_ID and settings.ADZUNA_APP_KEY
                and settings.EMAIL_HOST and settings.DEFAULT_FROM_EMAIL
                and settings.EMAIL_BACKEND not in (
                    "django.core.mail.backends.console.EmailBackend", "django.core.mail.backends.dummy.EmailBackend")
                and urlsplit(settings.SITE_URL).scheme == "https"
                and urlsplit(settings.SITE_URL).netloc)


def absolute_url(name, token=None):
    return settings.SITE_URL + reverse(name, kwargs={"token": token} if token else None)


def words(text):
    tokens = {word.rstrip(".") for word in re.findall(r"[a-z][a-z0-9+#.]*", strip_tags(text or "").lower())}
    return {word for word in tokens if (len(word) > 2 or word in {"c#", "hr", "it"}) and word not in STOP_WORDS}


def search_jobs(preference):
    if not alerts_ready():
        raise JobSearchUnavailable("Job alerts are not connected yet.")
    params = {
        "app_id": settings.ADZUNA_APP_ID, "app_key": settings.ADZUNA_APP_KEY,
        "what": preference.target_role, "where": preference.location,
        "distance": round(preference.radius_miles * 1.609344),
        "results_per_page": 50, "sort_by": "date", "max_days_old": 14,
    }
    if preference.minimum_salary:
        params["salary_min"] = preference.minimum_salary
    try:
        response = requests.get("https://api.adzuna.com/v1/api/jobs/gb/search/1", params=params,
                                headers={"Accept": "application/json"}, timeout=(5, 12))
        response.raise_for_status()
        results = response.json().get("results", [])
        if not isinstance(results, list):
            raise ValueError("Unexpected provider response")
        return results
    except (requests.RequestException, ValueError, AttributeError):
        # Never log exception text: request URLs can include API credentials.
        raise JobSearchUnavailable("Job search is temporarily unavailable. Please try again later.") from None


def rank_jobs(preference, results, exclude_ids=()):
    cv = preference.cv
    if not cv or cv.user_id != preference.user_id:
        return []
    cv_words = words(" ".join(filter(None, [cv.job_title, cv.skills, cv.experience, cv.professional_summary, cv.education])))
    role_words = words(preference.target_role)
    if not role_words:
        return []
    seen = set(exclude_ids)
    ranked = []
    for job in results:
        if not isinstance(job, dict):
            continue
        job_id = str(job.get("id", ""))
        url = str(job.get("redirect_url", ""))
        try:
            parsed_url = urlsplit(url)
            host = (parsed_url.hostname or "").lower()
        except ValueError:
            continue
        if (not job_id or len(job_id) > 200 or job_id in seen
                or parsed_url.scheme not in ("http", "https")
                or not (host == "adzuna.co.uk" or host.endswith(".adzuna.co.uk"))):
            continue
        seen.add(job_id)
        title = strip_tags(str(job.get("title", "")))[:250]
        description = strip_tags(str(job.get("description", "")))
        text = (title + " " + description).lower()
        # Work arrangements are filtered only when explicitly mentioned in the advert.
        if preference.work_preference == "remote" and (not re.search(r"remote|work from home|home.based", text) or "hybrid" in text):
            continue
        if preference.work_preference == "hybrid" and "hybrid" not in text:
            continue
        title_matches = role_words & words(title)
        if not title_matches or not role_words.issubset(words(title + " " + description)):
            continue
        matched = sorted(cv_words & words(title + " " + description))
        if not matched:
            continue
        salary = job.get("salary_min")
        try:
            if preference.minimum_salary and (not salary or float(salary) < preference.minimum_salary):
                continue
        except (ValueError, TypeError):
            continue
        company = job.get("company") if isinstance(job.get("company"), dict) else {}
        location = job.get("location") if isinstance(job.get("location"), dict) else {}
        score = len(title_matches) * 5 + len(matched)
        ranked.append({
            "id": job_id, "title": title, "url": url,
            "company": strip_tags(str(company.get("display_name", "Employer not supplied"))),
            "location": strip_tags(str(location.get("display_name", "Location not supplied"))),
            "reason": "Words shared with your CV: " + ", ".join(matched[:8]),
            "score": score,
        })
    return sorted(ranked, key=lambda job: (-job["score"], job["id"]))[:5]


def send_confirmation(preference):
    if not alerts_ready() or not preference.enabled or preference.confirmed_email == preference.user.email:
        return False
    now = timezone.now()
    if preference.confirmation_sent_at and preference.confirmation_sent_at > now - timedelta(days=1):
        return False
    url = absolute_url("confirm_job_alerts", preference.email_token)
    unsubscribe = absolute_url("unsubscribe_job_alerts", preference.email_token)
    frequency = "daily" if preference.frequency == "daily" else "weekly"
    body = (f"You requested {frequency} job alerts from AI CV Builder. Confirm your email to start receiving them:\n"
            + url + "\n\nIf you did not request this, ignore this email or stop the request here:\n" + unsubscribe)
    message = EmailMultiAlternatives("Confirm your AI CV Builder job alerts", body,
                                    settings.DEFAULT_FROM_EMAIL, [preference.user.email])
    if message.send() != 1:
        raise JobSearchUnavailable("Email could not be delivered.")
    preference.confirmation_sent_at = now
    preference.confirmation_email = preference.user.email
    preference.save(update_fields=["confirmation_sent_at", "confirmation_email"])
    return True


def send_job_digest(preference):
    """Caller must hold a lock on this preference until delivery is recorded."""
    now = timezone.now()
    if (not preference.enabled or not preference.cv or not preference.user.email
            or preference.cv.user_id != preference.user_id or not preference.user.is_active):
        return "skipped"
    subscription = getattr(preference.user, "subscription", None)
    if not subscription or not subscription.has_premium_access:
        return "skipped"
    if preference.last_attempt_at and preference.last_attempt_at > now - timedelta(hours=24):
        return "skipped"
    if preference.confirmed_email != preference.user.email:
        # A pending email gets one automatic confirmation, not daily reminders.
        if preference.confirmation_sent_at:
            return "skipped"
        return "confirmation" if send_confirmation(preference) else "skipped"
    frequency = "daily" if preference.frequency == "daily" else "weekly"
    interval = timedelta(days=1 if frequency == "daily" else 7)
    if preference.last_checked_at and preference.last_checked_at > now - interval:
        return "skipped"
    preference.last_attempt_at = now
    preference.save(update_fields=["last_attempt_at"])
    sent_ids = preference.sentjobalert_set.values_list("provider_job_id", flat=True)
    matches = rank_jobs(preference, search_jobs(preference), sent_ids)
    if matches:
        unsubscribe = absolute_url("unsubscribe_job_alerts", preference.email_token)
        context = {"jobs": matches, "frequency": frequency, "preferences_url": absolute_url("job_alert_preferences"), "unsubscribe_url": unsubscribe}
        text = render_to_string("emails/job_digest.txt", context)
        html = render_to_string("emails/job_digest.html", context)
        message = EmailMultiAlternatives(
            f"Your {frequency} job matches from AI CV Builder", text, settings.DEFAULT_FROM_EMAIL,
            [preference.user.email], headers={"List-Unsubscribe": "<" + unsubscribe + ">"},
        )
        message.attach_alternative(html, "text/html")
        if message.send() != 1:
            raise JobSearchUnavailable("Email could not be delivered.")
        SentJobAlert.objects.bulk_create([SentJobAlert(preference=preference, provider_job_id=job["id"]) for job in matches])
        preference.last_sent_at = now
    preference.last_checked_at = now
    preference.save(update_fields=["last_checked_at", "last_sent_at"])
    return "sent" if matches else "no_matches"
