"""Configuration for housing scraper."""

from datetime import date
from typing import List, Tuple

# Hardcoded filters from criteria.md
MAX_PRICE_PER_PERSON: int = 300
TARGET_LOCATION: str = "Koper"
MAX_DISTANCE_FROM_CENTER_KM: float = 3.0

# Date ranges as list of (from, to) tuples
# - July 1 - September 30, 2026
# - October 1, 2026 - June 30, 2027
DATE_RANGES: List[Tuple[date, date]] = [
    (date(2026, 7, 1), date(2026, 9, 30)),
    (date(2026, 10, 1), date(2027, 6, 30)),
]

# Mojcimer URLs
MOJCIMER_BASE_URL: str = "https://www.mojcimer.si"
MOJCIMER_LISTINGS_URL: str = f"{MOJCIMER_BASE_URL}/seznam-prostih-sob"

# Category slugs to fetch
CATEGORY_SLUGS: List[str] = [
    "soba",
    "garsonjera", 
    "enosobno-stanovanje",
    "dvosobno-stanovanje",
]

# Request headers
REQUEST_HEADERS: dict = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Timeout for requests
REQUEST_TIMEOUT: int = 30
