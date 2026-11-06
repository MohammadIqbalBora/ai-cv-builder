# CV quality release checks

All CV templates use the relevance order saved during tailoring. The AI ranks
employment, projects, qualifications and other supplied sections against the job
specification, regardless of profession or title. Invalid or duplicate section
IDs are ignored; omitted sections are appended so evidence is not lost. Older
CVs without a saved ranking use a projects-first fallback.

Apply the schema change before using this version:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

## Automated checks

Run the suite without connecting to the hosted database:

```powershell
.\.venv\Scripts\python.exe manage.py test --settings=config.test_settings --noinput
```

The PDF regression tests cover complete skills and contact details, project
ordering, qualifications, multi-page content, links, long tokens and escaped
markup. AI calls in the test suite are mocked: passing tests do not establish
that real model output meets the writing requirements.

## Quality gate before public launch

1. Test real tailoring on a fixed set of consented or fictional CVs covering an
   entry-level developer, an experienced developer, a career changer and at least
   two non-technical professions. Include jobs with alternative requirements.
2. Compare each result against the source. Require no invented skills, employers,
   dates, qualifications, numerical claims or commercial project experience.
   Check that named skills, qualifications and portfolio links survive upload,
   tailoring, review, saving and export. Record failures and retest after changes.
3. Inspect every PDF template visually with short and long inputs. Check all pages,
   readable text, links, page breaks, contact details and preview section order.
   Modern uses flowing paragraphs; headings stay with subsequent content but long
   roles can still continue onto another page.
4. Test the complete user journey in staging: upload, analyse, tailor, compare,
   correct, save and download. Test AI timeouts, invalid responses and retry
   behaviour so failures do not lose source content or create confusing copies.
5. Exercise signup, account ownership boundaries, free download limits and Stripe
   test-mode purchase, webhook retries and cancellation. Confirm paid exports and
   free watermark behaviour. Preserve the existing comparison step before export.
6. Run Django deployment checks against the actual staging/production settings.
   Local checks reported a weak/default secret key and missing HSTS. Verify a
   strong deployment secret, DEBUG=False, HTTPS and the intended HSTS policy;
   the local result is not an audit of the deployed environment.
7. Verify upload privacy, deletion, backups and restoration, error monitoring and
   limits on costly AI requests. Start with a small beta and review failed or
   corrected outputs before opening paid access widely.

## Existing CVs

Prompt changes apply to new imports/tailoring requests. They do not repair saved
text. Re-import the original document if qualifications were lost during upload,
then tailor a new copy. Rendering changes apply on the next Modern PDF download.

## Scope

This change improves Modern exports and the upload/tailoring instructions. It is
not a complete security, billing, accessibility or production-readiness audit.
Classic and Executive rendering remain separate implementations and need their
own visual review, although they share section ordering. The named-skill preservation and writing rules are model
instructions, not deterministic factual validation.
