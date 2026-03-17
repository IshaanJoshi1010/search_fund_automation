#!/usr/bin/env python3
"""
SFAO — SearchFund Auto-Outreach
Main CLI entry point.

Usage:
  python main.py scheduler          # Start the full background scheduler
  python main.py dashboard          # Start admin UI at http://localhost:5050
  python main.py run-discovery      # Run scrape + classify one-shot
  python main.py run-send           # Run today's email send batch
  python main.py run-followups      # Run follow-up checker
  python main.py run-poll           # Poll Gmail for replies now
  python main.py auth-gmail         # One-time Gmail OAuth flow
  python main.py db-init            # Initialize database
"""

import logging
import sys
import os

from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("sfao.log", mode="a"),
    ],
)
logger = logging.getLogger("sfao.main")


def cmd_scheduler():
    """Start the APScheduler background daemon."""
    logger.info("Starting SFAO Scheduler…")
    from scheduler.runner import start_scheduler
    start_scheduler()


def cmd_dashboard():
    """Launch the Flask admin dashboard."""
    logger.info("Starting SFAO Dashboard at http://127.0.0.1:5050")
    from dashboard.app import create_app
    app = create_app()
    app.run(host="127.0.0.1", port=5050, debug=False)


def cmd_run_discovery():
    """One-shot: discover + classify leads."""
    logger.info("Running discovery + classify…")
    from scraper.orchestrator import run_discovery
    from classifier.lead_classifier import classify_all_unclassified
    from database import get_session, init_db

    init_db()
    count = run_discovery()
    logger.info(f"New leads discovered: {count}")

    session = get_session()
    try:
        classified = classify_all_unclassified(session)
        logger.info(f"Leads classified: {classified}")
    finally:
        session.close()


def cmd_run_send():
    """One-shot: send today's email batch."""
    dry = os.getenv("SFAO_DRY_RUN", "true").lower() == "true"
    mode = "DRY RUN" if dry else "LIVE"
    logger.info(f"Running send batch [{mode}]…")
    from email_client.dispatcher import run_send_batch
    count = run_send_batch()
    logger.info(f"Emails sent: {count}")


def cmd_run_followups():
    """One-shot: check and send follow-ups."""
    dry = os.getenv("SFAO_DRY_RUN", "true").lower() == "true"
    mode = "DRY RUN" if dry else "LIVE"
    logger.info(f"Running follow-up job [{mode}]…")
    from scheduler.followup_job import run_followup_job
    count = run_followup_job()
    logger.info(f"Follow-ups sent: {count}")


def cmd_run_poll():
    """One-shot: poll Gmail for replies."""
    dry = os.getenv("SFAO_DRY_RUN", "true").lower() == "true"
    if dry:
        logger.info("[DRY RUN] Skipping response poll.")
        return
    logger.info("Polling Gmail for replies…")
    from email_client.response_poller import poll_for_replies
    count = poll_for_replies()
    logger.info(f"Replies detected: {count}")


def cmd_auth_gmail():
    """One-time Gmail OAuth flow — opens browser."""
    logger.info("Running Gmail OAuth flow…")
    from email_client.gmail_client import GmailClient
    client = GmailClient()
    client.run_oauth_flow()
    logger.info("✓ Gmail authenticated successfully.")


def cmd_db_init():
    """Initialize the database and create tables."""
    from database import init_db
    init_db()
    logger.info("✓ Database initialized (sfao.db)")


COMMANDS = {
    "scheduler": cmd_scheduler,
    "dashboard": cmd_dashboard,
    "run-discovery": cmd_run_discovery,
    "run-send": cmd_run_send,
    "run-followups": cmd_run_followups,
    "run-poll": cmd_run_poll,
    "auth-gmail": cmd_auth_gmail,
    "db-init": cmd_db_init,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        print(f"Available commands: {', '.join(COMMANDS.keys())}")
        sys.exit(1)

    command = sys.argv[1]
    COMMANDS[command]()


if __name__ == "__main__":
    main()
