"""Parser for normalizing housing listing data."""

import re
from typing import Dict, Any, Optional, List


# Location normalization mapping
CENTER_KEYWORDS = ['center', 'centre', 'center mesta', 'središče']
SEMEDELLA_KEYWORDS = ['semedella', 'semedela', 'semedelo']


def normalize_location(location: str) -> str:
    """
    Normalize location to standard categories:
    - "Koper-Center"
    - "Koper-Semedella" 
    - "Koper-Other"
    """
    if not location:
        return "Koper-Other"
    
    location_lower = location.lower()
    
    # Check for Center
    for keyword in CENTER_KEYWORDS:
        if keyword in location_lower:
            return "Koper-Center"
    
    # Check for Semedella
    for keyword in SEMEDELLA_KEYWORDS:
        if keyword in location_lower:
            return "Koper-Semedella"
    
    # Default to Other
    return "Koper-Other"


def calculate_price_per_person(price: Optional[int], capacity: Optional[int]) -> Optional[int]:
    """
    Calculate price per person if total price and capacity are known.
    
    Args:
        price: Total price in EUR
        capacity: Number of beds/persons
        
    Returns:
        Price per person or None if cannot calculate
    """
    if price is None or capacity is None or capacity <= 0:
        return None
    return price // capacity


def parse_listing(raw_listing: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse and normalize a raw listing into standardized format.
    
    Args:
        raw_listing: Raw listing dict from scraper
        
    Returns:
        Standardized listing dict
    """
    # Extract raw values
    title = raw_listing.get('title', '').strip()
    location_raw = raw_listing.get('location', '') or raw_listing.get('address', '')
    address = raw_listing.get('address', location_raw).strip()
    price = raw_listing.get('price')
    capacity = raw_listing.get('capacity')
    contact_name = raw_listing.get('contact_name', '').strip()
    contact_phone = raw_listing.get('contact_phone', '').strip()
    description = raw_listing.get('description', '').strip()
    url = raw_listing.get('url', '')
    source = raw_listing.get('source', 'unknown')
    
    # Normalize location
    location_normalized = normalize_location(location_raw)
    
    # Calculate price per person
    price_per_person = calculate_price_per_person(price, capacity)
    
    # Extract room type from title/description
    room_type = extract_room_type(title, description)
    
    result = {
        "title": title,
        "location_raw": location_raw,
        "location_normalized": location_normalized,
        "address": address,
        "price_eur": price,
        "price_per_person": price_per_person,
        "capacity": capacity,
        "room_type": room_type,
        "contact_name": contact_name,
        "contact_phone": contact_phone,
        "description": description,
        "url": url,
        "source": source,
    }

    # Pass through optional fields from scraper if present
    for key in ['size_sqm', 'baths', 'amenities', 'images', 'images_local',
                'description_full', 'description_en', 'contact_email', 'price',
                'is_new']:
        if key in raw_listing and raw_listing[key] is not None:
            result[key] = raw_listing[key]

    return result


def extract_room_type(title: str, description: str) -> Optional[str]:
    """
    Extract room type from title and description.
    
    Returns one of: "soba", "garsonjera", "enosobno", "dvosobno", "trososbno", None
    """
    text = f"{title} {description}".lower()
    
    if 'garsonjera' in text:
        return "garsonjera"
    if 'trososbno' in text or 'trosed' in text:
        return "trososbno"
    if 'dvosobno' in text or 'dvosed' in text:
        return "dvosobno"
    if 'enosobno' in text or 'enosed' in text:
        return "enosobno"
    if 'soba' in text:
        return "soba"
    
    return None


def parse_listings(raw_listings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Parse a list of raw listings into standardized format.
    
    Args:
        raw_listings: List of raw listing dicts from scraper
        
    Returns:
        List of standardized listing dicts
    """
    parsed = []
    for raw in raw_listings:
        try:
            normalized = parse_listing(raw)
            parsed.append(normalized)
        except Exception as e:
            # Log error but continue processing other listings
            import sys
            print(f"Error parsing listing {raw.get('title', 'unknown')}: {e}", file=sys.stderr)
            continue
    
    return parsed
