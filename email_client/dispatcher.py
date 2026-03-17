"""
Email dispatcher.
Selects a daily batch of leads, renders emails, attaches PDFs, and sends via Gmail.
"""
import logging
import os
import random
import time
from datetime import datetime
from pathlib import Path

from database import get_session, init_db
from models import Lead, EmailLog, EmailType, ResponseStatus
from engine.template_engine import render, preview
from email_client.gmail_client import GmailClient
from attachments.manager import get_resume_path
from attachments.matcher import get_thesis_for_lead

logger = logging.getLogger(__name__)


def run_send_batch() -> int:
    """
    Select up to N leads/day, render emails, and send.
    Returns number of emails sent (or dry-run logged).
    """
    init_db()
    session = get_session()
    client = GmailClient()
    dry_run = os.getenv("SFAO_DRY_RUN", "true").lower() == "true"

    # Load config for daily cap + delay settings
    import yaml
    cfg_path = Path(__file__).parent.parent / "config.yaml"
    with open(cfg_path) as f:
        config = yaml.safe_load(f)

    daily_cap = int(config["email"]["daily_send_cap"])
    delay_min = int(config["email"]["delay_between_sends_min"])
    delay_max = int(config["email"]["delay_between_sends_max"])

    # Fetch new leads (not yet contacted)
    leads_to_contact = (
        session.query(Lead)
        .filter(
            Lead.response_status == ResponseStatus.new,
            Lead.last_contacted_at.is_(None),
        )
        .limit(daily_cap)
        .all()
    )

    if not leads_to_contact:
        logger.info("No new leads to contact today.")
        session.close()
        return 0

    logger.info(f"Sending to {len(leads_to_contact)} leads (dry_run={dry_run})")

    resume_path = get_resume_path()
    sent_count = 0

    for lead in leads_to_contact:
        try:
            thesis_path, thesis_industry = get_thesis_for_lead(lead, session)

            # Render template
            subject, body = render(lead, EmailType.initial, thesis_industry)

            # Build attachments list
            attachments = []
            if resume_path and resume_path.exists():
                attachments.append(resume_path)
            if thesis_path and thesis_path.exists():
                attachments.append(thesis_path)

            if dry_run:
                logger.info(preview(lead, EmailType.initial, thesis_industry))
            else:
                result = client.send_email(
                    to=lead.email,
                    subject=subject,
                    body=body,
                    attachments=attachments,
                )
                lead.gmail_thread_id = result.get("thread_id")

            # Update lead status
            lead.last_contacted_at = datetime.utcnow()
            lead.response_status = ResponseStatus.contacted

            # Log email
            log = EmailLog(
                lead_id=lead.id,
                email_type=EmailType.initial,
                subject=subject,
                body_snippet=body[:500],
                gmail_message_id=None if dry_run else result.get("message_id"),
                dry_run=dry_run,
            )
            session.add(log)
            session.commit()
            sent_count += 1

            # Polite delay between sends
            if not dry_run:
                sleep_time = random.uniform(delay_min, delay_max)
                logger.info(f"  Sleeping {sleep_time:.0f}s before next send…")
                time.sleep(sleep_time)

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to send to {lead.email}: {e}")
            continue

    session.close()
    logger.info(f"Send batch complete. {sent_count} emails {'logged (dry run)' if dry_run else 'sent'}.")
    return sent_count
