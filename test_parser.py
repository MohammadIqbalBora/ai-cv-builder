from resumes.cv_parser import extract_text_from_cv

file_path = "media/cv_uploads/M_Bora_CV_2026.docx"

text = extract_text_from_cv(file_path)

print("=" * 50)
print("EXTRACTED TEXT")
print("=" * 50)
print(text)
