"""Scraper for nepremicnine.net – the main Slovenian real-estate portal."""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Optional

from housing_skill.models.listing import Listing, ListingCriteria
from housing_skill.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://www.nepremicnine.net"
RENT_PATH = "/oglasi-oddaja/slovenija/stanovanje/"


class NepremicnineScraper(BaseScraper):
    """Scrapes rental listings from nepremicnine.net."""

    source_name = "nepremicnine.net"

    def _fetch_listings(self, criteria: ListingCriteria) -> list[Listing]:
        params = self._build_params(criteria)
        listings: list[Listing] = []

        page = 1
        while len(listings) < criteria.max_results * 3:  # fetch extra for filtering
            url = f"{BASE_URL}{RENT_PATH}"
            if page > 1:
                url = f"{BASE_URL}{RENT_PATH}{page}/"

            try:
                soup = self._get(url, params=params)
            except Exception as exc:
                logger.warning(
                    "nepremicnine.net: failed to fetch page %d: %s", page, exc
                )
                break

            page_listings = self._parse_page(soup)
            if not page_listings:
                break

            listings.extend(page_listings)

            # Check whether a next page exists
            if not soup.find("a", class_="next"):
                break
            page += 1

        return listings[: criteria.max_results * 3]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_params(criteria: ListingCriteria) -> dict:
        params: dict = {}
        if criteria.max_price_eur:
            params["cena_do"] = int(criteria.max_price_eur)
        if criteria.min_price_eur:
            params["cena_od"] = int(criteria.min_price_eur)
        if criteria.min_size_m2:
            params["velikost_od"] = int(criteria.min_size_m2)
        if criteria.max_size_m2:
            params["velikost_do"] = int(criteria.max_size_m2)
        if criteria.min_rooms:
            params["sobe_od"] = criteria.min_rooms
        if criteria.max_rooms:
            params["sobe_do"] = criteria.max_rooms
        return params

    def _parse_page(self, soup) -> list[Listing]:
        listings: list[Listing] = []
        for article in soup.select("article.property-wrapper"):
            try:
                listing = self._parse_article(article)
                if listing:
                    listings.append(listing)
            except Exception as exc:
                logger.debug("nepremicnine.net: error parsing article: %s", exc)
        return listings

    def _parse_article(self, article) -> Optional[Listing]:
        # Title and URL
        title_tag = article.select_one("h2.title a, .property-title a")
        if not title_tag:
            return None
        title = title_tag.get_text(strip=True)
        href = title_tag.get("href", "")
        url = href if href.startswith("http") else f"{BASE_URL}{href}"
        listing_id = hashlib.md5(url.encode()).hexdigest()[:12]

        # Price
        price_tag = article.select_one(".cena, .price, [class*='price']")
        price = self._parse_price(price_tag.get_text()) if price_tag else None

        # Size
        size_tag = article.select_one(".velikost, .size, [class*='size']")
        size = self._parse_size(size_tag.get_text()) if size_tag else None

        # Rooms
        rooms_tag = article.select_one(".sobe, .rooms, [class*='room']")
        rooms = self._parse_rooms(rooms_tag.get_text()) if rooms_tag else None

        # Location
        loc_tag = article.select_one(".lokacija, .location, [class*='location']")
        location = loc_tag.get_text(strip=True) if loc_tag else ""

        # Description snippet
        desc_tag = article.select_one(".opis, .description, p")
        description = desc_tag.get_text(strip=True) if desc_tag else ""

        # Images
        images = [
            img.get("src", img.get("data-src", ""))
            for img in article.select("img")
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
            furnished=self._detect_furnished(title + " " + description),
            description=description,
            images=images,
        )

    @staticmethod
    def _parse_rooms(text: str) -> Optional[float]:
        text = text.strip().lower()
        match = re.search(r"([\d]+[,.]?[\d]*)", text.replace(",", "."))
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
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
