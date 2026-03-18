"""
Generic individual searcher profile scraper.
Visits a searcher's firm website and extracts:
  - email addresses
  - location (city/state)
  - sector keywords / bio text
  - education mentions
"""
import re
import logging
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from scraper.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Patterns likely to contain emails on a contact/team page
CONTACT_PAGE_SLUGS = [
    "/contact", "/contact-us", "/team", "/about", "/about-us",
    "/people", "/leadership", "/founders", "/us", "/reach-out",
]


class GenericProfileScraper(BaseScraper):
    """
    Visits an individual searcher's website URL and extracts structured data.
    Returns a dict that is then merged into the lead record.
    """

    def __init__(self, website_url: str):
        super().__init__()
        self.website_url = website_url.rstrip("/")

    def scrape(self) -> list[dict]:
        """Not used directly — use extract() instead."""
        return [self.extract()]

    def extract(self) -> dict:
        """
        Returns a dict with:
          email, city, state, bio_text, raw_text
        """
        result = {
            "email": None,
            "city": None,
            "state": None,
            "bio_text": "",
            "raw_text": "",
        }

        # 1. Try the homepage first
        soup = self.fetch(self.website_url)
        if soup:
            self._extract_from_soup(soup, result)

        # 2. If no email yet, try known contact sub-pages
        if not result["email"]:
            for slug in CONTACT_PAGE_SLUGS:
                contact_url = self.website_url + slug
                self.polite_sleep(1, 3)
                soup = self.fetch(contact_url)
                if soup:
                    self._extract_from_soup(soup, result)
                    if result["email"]:
                        break

        return result

    def _extract_from_soup(self, soup: BeautifulSoup, result: dict):
        """Mutate result dict in-place with extracted data."""
        full_text = soup.get_text(separator=" ", strip=True)

        # Append to raw_text for classification later
        result["raw_text"] += " " + full_text

        # ── Email extraction ──────────────────────────────────────────────────
        if not result["email"]:
            # 1. mailto links (most reliable)
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("mailto:"):
                    email = href.replace("mailto:", "").strip().split("?")[0]
                    if self._valid_email(email):
                        result["email"] = email
                        break

        if not result["email"]:
            # 2. Regex scan full page text
            matches = EMAIL_REGEX.findall(full_text)
            for m in matches:
                if self._valid_email(m):
                    result["email"] = m
                    break

        # ── Location extraction ───────────────────────────────────────────────
        if not result["city"]:
            self._extract_location(full_text, result)

        # ── Bio text ─────────────────────────────────────────────────────────
        # Grab paragraphs that look like bios (>40 chars)
        bio_parts = []
        for tag in soup.find_all(["p", "div", "span"]):
            text = tag.get_text(strip=True)
            if len(text) > 40 and not text.startswith("©") and not text.startswith("Cookie"):
                bio_parts.append(text)
        result["bio_text"] = " ".join(bio_parts[:8])  # top 8 blocks

    @staticmethod
    def _valid_email(email: str) -> bool:
        """Reject generic/role-based emails — only accept personal addresses."""
        skip_prefixes = [
            "info", "contact", "hello", "hi", "hey", "team", "admin",
            "support", "help", "news", "media", "press", "pr", "marketing",
            "sales", "office", "mail", "email", "inquiry", "inquiries",
            "noreply", "no-reply", "donotreply", "eta", "fund", "invest",
            "partners", "general", "careers", "jobs", "legal", "privacy",
        ]
        skip_patterns = [
            "example.com", "youremail", "test@", ".png", ".jpg", ".gif",
            "info@website",
        ]
        e = email.lower()
        local = e.split("@")[0]
        if not bool(EMAIL_REGEX.match(e)):
            return False
        if any(p in e for p in skip_patterns):
            return False
        if local in skip_prefixes:
            return False
        return True

    @staticmethod
    def _extract_location(text: str, result: dict):
        """
        Attempt to extract city/state from text via heuristics.
        Looks for patterns like "Based in Austin, TX" or "Boston, MA".
        """
        # Common US state abbreviations
        state_abbrevs = {
            "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID",
            "IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS",
            "MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK",
            "OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV",
            "WI","WY","DC",
        }

        # Pattern: "City, ST" or "City, State"
        city_state_re = re.compile(
            r'\b([A-Z][a-zA-Z\s\-]{2,25}),\s*([A-Z]{2})\b'
        )
        matches = city_state_re.findall(text)
        for city, state in matches:
            if state.upper() in state_abbrevs:
                result["city"] = city.strip()
                result["state"] = state.upper()
                return

        # Pattern: "based in <City>" / "located in <City>"
        based_re = re.compile(
            r'(?:based|located|headquartered|operating)\s+in\s+([A-Z][a-zA-Z\s]{2,30})',
            re.IGNORECASE
        )
        m = based_re.search(text)
        if m:
            result["city"] = m.group(1).strip().title()
