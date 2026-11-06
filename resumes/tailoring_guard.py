"""Conservative source-preservation checks for generated CV sections."""
import re


def words(text):
    return set(re.findall(r"[\w+#]+", str(text or "").casefold())) - {
        "at", "the", "and", "a", "an", "of", "in", "to", "for", "with", "using",
    }


def protect_source_sections(cv, data):
    """Fall back rather than save rewrites that lose source facts or duplicate projects.

Whole-section fallback intentionally favours fidelity over rewriting: token
coverage is not a complete factual verifier, and changed wording may also fall
back. Additional sections themselves are never rewritten by this workflow.
"""
    result = dict(data)
    restored = []
    for field in ("experience", "skills", "education"):
        source = getattr(cv, field) or ""
        proposed = result.get(field) or ""
        if source and not words(source).issubset(words(proposed)):
            result[field] = source
            restored.append(field)
    experience = result.get("experience") or ""
    from .cv_layout import PROJECT_TITLES
    for section in cv.additional_sections or []:
        if section["title"].strip().casefold() not in PROJECT_TITLES:
            continue
        # Project entry headings belong in Projects, unless already in source employment.
        for line in section["content"].splitlines():
            title = line.split("|")[0].strip()
            if len(title) >= 6 and "|" in line and title.casefold() in experience.casefold() and title.casefold() not in (cv.experience or "").casefold():
                result["experience"] = cv.experience or ""
                if "experience" not in restored:
                    restored.append("experience")
    summary = result.get("professional_summary") or ""
    # Recognition must be explicit evidence, not an embellishment of having projects.
    recognition = r"\b(recogni[sz]ed|award-winning|acclaimed|renowned)\b"
    evidence = " ".join(str(getattr(cv, field) or "") for field in
                        ("professional_summary", "experience", "education"))
    evidence += " " + " ".join(section["content"] for section in cv.additional_sections or [])
    if re.search(recognition, summary, re.I) and not re.search(recognition, evidence, re.I):
        result["professional_summary"] = cv.professional_summary or ""
        restored.append("professional_summary")
    return result, restored
