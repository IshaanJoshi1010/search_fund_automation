"""
Thesis matcher.
Given a lead's sector_focus tags, returns the best matching thesis PDF and its industry label.
"""
import logging
from pathlib import Path
from sqlalchemy.orm import Session

from models import Lead
from attachments.manager import list_thesis_files

logger = logging.getLogger(__name__)

ATTACHMENTS_DIR = Path(__file__).parent

# Mapping from sector tags → thesis filename prefix
SECTOR_THESIS_MAP = {
    "software": ["software", "verticalSaaS", "saas", "tech"],
    "tech_enabled_services": ["tech", "software", "services"],
    "healthcare": ["healthcare", "health"],
    "government_services": ["government", "public"],
    "industrials": ["industrial", "manufacturing"],
    "lower_middle_market": ["general", "lmm"],
    "consumer": ["consumer", "retail"],
}


def get_thesis_for_lead(lead: Lead, session: Session) -> tuple[Path | None, str | None]:
    """
    Return (thesis_pdf_path, thesis_industry_label) for a lead.
    Falls back to thesis_general.pdf if no specific match found.
    """
    available = list_thesis_files()
    if not available:
        return None, None

    # Build a lookup by industry label (lowercased)
    by_label = {t["industry_label"].lower(): t for t in available}
    by_file = {Path(t["filepath"]).stem.lower(): t for t in available}

    # Try to match by sector tags
    sector_tags = lead.sector_focus or []
    for tag in sector_tags:
        prefixes = SECTOR_THESIS_MAP.get(tag, [])
        for prefix in prefixes:
            # Look for a thesis file whose name starts with the prefix
            for stem, thesis in by_file.items():
                if prefix.lower() in stem:
                    path = Path(thesis["filepath"])
                    label = thesis["industry_label"]
                    logger.info(f"  Matched thesis '{label}' for lead {lead.email} (sector: {tag})")
                    return path, label

    # Fallback: general thesis
    general = ATTACHMENTS_DIR / "thesis_general.pdf"
    if general.exists():
        return general, "ETA / Search Fund"

    logger.warning(f"No matching thesis found for {lead.email}, no attachment.")
    return None, None
