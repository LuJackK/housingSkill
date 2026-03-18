"""Mojcimer.si scraper using curl and regex."""

import re
import subprocess
import json
import time
from typing import List, Dict, Any, Optional

MOJCIMER_BASE_URL = "https://www.mojcimer.si"
MOJCIMER_LISTINGS_URL = f"{MOJCIMER_BASE_URL}/seznam-prostih-sob"
CATEGORY_SLUGS = ["soba", "garsonjera", "enosobno-stanovanje", "dvosobno-stanovanje", "trisobno-stanovanje"]
MAX_PAGES_PER_CATEGORY = 10  # Safety limit


def fetch_page(url: str) -> str:
    """Fetch page using curl."""
    try:
        result = subprocess.run(
            ["curl", "-s", "-L", "-A", "Mozilla/5.0", url],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=__import__('sys').stderr)
        return ""


def get_max_page(html: str) -> int:
    """Extract the highest page number from pagination links."""
    pages = re.findall(r'\?page=(\d+)', html)
    if pages:
        return max(int(p) for p in pages)
    return 1


def scrape_all_listings(scrape_details: bool = True) -> List[Dict[str, Any]]:
    """Scrape ALL listings from mojcimer.si with pagination support."""
    all_listings = []
    seen_urls = set()

    # Scrape main listing page with pagination
    print(f"Fetching: {MOJCIMER_LISTINGS_URL}", file=__import__('sys').stderr)
    first_page = fetch_page(MOJCIMER_LISTINGS_URL)
    max_page = get_max_page(first_page)
    print(f"  Pages: {max_page}", file=__import__('sys').stderr)

    # Parse first page
    listings = parse_listings(first_page)
    for listing in listings:
        if listing['url'] not in seen_urls:
            seen_urls.add(listing['url'])
            all_listings.append(listing)
    print(f"  Page 1: {len(listings)} listings", file=__import__('sys').stderr)

    # Fetch remaining pages
    for page in range(2, max_page + 1):
        url = f"{MOJCIMER_LISTINGS_URL}?page={page}"
        print(f"  Page {page}...", file=__import__('sys').stderr)
        html = fetch_page(url)
        if html:
            listings = parse_listings(html)
            new = 0
            for listing in listings:
                if listing['url'] not in seen_urls:
                    seen_urls.add(listing['url'])
                    all_listings.append(listing)
                    new += 1
            print(f"    {len(listings)} found, {new} new", file=__import__('sys').stderr)
            if new == 0:
                break  # No more new listings
        time.sleep(0.3)  # Be polite

    # Also scrape category pages for any we missed
    for cat in CATEGORY_SLUGS:
        cat_url = f"{MOJCIMER_LISTINGS_URL}?category={cat}"
        print(f"\nCategory: {cat}", file=__import__('sys').stderr)

        first_html = fetch_page(cat_url)
        if not first_html:
            continue

        cat_listings = parse_listings(first_html)
        new = sum(1 for l in cat_listings if l['url'] not in seen_urls)
        for listing in cat_listings:
            if listing['url'] not in seen_urls:
                seen_urls.add(listing['url'])
                all_listings.append(listing)
        print(f"  Page 1: {len(cat_listings)} found, {new} new", file=__import__('sys').stderr)

        # Paginate within category
        cat_max_page = get_max_page(first_html)
        for page in range(2, min(cat_max_page, MAX_PAGES_PER_CATEGORY) + 1):
            url = f"{cat_url}&page={page}"
            html = fetch_page(url)
            if not html:
                break
            listings = parse_listings(html)
            new = sum(1 for l in listings if l['url'] not in seen_urls)
            if new == 0:
                break
            for listing in listings:
                if listing['url'] not in seen_urls:
                    seen_urls.add(listing['url'])
                    all_listings.append(listing)
            print(f"  Page {page}: {len(listings)} found, {new} new", file=__import__('sys').stderr)
            time.sleep(0.3)

    print(f"\nTotal unique listings: {len(all_listings)}", file=__import__('sys').stderr)
    return all_listings


