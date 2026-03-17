"""
Response poller.
Polls Gmail inbox for replies on tracked thread IDs.
Marks lead status as 'replied' when a response is detected.
Optionally applies a Gmail label for easy filtering.
"""
import logging
import os
from datetime import datetime

from googleapiclient.errors import HttpError

from database import get_session
from models import Lead, ResponseStatus
from email_client.gmail_client import GmailClient

logger = logging.getLogger(__name__)

LABEL_NAME = "SFAO - Hot"


def poll_for_replies() -> int:
    """
    Check all 'contacted' leads for replies in their Gmail threads.
    Returns number of new replies found.
    """
    session = get_session()
    client = GmailClient()

    dry_run = os.getenv("SFAO_DRY_RUN", "true").lower() == "true"
    if dry_run:
        logger.info("[DRY RUN] Skipping response poll.")
        session.close()
        return 0

    contacted_leads = (
        session.query(Lead)
        .filter(
            Lead.response_status == ResponseStatus.contacted,
            Lead.gmail_thread_id.isnot(None),
        )
        .all()
    )

    replies_found = 0

    sender_email = os.getenv("SENDER_EMAIL", "").lower()

    for lead in contacted_leads:
        try:
            messages = client.get_thread_replies(lead.gmail_thread_id)
            # Check if any message in the thread is FROM someone other than the sender
            reply_detected = False
            for msg in messages:
                headers = msg.get("payload", {}).get("headers", [])
                from_header = next((h["value"] for h in headers if h["name"].lower() == "from"), "")
                if sender_email and sender_email not in from_header.lower():
                    reply_detected = True
                    break
                elif not sender_email and len(messages) > 1:
                    # Fallback: no sender email configured, use count heuristic
                    reply_detected = True
                    break

            if reply_detected:
                lead.response_status = ResponseStatus.replied
                session.commit()
                logger.info(f"🎉 Reply detected from {lead.email} ({lead.first_name} {lead.last_name})")
                replies_found += 1

                # Try to apply Gmail label
                try:
                    _apply_label(client, lead.gmail_thread_id)
                except Exception as e:
                    logger.warning(f"Could not apply Gmail label: {e}")

        except Exception as e:
            session.rollback()
            logger.error(f"Error polling thread for {lead.email}: {e}")

    session.close()
    logger.info(f"Response poll complete. {replies_found} new replies detected.")
    return replies_found


def _apply_label(client: GmailClient, thread_id: str):
    """Apply the 'SFAO - Hot' label to a thread in Gmail."""
    try:
        service = client.service

        # List existing labels to find or create ours
        labels_result = service.users().labels().list(userId="me").execute()
        existing_labels = labels_result.get("labels", [])

        label_id = None
        for label in existing_labels:
            if label["name"] == LABEL_NAME:
                label_id = label["id"]
                break

        if not label_id:
            # Create the label
            label = service.users().labels().create(
                userId="me",
                body={"name": LABEL_NAME, "labelListVisibility": "labelShow", "messageListVisibility": "show"},
            ).execute()
            label_id = label["id"]

        # Apply label to thread
        service.users().threads().modify(
            userId="me",
            id=thread_id,
            body={"addLabelIds": [label_id]},
        ).execute()
        logger.info(f"  Applied label '{LABEL_NAME}' to thread {thread_id}")

    except HttpError as e:
        logger.warning(f"Gmail label error: {e}")
