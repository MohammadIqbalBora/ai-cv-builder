# This file contains automated checks for the application's behaviour.

from resumes.cv_parser import extract_text_from_cv  # Import CV text extraction helper

# Example path to a CV file inside the project's `media` directory
file_path = "media/cv_uploads/M_Bora_CV_2026.docx"

# Call the parser to extract raw text from the CV file
text = extract_text_from_cv(file_path)

# Print a simple delimiter and the extracted text for quick manual testing
print("=" * 50)
print("EXTRACTED TEXT")
print("=" * 50)
print(text)