def parse_listings(html: str) -> List[Dict[str, Any]]:
    """Parse listings from HTML using regex - returns raw listing data."""
    listings = []

    # Split by listing blocks
    listing_htmls = re.split(r'(?=<div class="col-lg-12"><a href="/seznam-prostih-sob/)', html)

    for block in listing_htmls:
        if '/seznam-prostih-sob/' not in block:
            continue

        try:
            # Extract URL
            url_match = re.search(r'href="(/seznam-prostih-sob/\d+)"', block)
            if not url_match:
                continue
            url = MOJCIMER_BASE_URL + url_match.group(1)

            # Extract price
            price_match = re.search(r'<span class="fp_price"[^>]*>(\d+)&euro;', block)
            if not price_match:
                price_match = re.search(r'<span class="fp_price"[^>]*>(\d+)\u20ac', block)
            if not price_match:
                price_match = re.search(r'<span class="fp_price"[^>]*>(\d+)\$', block)
            if not price_match:
                price_match = re.search(r'fp_price[^>]*>(\d+)', block)
            price = int(price_match.group(1)) if price_match else None

            # Extract title
            title_match = re.search(r'<h4[^>]*>([^<]+)</h4>', block)
            title = title_match.group(1).strip() if title_match else ""

            # Extract address
            addr_match = re.search(r'<div class="address[^>]*><i[^>]*></i>\s*([^<]+)</div>', block)
            address = addr_match.group(1).strip() if addr_match else ""

            # Extract location tag (Koper, Izola, etc)
            loc_match = re.search(r'<li class="list-inline-item">([^<]+)</li>', block)
            location = loc_match.group(1).strip() if loc_match else ""

            # Extract beds
            beds_match = re.search(r'<i class="fad fa-bed-alt"></i>\s*(\d+)', block)
            beds = int(beds_match.group(1)) if beds_match else None

            # Extract size
            size_match = re.search(r'<i class="fad fa-draw-square"></i>\s*(\d+)m', block)
            size = int(size_match.group(1)) if size_match else None

            # Extract baths from listing page
            baths_match = re.search(r'<i class="fad fa-shower"></i>\s*(\d+)', block)
            baths = int(baths_match.group(1)) if baths_match else None

            # Extract description
            desc_match = re.search(r'<p>([^<]{10,200})</p>', block)
            description = desc_match.group(1).strip() if desc_match else ""

            # Extract thumbnail image
            img_match = re.search(r'<img[^>]*class="[^"]*checkImage[^"]*"[^>]*src="([^"]+)"', block)
            thumbnail = MOJCIMER_BASE_URL + img_match.group(1) if img_match else ""

            # Combine location + address for parser
            location_raw = f"{location} {address}".strip()

            listing = {
                "title": title,
                "location": location_raw,
                "address": address,
                "price": price,
                "capacity": beds,
                "size_sqm": size,
                "baths": baths,
                "contact_name": "",
                "contact_phone": "",
                "description": description[:200] if description else "",
                "thumbnail": thumbnail,
                "url": url,
                "source": "mojcimer",
            }

            if title and price:
                listings.append(listing)

        except Exception as e:
            continue

    return listings


