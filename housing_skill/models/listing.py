"""Data models for housing listings and search criteria."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Listing:
    """Represents a single rental listing scraped from a real-estate website."""

    id: str
    title: str
    url: str
    source: str
    price_eur: Optional[float]
    size_m2: Optional[float]
    location: str
    address: Optional[str]
    rooms: Optional[float]
    floor: Optional[int]
    furnished: Optional[bool]
    description: str
    images: list[str] = field(default_factory=list)
    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    score: float = 0.0

    # Derived fields (calculated after construction if not supplied)
    price_per_m2: Optional[float] = None

    def __post_init__(self) -> None:
        if self.price_eur and self.size_m2 and self.size_m2 > 0:
            self.price_per_m2 = round(self.price_eur / self.size_m2, 2)

    def to_dict(self) -> dict:
        """Serialise listing to a plain dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "price_eur": self.price_eur,
            "size_m2": self.size_m2,
            "price_per_m2": self.price_per_m2,
            "location": self.location,
            "address": self.address,
            "rooms": self.rooms,
            "floor": self.floor,
            "furnished": self.furnished,
            "description": self.description,
            "images": self.images,
            "scraped_at": self.scraped_at.isoformat(),
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Listing":
        """Deserialise a listing from a plain dictionary."""
        scraped_at = data.get("scraped_at")
        if isinstance(scraped_at, str):
            scraped_at = datetime.fromisoformat(scraped_at)
        return cls(
            id=data["id"],
            title=data["title"],
            url=data["url"],
            source=data["source"],
            price_eur=data.get("price_eur"),
            size_m2=data.get("size_m2"),
            location=data.get("location", ""),
            address=data.get("address"),
            rooms=data.get("rooms"),
            floor=data.get("floor"),
            furnished=data.get("furnished"),
            description=data.get("description", ""),
            images=data.get("images", []),
            scraped_at=scraped_at or datetime.now(timezone.utc),
            score=data.get("score", 0.0),
        )


@dataclass
class ListingCriteria:
    """Search and ranking criteria supplied by the user / AI agent."""

    # Hard filters (listings that fail these are excluded entirely)
    max_price_eur: Optional[float] = None
    min_price_eur: Optional[float] = None
    min_size_m2: Optional[float] = None
    max_size_m2: Optional[float] = None
    min_rooms: Optional[float] = None
    max_rooms: Optional[float] = None
    locations: list[str] = field(default_factory=list)
    furnished: Optional[bool] = None

    # Soft preferences (affect score but don't exclude)
    preferred_locations: list[str] = field(default_factory=list)
    # Weight 0-1 for how much to favour cheaper listings (vs. larger)
    price_weight: float = 0.5
    # Weight 0-1 for how much to favour larger listings
    size_weight: float = 0.5
    keywords: list[str] = field(default_factory=list)
    max_results: int = 20

    def to_dict(self) -> dict:
        return {
            "max_price_eur": self.max_price_eur,
            "min_price_eur": self.min_price_eur,
            "min_size_m2": self.min_size_m2,
            "max_size_m2": self.max_size_m2,
            "min_rooms": self.min_rooms,
            "max_rooms": self.max_rooms,
            "locations": self.locations,
            "furnished": self.furnished,
            "preferred_locations": self.preferred_locations,
            "price_weight": self.price_weight,
            "size_weight": self.size_weight,
            "keywords": self.keywords,
            "max_results": self.max_results,
        }
