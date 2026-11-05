from django.core.exceptions import ValidationError


MAX_ADDITIONAL_SECTIONS = 10
MAX_SECTION_TITLE = 80
MAX_SECTION_CONTENT = 5000


def validate_additional_sections(value):
    """Keep user-defined CV sections small and consistently structured."""
    if not isinstance(value, list):
        raise ValidationError("Additional sections must be a list.")
    if len(value) > MAX_ADDITIONAL_SECTIONS:
        raise ValidationError("You can add up to 10 additional sections.")
    for section in value:
        if not isinstance(section, dict):
            raise ValidationError("Each additional section needs a heading and details.")
        title, content = section.get("title"), section.get("content")
        if not isinstance(title, str) or not isinstance(content, str) or not title.strip() or not content.strip():
            raise ValidationError("Enter both a heading and details for each additional section, or remove it.")
        if len(title) > MAX_SECTION_TITLE:
            raise ValidationError("Section headings must be 80 characters or fewer.")
        if len(content) > MAX_SECTION_CONTENT:
            raise ValidationError("Section details must be 5,000 characters or fewer.")
