"""
Sector classifier.
Maps scraped bio/site text to sector tags using keyword matching from config.yaml.
"""
import os
import yaml
import logging

logger = logging.getLogger(__name__)


def load_sector_keywords() -> dict[str, list[str]]:
    cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    with open(cfg_path) as f:
        config = yaml.safe_load(f)
    return config.get("sector_keywords", {})


SECTOR_KEYWORDS = load_sector_keywords()

# Human-readable focus hook for each sector tag
FOCUS_HOOK_MAP = {
    "software": "software and vertical SaaS space",
    "tech_enabled_services": "tech-enabled services space",
    "healthcare": "healthcare services space",
    "government_services": "government services sector",
    "industrials": "industrial and distribution space",
    "lower_middle_market": "lower middle market",
    "consumer": "consumer and retail space",
}


def classify_sectors(text: str) -> list[str]:
    """
    Given a blob of text (bio, website copy), return a list of matched sector tags.
    """
    text_lower = text.lower()
    matched = []
    for sector, keywords in SECTOR_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                if sector not in matched:
                    matched.append(sector)
                break
    return matched


def derive_focus_hook(sector_tags: list[str]) -> str:
    """
    From a list of sector tags, derive the human-readable focus_hook for the email template.
    Uses the first (most specific) matched sector.
    """
    for tag in sector_tags:
        if tag in FOCUS_HOOK_MAP:
            return FOCUS_HOOK_MAP[tag]
    return "lower middle market"  # default fallback
