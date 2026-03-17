"""
Follow-up scheduler job.
Checks all 'contacted' leads and sends follow-up 1 or 2 based on elapsed days.
"""
import logging
import os
import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from database import get_session, init_db
from email_client.gmail_client import GmailClient
from engine.template_engine import render, preview
from models import EmailLog, EmailType, Lead, ResponseStatus
from attachments.manager import get_resume_path
from attachments.matcher import get_thesis_for_lead

logger = logging.getLogger(__name__)


def run_followup_job() -> int:
    """
    Check leads that need follow-ups and send them.
    Returns total follow-ups sent/logged.
    """
    init_db()
    session = get_session()
    client = GmailClient()
    dry_run = os.getenv("SFAO_DRY_RUN", "true").lower() == "true"

    cfg_path = Path(__file__).parent.parent / "config.yaml"
    with open(cfg_path) as f:
        config = yaml.safe_load(f)

    followup_1_days = int(config["followup"]["followup_1_days"])
    followup_2_days = int(config["followup"]["followup_2_days"])
    delay_min = int(config["email"]["delay_between_sends_min"])
    delay_max = int(config["email"]["delay_between_sends_max"])

    now = datetime.utcnow()
    sent_count = 0

    # Get all contacted leads that haven't replied
    candidates = (
        session.query(Lead)
        .filter(Lead.response_status == ResponseStatus.contacted)
        .all()
    )

    for lead in candidates:
        if not lead.last_contacted_at:
            continue

        days_elapsed = (now - lead.last_contacted_at).days

        # Determine which follow-up to send
        if lead.follow_up_count == 0 and days_elapsed >= followup_1_days:
            email_type = EmailType.follow_up_1
        elif lead.follow_up_count == 1 and days_elapsed >= followup_2_days:
            email_type = EmailType.follow_up_2
        else:
            continue  # Not time yet

        try:
            thesis_path, thesis_industry = get_thesis_for_lead(lead, session)
            subject, body = render(lead, email_type, thesis_industry)

            attachments = []
            if email_type == EmailType.follow_up_1:
                # Re-attach resume for first follow-up
                resume = get_resume_path()
                if resume and resume.exists():
                    attachments.append(resume)

            if dry_run:
                logger.info(preview(lead, email_type, thesis_industry))
                result = {"message_id": "DRY_RUN", "thread_id": lead.gmail_thread_id}
            else:
                result = client.send_email(
                    to=lead.email,
                    subject=subject,
                    body=body,
                    attachments=attachments,
                    thread_id=lead.gmail_thread_id,  # reply in-thread
                )

            # Update lead
            lead.follow_up_count += 1
            lead.last_contacted_at = now

            if lead.follow_up_count >= 2:
                lead.response_status = ResponseStatus.closed_no_response
                logger.info(f"  Closed (no response): {lead.email}")

            # Log
            log = EmailLog(
                lead_id=lead.id,
                email_type=email_type,
                subject=subject,
                body_snippet=body[:500],
                gmail_message_id=result.get("message_id"),
                dry_run=dry_run,
            )
            session.add(log)
            session.commit()
            sent_count += 1
            logger.info(
                f"  {'[DRY RUN] ' if dry_run else ''}"
                f"Follow-up {lead.follow_up_count} sent to {lead.email}"
            )

            if not dry_run:
                time.sleep(random.uniform(delay_min, delay_max))

        except Exception as e:
            session.rollback()
            logger.error(f"Follow-up failed for {lead.email}: {e}")

    session.close()
    logger.info(f"Follow-up job complete. {sent_count} follow-ups sent.")
    return sent_count
