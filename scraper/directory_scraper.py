"""
Scraper for smash.vc/search-fund-investors/ and similar investor directory pages.
Finds links to individual searcher/fund pages and returns raw lead dicts.
"""
import logging
import re
from urllib.parse import urljoin, urlparse

from scraper.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class DirectoryScraper(BaseScraper):
    """
    Generic investor directory scraper.
    Given a directory URL, finds all links that look like individual
    searcher/fund profile pages.
    Works for: smash.vc, investor "portfolio" pages, "our entrepreneurs" pages.
    """

    def __init__(self, source_url: str, source_name: str = ""):
        super().__init__()
        self.source_url = source_url
        self.source_name = source_name
        self.base_domain = f"{urlparse(source_url).scheme}://{urlparse(source_url).netloc}"

    def scrape(self) -> list[dict]:
        """Return list of raw lead dicts with website_url and source info."""
        soup = self.fetch(self.source_url)
        if not soup:
            logger.error(f"Cannot scrape {self.source_url}")
            return []

        leads = []
        profile_links = self._find_profile_links(soup)

        logger.info(f"Found {len(profile_links)} profile links on {self.source_url}")

        for url in profile_links:
            self.polite_sleep(1.5, 4.0)
            profile_soup = self.fetch(url)
            if not profile_soup:
                continue

            lead = self._parse_profile(profile_soup, url)
            if lead:
                lead["source_url"] = self.source_url
                leads.append(lead)

        return leads

    def _find_profile_links(self, soup) -> list[str]:
        """
        Find links that look like individual searcher or fund profile pages.
        Strategy: look for external links (different domain) from the directory page,
        since directories typically link OUT to each searcher's own website.
        """
        domain = urlparse(self.source_url).netloc
        found_urls = []
        seen = set()

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()

            # Skip anchors, mailto, tel, javascript
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue

            # Make absolute
            abs_url = urljoin(self.source_url, href)
            parsed = urlparse(abs_url)

            # We want external links (searcher's own websites) OR
            # internal sub-pages that look like profiles
            if parsed.netloc and parsed.netloc != domain:
                # External link — likely a searcher's own site
                clean = abs_url.split("?")[0].rstrip("/")
                if clean not in seen and self._looks_like_business_site(clean):
                    seen.add(clean)
                    found_urls.append(clean)
            else:
                # Internal link — check if it looks like a profile path
                path = parsed.path.lower()
                if any(kw in path for kw in ["/searcher", "/entrepreneur", "/portfolio", "/fund", "/team"]):
                    clean = abs_url.split("?")[0].rstrip("/")
                    if clean not in seen:
                        seen.add(clean)
                        found_urls.append(clean)

        return found_urls

    @staticmethod
    def _looks_like_business_site(url: str) -> bool:
        """Filter out social/utility sites that aren't searcher websites."""
        skip_domains = [
            "linkedin.com", "twitter.com", "facebook.com", "instagram.com",
            "youtube.com", "maps.google", "apple.com", "microsoft.com",
            "stanford.edu", "smash.vc", "searchfunder.com", "google.com",
            "glassdoor.com", "crunchbase.com", "sec.gov",
        ]
        url_lower = url.lower()
        return not any(d in url_lower for d in skip_domains)

    def _parse_profile(self, soup, url: str) -> dict | None:
        """
        Extract name and firm from a profile page.
        Returns minimal lead dict; generic_profile.py enriches it with email/location.
        """
        title = soup.find("title")
        title_text = title.get_text(strip=True) if title else ""

        # Try to extract name from:
        # 1. h1 tag (most common for personal/firm sites)
        # 2. meta author
        # 3. OG title
        name = ""
        h1 = soup.find("h1")
        if h1:
            name = h1.get_text(strip=True)

        if not name:
            og_title = soup.find("meta", property="og:title")
            if og_title:
                name = og_title.get("content", "")

        if not name:
            name = title_text.split("|")[0].split("–")[0].strip()

        # Parse name into first/last
        parts = name.strip().split()
        first_name = parts[0] if parts else "Unknown"
        last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

        # Firm name: secondary heading or domain name
        firm_name = self._extract_firm_name(soup, url)

        return {
            "first_name": first_name,
            "last_name": last_name,
            "firm_name": firm_name,
            "website_url": url,
        }

    @staticmethod
    def _extract_firm_name(soup, url: str) -> str:
        """Try to extract the fund/firm name from a profile page."""
        # OG site name
        og_site = soup.find("meta", property="og:site_name")
        if og_site and og_site.get("content"):
            return og_site["content"].strip()

        # Schema.org Organization name
        org = soup.find("span", itemprop="name")
        if org:
            return org.get_text(strip=True)

        # Fall back to domain name, prettified
        domain = urlparse(url).netloc.replace("www.", "")
        return domain.split(".")[0].replace("-", " ").title()
