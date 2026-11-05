"""Run daily; send each confirmed subscriber's daily or weekly digest when due."""
import logging
from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from resumes.job_alert_service import alerts_ready, send_job_digest
from resumes.models import JobAlertPreference

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send due daily or weekly Premium job digests. Requires configured job API and SMTP."

    def add_arguments(self, parser):
        parser.add_argument("--check", action="store_true", help="Check configuration without sending emails or searching.")

    def handle(self, *args, **options):
        if not alerts_ready():
            raise CommandError("Job alerts are inactive: configure licensed Adzuna access, SMTP, sender, HTTPS DOMAIN and JOB_ALERTS_ENABLED.")
        if options["check"]:
            self.stdout.write("Job alert configuration is present. No email or API request was sent.")
            return
        counts = Counter()
        ids = JobAlertPreference.objects.filter(enabled=True).values_list("pk", flat=True)
        for pk in ids.iterator():
            with transaction.atomic():
                preference = JobAlertPreference.objects.select_for_update(skip_locked=True).filter(pk=pk).first()
                if not preference:
                    continue
                try:
                    outcome = send_job_digest(preference)
                    counts[outcome] += 1
                except Exception:
                    preference.last_attempt_at = timezone.now()
                    preference.save(update_fields=["last_attempt_at"])
                    counts["failed"] += 1
                    logger.warning("Job alert processing failed for preference %s", pk)
        self.stdout.write(
            "Job alerts: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
        )
