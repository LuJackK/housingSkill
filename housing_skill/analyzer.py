"""Listing analyzer – scores and ranks scraped listings against user criteria."""

from __future__ import annotations

import logging
from typing import Optional

from housing_skill.models.listing import Listing, ListingCriteria

logger = logging.getLogger(__name__)


class ListingAnalyzer:
    """Scores and ranks :class:`Listing` objects against :class:`ListingCriteria`.

    Scoring algorithm (each component is in [0, 1]):

    * **price_score**: cheaper → higher score.  Computed relative to the
      range of prices found in the dataset.
    * **size_score**: larger → higher score.  Computed relative to the
      range of sizes found in the dataset.
    * **location_score**: 1.0 if the listing's location matches one of the
      user's ``preferred_locations``, else 0.5 if it matches a hard-filter
      location, else 0.0.
    * **keyword_score**: fraction of user-supplied keywords present in the
      listing title + description.
    * **furnished_score**: 1.0 if furnished preference is satisfied or no
      preference is given, else 0.0.

    The final score is a weighted combination of the above components.
    """

    def analyze(
        self, listings: list[Listing], criteria: ListingCriteria
    ) -> list[Listing]:
        """Score each listing and return them sorted by score (descending).

        The *score* attribute of each listing is updated in-place.
        """
        if not listings:
            return []

        prices = [l.price_eur for l in listings if l.price_eur is not None]
        sizes = [l.size_m2 for l in listings if l.size_m2 is not None]

        min_price, max_price = (min(prices), max(prices)) if prices else (None, None)
        min_size, max_size = (min(sizes), max(sizes)) if sizes else (None, None)

        for listing in listings:
            listing.score = self._score_listing(
                listing, criteria, min_price, max_price, min_size, max_size
            )

        listings.sort(key=lambda l: l.score, reverse=True)
        return listings[: criteria.max_results]

    # ------------------------------------------------------------------

    @staticmethod
    def _score_listing(
        listing: Listing,
        criteria: ListingCriteria,
        min_price: Optional[float],
        max_price: Optional[float],
        min_size: Optional[float],
        max_size: Optional[float],
    ) -> float:
        components: list[float] = []
        weights: list[float] = []

        # --- Price score (lower price → higher score) -----------------
        if listing.price_eur is not None and min_price is not None and max_price is not None:
            price_range = max_price - min_price
            if price_range > 0:
                price_score = 1.0 - (listing.price_eur - min_price) / price_range
            else:
                price_score = 1.0
            components.append(price_score)
            weights.append(criteria.price_weight)

        # --- Size score (larger → higher score) -----------------------
        if listing.size_m2 is not None and min_size is not None and max_size is not None:
            size_range = max_size - min_size
            if size_range > 0:
                size_score = (listing.size_m2 - min_size) / size_range
            else:
                size_score = 1.0
            components.append(size_score)
            weights.append(criteria.size_weight)

        # --- Location score -------------------------------------------
        loc_lower = listing.location.lower()
        if criteria.preferred_locations and any(
            p.lower() in loc_lower for p in criteria.preferred_locations
        ):
            loc_score = 1.0
        elif criteria.locations and any(
            l.lower() in loc_lower for l in criteria.locations
        ):
            loc_score = 0.5
        else:
            loc_score = 0.25
        components.append(loc_score)
        weights.append(0.3)

        # --- Keyword score --------------------------------------------
        if criteria.keywords:
            combined = (listing.title + " " + listing.description).lower()
            matched = sum(1 for kw in criteria.keywords if kw.lower() in combined)
            kw_score = matched / len(criteria.keywords)
            components.append(kw_score)
            weights.append(0.2)

        # --- Furnished score -----------------------------------------
        if criteria.furnished is not None and listing.furnished is not None:
            fur_score = 1.0 if listing.furnished == criteria.furnished else 0.0
            components.append(fur_score)
            weights.append(0.1)

        if not components:
            return 0.0

        total_weight = sum(weights)
        if total_weight == 0:
            return 0.0

        return round(
            sum(c * w for c, w in zip(components, weights)) / total_weight, 4
        )
