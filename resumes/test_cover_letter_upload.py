from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from docx import Document
from reportlab.pdfgen import canvas

from .models import CV, CoverLetter


@override_settings(SECURE_SSL_REDIRECT=False, STORAGES={
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class CoverLetterUploadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='letter-upload-owner')
        self.cv = CV.objects.create(user=self.user, full_name='Example')
        self.client.force_login(self.user)
        self.url = reverse('create_cover_letter', args=[self.cv.pk])

    @patch('resumes.views.AIService')
    def test_pdf_and_docx_uploads_supply_job_text(self, ai):
        ai.return_value.generate_cover_letter.return_value = 'Dear hiring manager'
        for extension in ('pdf', 'docx'):
            with self.subTest(extension=extension):
                stream = BytesIO()
                if extension == 'pdf':
                    pdf = canvas.Canvas(stream)
                    pdf.drawString(50, 750, 'Python developer role')
                    pdf.save()
                else:
                    document = Document()
                    document.add_paragraph('Python developer role')
                    document.save(stream)
                response = self.client.post(self.url, {
                    'job_description': 'Old job text',
                    'job_file': SimpleUploadedFile('job.' + extension, stream.getvalue()),
                })
                self.assertEqual(response.status_code, 302)
                self.assertEqual(CoverLetter.objects.latest('pk').job_description, 'Python developer role')
                self.assertEqual(ai.return_value.generate_cover_letter.call_args.args[1], 'Python developer role')

    @patch('resumes.views.AIService')
    def test_invalid_empty_and_unreadable_inputs_do_not_generate(self, ai):
        for payload in ({}, {'job_file': SimpleUploadedFile('job.txt', b'text')},
                        {'job_file': SimpleUploadedFile('job.pdf', b'broken document')}):
            response = self.client.post(self.url, payload)
            self.assertEqual(response.status_code, 400)
            self.assertContains(response, 'role="alert"', status_code=400)
        ai.assert_not_called()
        self.assertFalse(CoverLetter.objects.exists())

    @patch('resumes.views.AIService')
    def test_pasted_description_works_without_prior_matching(self, ai):
        ai.return_value.generate_cover_letter.return_value = 'Letter'
        self.assertEqual(self.client.post(self.url, {'job_description': 'New role'}).status_code, 302)
        self.assertEqual(CoverLetter.objects.get().job_description, 'New role')
