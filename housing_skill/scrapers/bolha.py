"""Scraper for bolha.com – Slovenian classifieds with a real-estate section."""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Optional

from housing_skill.models.listing import Listing, ListingCriteria
from housing_skill.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://www.bolha.com"
RENT_PATH = "/oddaja-nepremicnin"


class BolhaScraper(BaseScraper):
    """Scrapes rental listings from bolha.com."""

    source_name = "bolha.com"

    def _fetch_listings(self, criteria: ListingCriteria) -> list[Listing]:
        listings: list[Listing] = []

        page = 1
        while len(listings) < criteria.max_results * 3:
            params = self._build_params(criteria, page)
            try:
                soup = self._get(f"{BASE_URL}{RENT_PATH}", params=params)
            except Exception as exc:
                logger.warning("bolha.com: failed to fetch page %d: %s", page, exc)
                break

            page_listings = self._parse_page(soup)
            if not page_listings:
                break

            listings.extend(page_listings)

            next_page = soup.select_one("a.next-page, .pagination .next a")
            if not next_page:
                break
            page += 1

        return listings[: criteria.max_results * 3]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_params(criteria: ListingCriteria, page: int = 1) -> dict:
        params: dict = {"page": page}
        if criteria.max_price_eur:
            params["price_to"] = int(criteria.max_price_eur)
        if criteria.min_price_eur:
            params["price_from"] = int(criteria.min_price_eur)
        if criteria.locations:
            params["city"] = criteria.locations[0]
        return params

    def _parse_page(self, soup) -> list[Listing]:
        listings: list[Listing] = []
        for article in soup.select("article.entity-body, ul.EntityList li.EntityList-item article"):
            try:
                listing = self._parse_article(article)
                if listing:
                    listings.append(listing)
            except Exception as exc:
                logger.debug("bolha.com: error parsing article: %s", exc)
        return listings

    def _parse_article(self, article) -> Optional[Listing]:
        # Title and URL
        title_tag = article.select_one("h3.entity-title a, h3 a")
        if not title_tag:
            return None
        title = title_tag.get_text(strip=True)
        href = title_tag.get("href", "")
        url = href if href.startswith("http") else f"{BASE_URL}{href}"
        listing_id = hashlib.md5(url.encode()).hexdigest()[:12]

        # Price
        price_tag = article.select_one(".price-box strong, .price-label")
        price = self._parse_price(price_tag.get_text()) if price_tag else None

        # Description
        desc_tag = article.select_one(".price-box + p, .entity-description-body")
        description = desc_tag.get_text(strip=True) if desc_tag else ""

        # Try to extract size and rooms from description/title
        combined = title + " " + description
        size = self._extract_size_from_text(combined)
        rooms = self._extract_rooms_from_text(combined)

        # Location
        loc_tag = article.select_one(".entity-description-title small, .city-name")
        location = loc_tag.get_text(strip=True) if loc_tag else ""

        # Images
        images = [
            img.get("src", img.get("data-src", ""))
            for img in article.select("img.entity-image")
            if img.get("src") or img.get("data-src")
        ]

        return Listing(
            id=listing_id,
            title=title,
            url=url,
            source=self.source_name,
            price_eur=price,
            size_m2=size,
            location=location,
            address=None,
            rooms=rooms,
            floor=None,
            furnished=self._detect_furnished(combined),
            description=description,
            images=images,
        )

    @staticmethod
    def _extract_size_from_text(text: str) -> Optional[float]:
        match = re.search(r"([\d]+[,.]?[\d]*)\s*m[²2]", text.replace(",", "."))
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None

    @staticmethod
    def _extract_rooms_from_text(text: str) -> Optional[float]:
        patterns = [
            r"([\d]+[,.]?\d*)\s*sobe",  # Slovenian: "2 sobe"
            r"([\d]+[,.]?\d*)\s*sob",
            r"([\d]+[,.]?\d*)\s*room",
        ]
        for pattern in patterns:
            match = re.search(pattern, text.lower().replace(",", "."))
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    pass
        return None

    @staticmethod
    def _detect_furnished(text: str) -> Optional[bool]:
        text_lower = text.lower()
        # Check for unfurnished first so that "neopremljeno" (which contains
        # "opremljeno") is matched correctly before the furnished keywords.
        if any(w in text_lower for w in ("neopremljeno", "unfurnished", "prazno")):
            return False
        if any(w in text_lower for w in ("opremljeno", "furnished", "pohištvo")):
            return True
        return None
