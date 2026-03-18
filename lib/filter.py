"""Filter functions for housing listings."""

import re
from typing import List, Dict, Any, Tuple
from datetime import date


def filter_by_price(max_price_per_person: int, listings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter listings by maximum price per person.
    
    Args:
        max_price_per_person: Maximum acceptable price per person in EUR
        listings: List of standardized listing dicts
        
    Returns:
        Filtered list of listings within budget
    """
    filtered = []
    for listing in listings:
        price_per_person = listing.get('price_per_person')
        
        # If we can't determine price per person, include it for manual review
        if price_per_person is None:
            filtered.append(listing)
            continue
        
        if price_per_person <= max_price_per_person:
            filtered.append(listing)
    
    return filtered


def filter_by_location(location: str, max_km: float, listings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter listings by location and maximum distance.
    
    Args:
        location: Target location (e.g., "Koper-Center", "Koper-Semedella", "Koper-Other")
        max_km: Maximum distance in km (simplified - uses normalized location categories)
        listings: List of standardized listing dicts
        
    Returns:
        Filtered list of listings within acceptable location
    """
    filtered = []
    
    for listing in listings:
        loc_normalized = listing.get('location_normalized', 'Koper-Other')
        
        # If filtering for Center, accept Center only
        if location == "Koper-Center":
            if loc_normalized == "Koper-Center":
                filtered.append(listing)
        
        # If filtering for Semedella, accept Center and Semedella (within reasonable distance)
        elif location == "Koper-Semedella":
            if loc_normalized in ["Koper-Center", "Koper-Semedella"]:
                filtered.append(listing)
        
        # If filtering for Other or general Koper, accept all
        else:
            filtered.append(listing)
    
    return filtered


def filter_by_dates(ranges: List[Tuple[date, date]], listings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter listings by available date ranges.
    
    Note: This is a simplified implementation. Mojcimer doesn't always have explicit
    date info on listings, so this filter mainly passes through listings that might
    match, or filters based on available date information in description.
    
    Args:
        ranges: List of (from_date, to_date) tuples representing acceptable stay periods
        listings: List of standardized listing dicts
        
    Returns:
        Filtered list of listings that might be available in given date ranges
    """
    # For mojcimer.si, date filtering is often not possible from the listing alone
    # as availability dates are usually discussed with the landlord.
    # This filter primarily passes through listings for manual date verification.
    
    filtered = []
    
    for listing in listings:
        description = listing.get('description', '').lower()
        
        # If description mentions specific dates, try to match
        # This is a heuristic - most listings will pass through for manual review
        
        # Check if listing explicitly mentions "available from" or similar
        available_match = re.search(
            r'(available|available from|prosto od|na voljo od)\s*(\d{1,2})[./](\d{1,2})[./]?(\d{2,4})?',
            description
        )
        
        if available_match:
            # Parse the available date
            day = int(available_match.group(2))
            month = int(available_match.group(3))
            year_str = available_match.group(4)
            year = int(year_str) if year_str else date.today().year
            if year < 100:
                year += 2000
            
            try:
                available_from = date(year, month, day)
                
                # Check if available date overlaps with any requested range
                for range_start, range_end in ranges:
                    # If available before or at range end, it might work
                    if available_from <= range_end:
                        filtered.append(listing)
                        break
            except ValueError:
                # Invalid date, include for manual review
                filtered.append(listing)
        else:
            # No date info found, include for manual review
            filtered.append(listing)
    
    return filtered


def apply_all_filters(
    listings: List[Dict[str, Any]],
    max_price_per_person: int,
    location: str,
    max_km: float,
    date_ranges: List[Tuple[date, date]],
) -> List[Dict[str, Any]]:
    """
    Apply all filters in sequence.
    
    Args:
        listings: List of standardized listing dicts
        max_price_per_person: Maximum price per person
        location: Target location
        max_km: Maximum distance in km
        date_ranges: List of acceptable date ranges
        
    Returns:
        List of listings matching all criteria
    """
    result = listings
    
    # Apply location filter first (most restrictive)
    result = filter_by_location(location, max_km, result)
    
    # Apply price filter
    result = filter_by_price(max_price_per_person, result)
    
    # Apply date filter
    result = filter_by_dates(date_ranges, result)
    
    return result
