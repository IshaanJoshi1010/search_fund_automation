"""
APScheduler runner.
Registers all three jobs (discovery, send, followup, response poll)
and runs them as a persistent background process.
"""
import logging
import os
from pathlib import Path

import yaml
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def load_config() -> dict:
    cfg_path = Path(__file__).parent.parent / "config.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)


def start_scheduler():
    """Start the APScheduler with all cron jobs."""
    config = load_config()
    sched_cfg = config.get("scheduler", {})

    scheduler = BlockingScheduler(timezone="America/New_York")

    # Lazy imports to avoid circular imports at module load
    from scraper.orchestrator import run_discovery
    from classifier.lead_classifier import classify_all_unclassified
    from email_client.dispatcher import run_send_batch
    from email_client.response_poller import poll_for_replies
    from scheduler.followup_job import run_followup_job
    from database import get_session

    def discovery_and_classify():
        logger.info("⏰ Running discovery + classify job…")
        run_discovery()
        session = get_session()
        try:
            classify_all_unclassified(session)
        finally:
            session.close()

    def send_job():
        logger.info("⏰ Running send batch job…")
        run_send_batch()

    def followup_job():
        logger.info("⏰ Running follow-up job…")
        run_followup_job()

    def response_poll_job():
        logger.info("⏰ Running response poll job…")
        poll_for_replies()

    # Register jobs
    discovery_cron = sched_cfg.get("discovery_cron", "0 3 * * *")
    send_cron = sched_cfg.get("send_cron", "0 9 * * *")
    followup_cron = sched_cfg.get("followup_cron", "0 10 * * *")
    response_poll_cron = sched_cfg.get("response_poll_cron", "0 */4 * * *")

    scheduler.add_job(
        discovery_and_classify,
        CronTrigger.from_crontab(discovery_cron),
        id="discovery",
        name="Lead Discovery + Classify",
        replace_existing=True,
    )
    scheduler.add_job(
        send_job,
        CronTrigger.from_crontab(send_cron),
        id="send",
        name="Daily Send Batch",
        replace_existing=True,
    )
    scheduler.add_job(
        followup_job,
        CronTrigger.from_crontab(followup_cron),
        id="followup",
        name="Follow-up Checker",
        replace_existing=True,
    )
    scheduler.add_job(
        response_poll_job,
        CronTrigger.from_crontab(response_poll_cron),
        id="response_poll",
        name="Response Poller",
        replace_existing=True,
    )

    logger.info("✅ Scheduler started. Jobs registered:")
    for job in scheduler.get_jobs():
        logger.info(f"  [{job.id}] {job.name} — next run: {job.next_run_time}")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
