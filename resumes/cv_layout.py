"""Validated evidence order shared by CV previews and PDF exports."""
PROJECT_TITLES = {"projects", "personal projects", "selected projects", "portfolio", "project experience"}


def normalise_section_order(value, extras):
    allowed = {"professional_summary", "skills", "experience", "education"}
    allowed.update(f"additional:{index}" for index, _ in enumerate(extras or []))
    result = []
    for key in value if isinstance(value, list) else []:
        if isinstance(key, str) and key in allowed and key not in result:
            result.append(key)
    return result


def modern_sections(cv):
    """Apply the saved relevance ranking without deleting unranked content."""
    extras = cv.additional_sections or []
    sections = [
        {"id": "professional_summary", "title": "Professional Profile", "content": cv.professional_summary},
        {"id": "skills", "title": "Skills", "content": cv.skills},
    ]
    projects, other = [], []
    for index, item in enumerate(extras):
        section = dict(item, id=f"additional:{index}", entries=True)
        (projects if item["title"].strip().casefold() in PROJECT_TITLES else other).append(section)
    # Safe fallback for older/source CVs; no inference from seniority or job title.
    sections.extend(projects)
    sections.extend([
        {"id": "experience", "title": "Professional Experience", "content": cv.experience, "entries": True},
        {"id": "education", "title": "Education and Certifications", "content": cv.education},
    ])
    sections.extend(other)
    by_id = {item["id"]: item for item in sections}
    order = normalise_section_order(cv.section_order, extras)
    ordered = [by_id[key] for key in order]
    ordered.extend(item for item in sections if item["id"] not in order)
    return [item for item in ordered if item["content"] and str(item["content"]).strip()]
