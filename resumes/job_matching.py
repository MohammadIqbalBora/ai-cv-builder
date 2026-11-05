"""Shared score policy and identity checks for CV tailoring."""

import hashlib
import json
from decimal import Decimal, InvalidOperation


MIN_TAILOR_MATCH_SCORE = 40
STRONG_MATCH_SCORE = 60


def cv_matching_text(cv):
    fields = (
        ("Name", cv.full_name), ("Job Title", cv.job_title),
        ("Email", cv.email), ("Phone", cv.phone), ("Address", cv.address),
        ("Professional Summary", cv.professional_summary), ("Skills", cv.skills),
        ("Experience", cv.experience), ("Education", cv.education),
    )
    lines = [f"{title}: {value or ''}" for title, value in fields]
    lines.extend(f"{section['title']}: {section['content']}" for section in cv.additional_sections)
    return "\n".join(lines)


def match_fingerprint(cv, job_description):
    data = json.dumps([cv.pk, cv_matching_text(cv), job_description], ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def normalise_analysis(analysis):
    """Reject invalid scores rather than treating them as permission to tailor."""
    result = dict(analysis) if isinstance(analysis, dict) else {}
    score = result.get("match_score")
    try:
        if isinstance(score, bool) or not isinstance(score, (int, float, str, Decimal)):
            raise ValueError
        number = Decimal(str(score).strip().removesuffix("%").strip())
        if not number.is_finite() or not 0 <= number <= 100:
            raise ValueError
        result["match_score"] = float(number)
    except (InvalidOperation, ValueError):
        result["match_score"] = None
    return result


def job_match_context(cv, job_description="", analysis=None, **extra):
    score = analysis.get("match_score") if analysis else None
    return {
        "cv": cv, "job_description": job_description, "analysis": analysis,
        "match_score": score, "minimum_match_score": MIN_TAILOR_MATCH_SCORE,
        "can_tailor": score is not None and score >= MIN_TAILOR_MATCH_SCORE,
        "weak_match": score is not None and MIN_TAILOR_MATCH_SCORE <= score < STRONG_MATCH_SCORE,
        **extra,
    }
