"""
Template engine.
Given a Lead object and email type, renders the correct template with all
placeholders substituted. Raises if any placeholder remains unfilled.
"""
import os
import re
import logging
from pathlib import Path

from models import Lead, EmailType

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def _load_template(email_type: EmailType) -> str:
    """Load raw template text for the given email type."""
    template_map = {
        EmailType.initial: "base_outreach.txt",
        EmailType.follow_up_1: "follow_up_1.txt",
        EmailType.follow_up_2: "follow_up_2.txt",
    }
    filename = template_map[email_type]
    path = TEMPLATES_DIR / filename
    return path.read_text(encoding="utf-8")


def render(lead: Lead, email_type: EmailType, thesis_industry: str | None = None) -> tuple[str, str]:
    """
    Render an email for the given lead and email type.

    Returns:
        (subject, body) — both as plain strings, ready to send.

    Raises:
        ValueError if any {{placeholder}} remains unfilled.
    """
    raw = _load_template(email_type)

    # Build thesis clause
    if thesis_industry:
        thesis_clause = f" and a brief one-page thesis on {thesis_industry}"
    else:
        thesis_clause = ""

    # Build substitution map
    substitutions = {
        "{{email}}": lead.email,
        "{{first_name}}": (lead.first_name or "").split()[0],  # just first name
        "{{relationship_hook}}": lead.relationship_hook or "fellow operator who has taken the search fund journey successfully",
        "{{focus_hook}}": lead.focus_hook or "lower middle market",
        "{{thesis_clause}}": thesis_clause,
    }

    rendered = raw
    for placeholder, value in substitutions.items():
        rendered = rendered.replace(placeholder, value)

    # Check for unfilled placeholders
    remaining = re.findall(r"\{\{[^}]+\}\}", rendered)
    if remaining:
        raise ValueError(f"Unfilled template placeholders: {remaining}")

    # Parse into subject and body
    lines = rendered.strip().split("\n")
    subject = ""
    body_start = 0

    for i, line in enumerate(lines):
        if line.startswith("SUBJECT:"):
            subject = line.replace("SUBJECT:", "").strip()
            body_start = i + 1
            break

    # Skip blank lines after subject header
    while body_start < len(lines) and not lines[body_start].strip():
        body_start += 1

    body = "\n".join(lines[body_start:]).strip()

    return subject, body


def preview(lead: Lead, email_type: EmailType, thesis_industry: str | None = None) -> str:
    """
    Return a formatted preview string for dry-run logging.
    """
    subject, body = render(lead, email_type, thesis_industry)
    return (
        f"\n{'='*60}\n"
        f"TO: {lead.email}\n"
        f"SUBJECT: {subject}\n"
        f"{'─'*60}\n"
        f"{body}\n"
        f"{'='*60}\n"
    )