def fetch_listing_details(url: str) -> Dict[str, Any]:
    """Fetch full details from a listing detail page.

    Returns dict with: description, size, beds, baths, amenities,
    contact_phone, contact_email, images.
    """
    html = fetch_page(url)
    if not html:
        return {}

    result = {}

    # Full description
    desc_match = re.search(r'<div class="content-inner[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
    if desc_match:
        desc = re.sub(r'<[^>]+>', ' ', desc_match.group(1))
        desc = ' '.join(desc.split())
        result['description_full'] = desc

    # Size
    size_match = re.search(r'(\d+)m<sup>2</sup>', html)
    if size_match:
        result['size_sqm'] = int(size_match.group(1))

    # Beds
    beds_match = re.search(r'Postelj:.*?<span>(\d+)</span>', html)
    if beds_match:
        result['capacity'] = int(beds_match.group(1))

    # Baths
    baths_match = re.search(r'Kopalnic:.*?<span>(\d+)</span>', html)
    if baths_match:
        result['baths'] = int(baths_match.group(1))

    # Price (more accurate from detail page)
    price_match = re.search(r'<div>(\d+)<small>EUR/mesec</small></div>', html)
    if price_match:
        result['price_eur'] = int(price_match.group(1))

    # Address
    addr_match = re.search(r'<p class="location"><i[^>]*></i>\s*([^<]+)</p>', html)
    if addr_match:
        result['address'] = addr_match.group(1).strip()

    # Amenities
    amenities = re.findall(r'<i class="fal fa-check-circle"></i>\s*([^<]+)', html)
    result['amenities'] = [a.strip() for a in amenities]

    # Contact phone
    phone_match = re.search(r'href="tel:([^"]+)"', html)
    if phone_match:
        result['contact_phone'] = phone_match.group(1)

    # Contact email
    email_match = re.search(r'href="mailto:([^"]+)"', html)
    if email_match:
        result['contact_email'] = email_match.group(1)

    # Images
    img_matches = re.findall(r'src="(/storage/image/[^"]+/crop/[^"]+\.(?:jpg|png|jpeg))"', html)
    result['images'] = list(set([MOJCIMER_BASE_URL + img for img in img_matches]))[:6]

    return result


def translate_to_english(text: str) -> str:
    """Translate Slovenian text to English using MyMemory API.
    
    For batch fallback translation, use translate_batch_nemotron().
    """
    if not text or len(text) < 5:
        return text

    # Clean HTML entities
    cleaned = clean_slovenian_text(text)
    if len(cleaned) > 800:
        cleaned = cleaned[:800]

    # Try MyMemory API (free, no key needed)
    try:
        from urllib.parse import quote
        encoded = quote(cleaned)
        url = f"https://api.mymemory.translated.net/get?q={encoded}&langpair=sl|en"
        result = subprocess.run(
            ["curl", "-s", "-L", url],
            capture_output=True, text=True, timeout=10
        )
        data = json.loads(result.stdout)
        resp_text = data.get('responseData', {}).get('translatedText', '')
        if data.get('responseStatus') == 200 and 'MYMEMORY WARNING' not in resp_text and len(resp_text) > 5:
            return resp_text
    except Exception:
        pass

    # Return original if MyMemory fails — will be batch-translated later
    return cleaned


def clean_slovenian_text(text: str) -> str:
    """Clean HTML entities and tags from Slovenian text."""
    text = text.replace('&scaron;', 'š').replace('&Scaron;', 'Š')
    text = text.replace('&ccaron;', 'č').replace('&Ccaron;', 'Č')
    text = text.replace('&zcaron;', 'ž').replace('&Zcaron;', 'Ž')
    text = text.replace('&nbsp;', ' ').replace('&ndash;', '–')
    text = text.replace('&euro;', '€')
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()


def translate_batch_nemotron(texts_dict: dict) -> dict:
    """
    Batch translate multiple Slovenian texts to English using Hunter (OpenRouter).
    
    Args:
        texts_dict: {id: text} mapping
        
    Returns:
        {id: translated_text} mapping
    """
    if not texts_dict:
        return {}

    # Build a single prompt with all texts numbered
    numbered = []
    for uid, text in texts_dict.items():
        numbered.append(f"[{uid}] {text[:500]}")

    all_text = "\n\n".join(numbered)
    
    # Truncate if too long
    if len(all_text) > 30000:
        all_text = all_text[:30000]

    prompt = f"""Translate these Slovenian housing listing descriptions to English.
Return a JSON object mapping each ID to its translation. ONLY return the JSON, nothing else.

Format: {{"id1": "translation1", "id2": "translation2", ...}}

Texts to translate:
{all_text}"""

    try:
        import urllib.request
        
        url = "https://openrouter.ai/api/v1/chat/completions"
        payload = json.dumps({
            "model": "openrouter/hunter-alpha",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4000,
            "temperature": 0.1
        }).encode()

        req = urllib.request.Request(url, data=payload, headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer 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"
        })
        
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            content = data["choices"][0]["message"]["content"].strip()
            
            # Parse JSON from response (might have markdown code block)
            if content.startswith("```"):
                content = re.sub(r'^```(?:json)?\s*', '', content)
                content = re.sub(r'\s*```$', '', content)
            
            translations = json.loads(content)
            return translations
            
    except Exception as e:
        print(f"  Batch translation failed: {e}", file=__import__('sys').stderr)
        return {}


if __name__ == "__main__":
    listings = scrape_all_listings()
    print(json.dumps(listings, indent=2, ensure_ascii=False))
