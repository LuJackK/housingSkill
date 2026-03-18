"""Shared test fixtures for the housing_skill test suite."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from housing_skill.models.listing import Listing, ListingCriteria


def make_listing(
    id: str = "abc",
    title: str = "Nice apartment",
    url: str = "https://example.com/1",
    source: str = "test",
    price_eur: float | None = 700.0,
    size_m2: float | None = 55.0,
    location: str = "Ljubljana",
    rooms: float | None = 2.0,
    furnished: bool | None = True,
    description: str = "",
) -> Listing:
    return Listing(
        id=id,
        title=title,
        url=url,
        source=source,
        price_eur=price_eur,
        size_m2=size_m2,
        location=location,
        address=None,
        rooms=rooms,
        floor=None,
        furnished=furnished,
        description=description,
        scraped_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


@pytest.fixture()
def basic_listing():
    return make_listing()


@pytest.fixture()
def basic_criteria():
    return ListingCriteria(
        max_price_eur=1000,
        min_size_m2=30,
        locations=["Ljubljana"],
        max_results=10,
    )
