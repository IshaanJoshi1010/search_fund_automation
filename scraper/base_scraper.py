"""
Base scraper: shared HTTP fetch + HTML parse utilities.
All scrapers inherit from BaseScraper.
"""
import time
import random
import logging
from abc import ABC, abstractmethod
from typing import Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


class BaseScraper(ABC):
    """Abstract base class with retry-enabled HTTP fetching."""

    def __init__(self, timeout: int = 20, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
        self.client = httpx.Client(
            headers=HEADERS,
            timeout=timeout,
            follow_redirects=True,
        )

    def fetch(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch a URL and return parsed BeautifulSoup, or None on failure."""
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.get(url)
                response.raise_for_status()
                return BeautifulSoup(response.text, "lxml")
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                logger.warning(f"HTTP {status} for {url} (attempt {attempt})")
                # Don't retry client errors (4xx) — page doesn't exist or access denied
                if status < 500:
                    return None
            except httpx.RequestError as e:
                logger.warning(f"Request error for {url}: {e} (attempt {attempt})")

            if attempt < self.max_retries:
                sleep_secs = 2 ** attempt + random.uniform(0, 1)
                logger.info(f"Retrying in {sleep_secs:.1f}s…")
                time.sleep(sleep_secs)

        logger.error(f"Failed to fetch {url} after {self.max_retries} attempts.")
        return None

    def polite_sleep(self, min_s: float = 2.0, max_s: float = 5.0):
        """Sleep a random amount to be polite to servers."""
        time.sleep(random.uniform(min_s, max_s))

    @abstractmethod
    def scrape(self) -> list[dict]:
        """
        Return a list of raw lead dicts with at minimum:
          { first_name, last_name, firm_name, website_url, source_url }
        """
        raise NotImplementedError

    def __del__(self):
        try:
            self.client.close()
        except Exception:
            pass
