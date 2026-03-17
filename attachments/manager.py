"""
Attachment manager.
Provides access to the canonical resume PDF and thesis PDFs.
"""
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

ATTACHMENTS_DIR = Path(__file__).parent


def get_resume_path() -> Path | None:
    """Return the path to the canonical resume PDF, or None if not found."""
    resume_path_env = os.getenv("RESUME_PATH", "attachments/resume.pdf")
    # Resolve relative to project root
    root = Path(__file__).parent.parent
    resume_path = root / resume_path_env

    if not resume_path.exists():
        logger.warning(
            f"Resume PDF not found at {resume_path}. "
            f"Place your resume at attachments/resume.pdf"
        )
        return None

    return resume_path


def list_thesis_files() -> list[dict]:
    """
    Return a list of dicts describing available thesis PDFs from the filesystem.
    Each dict: { filename, filepath, industry_label }
    Convention: files named thesis_<industry>.pdf
    """
    thesis_files = []
    for f in ATTACHMENTS_DIR.glob("thesis_*.pdf"):
        industry = f.stem.replace("thesis_", "").replace("_", " ").title()
        thesis_files.append({
            "filename": f.name,
            "filepath": str(f),
            "industry_label": industry,
        })
    return thesis_files
