# Premium Job Alerts: activation and operation

The integration is deployed **inactive by default**. It does not send email or query a job API until configured. There are no new paid add-ons or vendor accounts provisioned automatically.

## Provider and permissions

Use an Adzuna account with licensed access covering a paid CV-builder service and distribution of listings in email digests. Confirm this use with Adzuna before enabling the integration. A free evaluation API key alone does not establish permission for ongoing commercial use.

- API access: https://developer.adzuna.com/
- API terms and attribution: https://developer.adzuna.com/docs/terms_of_service
- API search documentation: https://developer.adzuna.com/docs/search

The adapter uses the UK search endpoint over HTTPS and requests up to 50 recent adverts for one role/location search. It passes role, location, distance and optional salary, not the CV, name, account email or phone. Matching runs locally using CV keywords. It is not an AI assessment of qualifications or a recommendation that the user is eligible for a regulated role. Descriptions supplied by this endpoint can be truncated.

Attribution and the provider's application link are included for every displayed/emailed vacancy. Do not remove these when editing the templates. Verify that the actual granted licence covers this presentation and email delivery.

## Email delivery

Choose an SMTP email delivery service and verify a sending domain/address with it. Configure SPF/DKIM and the provider's recommended DMARC policy. Use the service's SMTP credentials, not a personal account password. Set credentials directly in Heroku Settings > Config Vars; do not put them in Git, screenshots or chat.

Config Vars:

| Variable | Value |
| --- | --- |
| `ADZUNA_APP_ID` | Issued app ID |
| `ADZUNA_APP_KEY` | Issued API key |
| `DOMAIN` | `https://ai-cv-builder-mb-958b88cc64d9.herokuapp.com` (or the production HTTPS domain) |
| `EMAIL_HOST` | SMTP host from the email provider |
| `EMAIL_PORT` | Usually `587`, as specified by the provider |
| `EMAIL_HOST_USER` | SMTP username |
| `EMAIL_HOST_PASSWORD` | SMTP credential |
| `DEFAULT_FROM_EMAIL` | Verified sender, e.g. `AI CV Builder <alerts@your-domain>` |
| `EMAIL_USE_TLS` | `True` for STARTTLS, per provider instructions |
| `EMAIL_USE_SSL` | `False` when using STARTTLS; never enable both |
| `EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` (the default) |
| `JOB_ALERTS_ENABLED` | Keep `False` until credentials, commercial licence and email delivery are ready; then `True` |

`python manage.py send_job_alerts --check` validates required configuration presence only. It sends no email and does not test credentials or the licence.

## End-to-end check before enabling for customers

1. Configure the services, then enable alerts.
2. With an account you control that has Premium access, open **Job alerts**, choose an owned CV, enter a UK role/location and choose **Daily** or **Weekly** emails. Existing preferences default to Weekly.
3. Use **Preview job matches** to verify live API access. A preview does not subscribe the account or save preferences.
4. Explicitly opt in and save preferences. A confirmation email is sent to the account address. Follow its link and confirm on the page.
5. Run `python manage.py send_job_alerts` and confirm receipt, formatting, application links and provider attribution in that account's inbox.
6. Run it again: no duplicate digest should be sent within 24 hours for Daily or seven days for Weekly. Test both frequency choices and the unsubscribe link (a confirmation page followed by POST), then verify a paused subscription sends nothing.

Do not send test digests to real customers. No live end-to-end API/email test was performed while credentials were unavailable.

## Scheduling on Heroku

Use Heroku Scheduler or an equivalent scheduler to run:

```text
python manage.py send_job_alerts
```

Run **daily**; the command itself enforces each user's selected interval: at least 24 hours for Daily or seven days for Weekly, measured from the last completed check. Delivery happens on the next scheduled run after that interval. Changing frequency uses the existing last-check timestamp; it does not trigger an immediate email or clear previously sent job IDs. Heroku Scheduler's job times are UTC, and its one-off dynos consume usage. Configure the add-on and daily task in Heroku after deciding on that usage; it is not provisioned by this code. See https://devcenter.heroku.com/articles/scheduler.

Each run checks current Premium access, explicit opt-in, a valid owned CV and confirmed account email. A user whose selected CV was deleted must choose a new CV. Expired Premium accounts stop receiving digests automatically; pausing or deleting an account stops them too.

The command locks a preference while processing it, so overlapping PostgreSQL worker runs skip a preference already being processed. It records provider job IDs after successful email submission and skips them in later digests, even if the selected CV or email frequency is changed. An empty result advances the daily or weekly check without sending an empty email. Failed searches/delivery wait 24 hours before retrying. One confirmation is sent automatically when a saved pending preference becomes eligible; repeated reminders are not sent automatically. A user can request a resend by saving preferences after 24 hours.

SMTP submission and a database commit cannot be atomic: a process crash after accepted delivery but before commit can result in a repeated email on a later retry. For larger-scale or delivery-critical use, adopt a durable outbox and a provider supporting idempotent delivery. No exactly-once delivery is claimed.

## Privacy and monitoring

- Disclose the opt-in job-alert processing, provider, search data and retention in the site's privacy notice before activation.
- Consent and confirmation timestamps and job IDs already emailed are stored; full third-party adverts are not stored in the database. Preference and sent-ID records are removed with the account. Configure the site's wider retention policy separately.
- Email confirmation links expire after seven days and cannot confirm a newly changed account email using an old email's link. Unsubscribe links remain usable without login while the preference exists.
- Logs contain counts and preference IDs, not CVs, API URLs/keys or SMTP exception details.
- Monitor `sent`, `confirmation`, `no_matches`, `skipped`, and `failed` counts. Repeated `failed` runs require checking provider access and SMTP configuration without exposing credentials.
- Set `JOB_ALERTS_ENABLED=False` to suspend searches, previews and emails globally without losing saved preferences.
