from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("cv/create/", views.create_cv, name="create_cv"),
    path("cv/edit/<int:id>/", views.edit_cv, name="edit_cv"),
    path("cv/delete/<int:id>/", views.delete_cv, name="delete_cv"),
    path(
        "cv/pdf-templates/<int:id>/",
        views.select_pdf_template,
        name="select_pdf_template",
    ),
    path("cv/download/<int:id>/", views.download_cv_pdf, name="download_cv_pdf"),
    path("cv/improve/<int:id>/", views.improve_cv_ai, name="improve_cv_ai"),
    path(
        "cover-letter/<int:id>/", views.create_cover_letter, name="create_cover_letter"
    ),
    path("pricing/", views.pricing, name="pricing"),
    path("subscribe/", views.create_checkout_session, name="subscribe"),
    path("stripe/success/", views.stripe_success, name="stripe_success"),
    path("stripe/cancel/", views.stripe_cancel, name="stripe_cancel"),
    path("cv/<int:id>/", views.cv_detail, name="cv_detail"),
    path("cv/view/<int:id>/", views.cv_preview, name="cv_preview"),
    path(
        "cv/import/<int:id>/",
        views.import_uploaded_cv,
        name="import_uploaded_cv",
    ),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
]
