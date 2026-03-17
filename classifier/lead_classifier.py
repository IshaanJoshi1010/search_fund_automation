"""
Lead classifier orchestrator.
Given a Lead record (with bio text, city, state already populated),
runs all sub-classifiers and updates the lead in the database.
"""
import logging
from sqlalchemy.orm import Session

from classifier.sector import classify_sectors, derive_focus_hook
from classifier.geography import derive_relationship_hook
from classifier.education import extract_schools
from models import Lead

logger = logging.getLogger(__name__)


def classify_lead(lead: Lead, session: Session) -> Lead:
    """
    Run all classifiers on a Lead record, mutate it, and persist.
    Returns the updated lead.
    """
    text = (lead.prior_experience or "") + " " + (lead.firm_name or "")

    # 1. Base rule-based classification
    sector_tags = classify_sectors(text)
    lead.sector_focus = sector_tags
    fallback_foc = derive_focus_hook(sector_tags)
    fallback_rel = derive_relationship_hook(lead.city, lead.state)
    
    lead.education = extract_schools(text)

    # 2. Gemini AI Personalization
    from classifier.ai_personalizer import generate_hooks
    rel_hook, foc_hook = generate_hooks(
        first_name=lead.first_name,
        city=lead.city or "",
        state=lead.state or "",
        bio_text=text,
        fallback_rel_hook=fallback_rel,
        fallback_focus_hook=fallback_foc
    )

    lead.relationship_hook = rel_hook
    lead.focus_hook = foc_hook

    try:
        session.add(lead)
        session.commit()
        logger.info(
            f"Classified lead {lead.email}: "
            f"sectors={sector_tags}, geo_hook='{lead.relationship_hook}'"
        )
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to persist classification for {lead.email}: {e}")

    return lead


def classify_all_unclassified(session: Session) -> int:
    """
    Classify all leads that haven't been classified yet (no relationship_hook set).
    Returns count of leads classified.
    """
    unclassified = session.query(Lead).filter(Lead.relationship_hook.is_(None)).all()
    count = 0
    for lead in unclassified:
        classify_lead(lead, session)
        count += 1
    logger.info(f"Classified {count} previously unclassified leads.")
    return count
