# This file helps build or display printable PDF versions of a CV.

"""Exports PDF renderer functions for the resumes app."""

# Re-export one renderer from each design-specific module so callers can import
# all supported PDF styles from this single module.
from .classic_pdf import render_classic_pdf
from .executive_pdf import render_executive_pdf
from .modern_pdf import render_modern_pdf

# Explicitly document the public names exposed by `from ... import *` and tools.
__all__ = [
    "render_classic_pdf",
    "render_executive_pdf",
    "render_modern_pdf",
]
