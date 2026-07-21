# This module maps URL paths to the views that handle them.

"""URL patterns for the resumes app."""

# `path` connects each browser URL to one function in resumes/views.py.
from django.urls import path

# Import the view functions named in the route table below.
from . import views

# config/urls.py includes this table at the site root, so these fragments do
# not receive an additional prefix.
urlpatterns = [
    # Public landing page.
    path("", views.home, name="home"),
    # Logged-in user's saved CV list.
    path("dashboard/", views.dashboard, name="dashboard"),
    # Form that creates a new CV database record.
    path("cv/create/", views.create_cv, name="create_cv"),
    # `<int:id>` captures a numeric CV ID and passes it to the view function.
    path("cv/edit/<int:id>/", views.edit_cv, name="edit_cv"),
    # Confirmation and deletion flow for one owned CV.
    path("cv/delete/<int:id>/", views.delete_cv, name="delete_cv"),
    # Let the owner choose which visual PDF renderer the CV uses.
    path(
        "cv/pdf-templates/<int:id>/",
        views.select_pdf_template,
        name="select_pdf_template",
    ),
    # Generate and return the selected CV design as a PDF download.
    path("cv/download/<int:id>/", views.download_cv_pdf, name="download_cv_pdf"),
    # Ask the AI service to improve the CV's written sections.
    path("cv/improve/<int:id>/", views.improve_cv_ai, name="improve_cv_ai"),
    # Generate a cover letter using this CV as source material.
    path(
        "cover-letter/<int:id>/", views.create_cover_letter, name="create_cover_letter"
    ),
    # Turn the saved cover letter into a downloadable PDF.
    path(
        "cover-letter/<int:id>/download/",
        views.download_cover_letter_pdf,
        name="download_cover_letter_pdf",
    ),
    # Display Free/Premium plan information.
    path("pricing/", views.pricing, name="pricing"),
    # Create a Stripe-hosted checkout session.
    path("subscribe/", views.create_checkout_session, name="subscribe"),
    # Landing pages used after Stripe checkout completes or is cancelled.
    path("stripe/success/", views.stripe_success, name="stripe_success"),
    path("stripe/cancel/", views.stripe_cancel, name="stripe_cancel"),
    # Show all stored fields for a single CV.
    path("cv/<int:id>/", views.cv_detail, name="cv_detail"),
    # Show the CV in an on-screen preview layout.
    path("cv/view/<int:id>/", views.cv_preview, name="cv_preview"),
    # Parse an uploaded CV file and copy detected text into the CV record.
    path(
        "cv/import/<int:id>/",
        views.import_uploaded_cv,
        name="import_uploaded_cv",
    ),
    # Receive server-to-server Stripe event notifications.
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
    # Compare the CV with a supplied job description.
    path("job-match/<int:id>/", views.job_match, name="job_match"),
    # Use AI to rewrite the CV toward that job description.
    path("job-match/<int:id>/tailor/", views.tailor_cv_to_job, name="tailor_cv_to_job"),
]
