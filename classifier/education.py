"""
Education classifier.
Scans bio text for mentions of top schools to surface education hooks.
"""
import os
import re
import yaml
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def load_education_hooks() -> list[str]:
    cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    with open(cfg_path) as f:
        config = yaml.safe_load(f)
    return config.get("education_hooks", {}).get("ivy_and_top", [])


EDUCATION_HOOKS = load_education_hooks()


def extract_schools(text: str) -> list[str]:
    """Return a list of school names found in the text."""
    found = []
    for school in EDUCATION_HOOKS:
        if re.search(re.escape(school), text, re.IGNORECASE):
            found.append(school)
    return found


def derive_education_hook(schools: list[str]) -> Optional[str]:
    """
    Given a list of found schools, return a hook phrase if relevant.
    Example: "attended Wharton" / "a fellow Penn alum"
    """
    if not schools:
        return None

    school = schools[0]  # Use the first found school
    # Normalize common names
    if school in ("Penn", "University of Pennsylvania"):
        return "a Penn alum"
    if school == "Wharton":
        return "a Wharton alum"
    if school == "West Point":
        return "a West Point alum"
    return f"a {school} alum"
