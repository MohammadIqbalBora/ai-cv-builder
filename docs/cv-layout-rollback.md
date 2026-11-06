# Restore the layout behaviour before relevance ordering

Baseline commit: `3e3d104` (Restore original CV layouts and previews).

To discard only this section-ordering change, restore these paths from that commit:

```powershell
git restore --source=3e3d104 -- resumes/ai_service.py resumes/models.py resumes/modern_pdf.py resumes/classic_pdf.py resumes/executive_pdf.py templates/cv_detail.html templates/cv_preview.html templates/dashboard.html templates/includes/additional_cv_sections.html templates/includes/classic_cv.html
```

The new `templates/includes/leading_projects.html` and `resumes/test_project_order.py`
can then be deleted. No database migration is required for this change or rollback.
Commit and push the restoration if this version has been deployed. This baseline
preserves the AI writing improvements and Professional Profile form label.
