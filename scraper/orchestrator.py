"""
Scraper orchestrator.
Reads source_urls from config.yaml, runs the appropriate scraper for each,
enriches with GenericProfileScraper, and upserts into the leads DB.
"""
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scraper.directory_scraper import DirectoryScraper
from scraper.generic_profile import GenericProfileScraper
from database import get_session, init_db
from models import Lead, ResponseStatus
import yaml

logger = logging.getLogger(__name__)


def load_config() -> dict:
    cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    with open(cfg_path) as f:
        return yaml.safe_load(f)


def run_discovery() -> int:
    """
    Main entry point for the discovery job.
    Returns number of NEW leads added.
    """
    init_db()
    config = load_config()
    source_urls = config.get("source_urls", [])
    new_count = 0

    for source in source_urls:
        url = source["url"]
        name = source.get("name", url)
        logger.info(f"Scraping source: {name}")

        scraper = DirectoryScraper(source_url=url, source_name=name)
        raw_leads = scraper.scrape()

        logger.info(f"  → Found {len(raw_leads)} candidate leads from {name}")

        for raw in raw_leads:
            website_url = raw.get("website_url", "")
            if not website_url:
                continue

            # Enrich via generic profile scraper
            profile_scraper = GenericProfileScraper(website_url)
            try:
                profile_data = profile_scraper.extract()
            except Exception as e:
                logger.warning(f"  Profile scrape failed for {website_url}: {e}")
                profile_data = {}

            email = profile_data.get("email")
            if not email:
                logger.info(f"  Skipping {website_url} — no email found.")
                continue

            session = get_session()
            try:
                # Check for existing lead by email
                existing = session.query(Lead).filter_by(email=email).first()
                if existing:
                    logger.info(f"  Already have lead: {email}")
                    continue

                lead = Lead(
                    first_name=raw.get("first_name", "Unknown"),
                    last_name=raw.get("last_name", ""),
                    firm_name=raw.get("firm_name", ""),
                    email=email,
                    website_url=website_url,
                    city=profile_data.get("city"),
                    state=profile_data.get("state"),
                    prior_experience=profile_data.get("bio_text", ""),
                    source_url=raw.get("source_url", url),
                    response_status=ResponseStatus.new,
                )
                session.add(lead)
                session.commit()
                new_count += 1
                logger.info(f"  ✓ Added lead: {lead.first_name} {lead.last_name} <{email}>")

            except Exception as e:
                session.rollback()
                logger.error(f"  DB error for {email}: {e}")
            finally:
                session.close()

    logger.info(f"Discovery complete. {new_count} new leads added.")
    return new_count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_discovery()
