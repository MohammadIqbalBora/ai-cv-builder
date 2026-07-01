from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("cv/create/", views.create_cv, name="create_cv"),
    path("cv/download/<int:id>/", views.download_cv_pdf, name="download_cv_pdf"),
]
