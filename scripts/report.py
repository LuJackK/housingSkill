#!/usr/bin/env python3
"""Generate housing report PDFs — one per inquiry, top 10 listings each."""

import base64
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_DIR = Path(__file__).parent.parent
TEMPLATES_DIR = BASE_DIR / 'templates'
REPORTS_DIR = BASE_DIR / 'reports'
DATA_DIR = BASE_DIR / 'data'
INQUIRIES_DIR = BASE_DIR / 'inquiries'

import yaml

MAX_LISTINGS_IN_REPORT = 20


def image_to_data_uri(path: str, max_width: int = 300) -> str:
    """Convert a local image file to a base64 data URI, resizing for PDF."""
    try:
        p = Path(path)
        if not p.exists():
            return ''
        ext = p.suffix.lower().lstrip('.')
        if ext == 'jpg':
            ext = 'jpeg'

        # Try to resize with PIL to keep file small
        try:
            from PIL import Image
            import io
            img = Image.open(p)
            if img.width > max_width:
                ratio = max_width / img.width
                new_size = (max_width, int(img.height * ratio))
                img = img.resize(new_size, Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=70)
            data = base64.b64encode(buf.getvalue()).decode('ascii')
        except ImportError:
            # Fallback: use raw file (larger)
            data = base64.b64encode(p.read_bytes()).decode('ascii')

        return f'data:image/{ext};base64,{data}'
    except Exception:
        return ''


def load_inquiry(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_analysis(date_str: str) -> dict:
    """Load agent analysis results keyed by listing URL."""
    analysis_path = REPORTS_DIR / f"analysis_{date_str}.json"
    if analysis_path.exists():
        with open(analysis_path) as f:
            data = json.load(f)
        return {item['url']: item for item in data.get('analysis', data.get('analyses', []))}
    return {}


def load_analysis_for_inquiry(date_str: str, inquiry_name: str) -> dict:
    """Load analysis for a specific inquiry."""
    analysis_path = REPORTS_DIR / f"analysis_{inquiry_name}_{date_str}.json"
    if analysis_path.exists():
        with open(analysis_path) as f:
            data = json.load(f)
        return {item['url']: item for item in data.get('analysis', data.get('analyses', []))}
    # Fallback to shared analysis
    return load_analysis(date_str)


def extract_price_from_description(desc: str, capacity: int) -> tuple:
    """
    Try to extract explicit per-person price from description.
    Returns (price_pp, source) where source is 'description' or 'calculated'.
    """
    if not desc:
        return None, None

    desc_lower = desc.lower()

    # Look for explicit per-person mentions
    # "150 EUR na osebo", "150€/osebo", "150 evrov na osebo", "150 eur/osebo"
    pp_match = re.search(r'(\d+)\s*(?:€|eur|evrov?)\s*(?:/|na|per|po)\s*(?:osebo|oseb|person|študenta)', desc_lower)
    if pp_match:
        return int(pp_match.group(1)), 'description'

    # "po 150€", "po 150 eur"
    po_match = re.search(r'(?:po|vsak)\s*(\d+)\s*(?:€|eur|evrov?)', desc_lower)
    if po_match:
        return int(po_match.group(1)), 'description'

    # Look for "skupaj X EUR" (total X EUR) then divide
    total_match = re.search(r'(?:skupaj|total|vsega|cena:?\s*)\s*(\d+)\s*(?:€|eur|evrov?)', desc_lower)
    if total_match and capacity > 0:
        total = int(total_match.group(1))
        if total > 200:  # Sanity: total should be > per-person
            return round(total / capacity), 'total_from_description'

    # Check for "X eur/mesec" when capacity > 1 — might be total or per-person
    # If price is very low relative to capacity, it's likely per-person already
    monthly_match = re.search(r'(\d+)\s*(?:€|eur|evrov?)\s*(?:/|na|mesec|mesec)', desc_lower)
    if monthly_match:
        price = int(monthly_match.group(1))
        # If price < 200 and capacity > 1, it's likely per-person
        if price < 200 and capacity > 1:
            return price, 'description_per_person'

    return None, None


def sort_listings(listings: list, analysis_map: dict, people: int) -> list:
    """Sort by verdict then score. Penalize listings that don't fit."""
    verdict_order = {'Recommended': 0, 'Decent': 1, 'Skip': 2, 'Untested': 3}

    def sort_key(item):
        url = item.get('url', '')
        analysis = analysis_map.get(url, {})
        verdict = analysis.get('verdict', 'Untested')
        verdict_rank = verdict_order.get(verdict, 3)
        positives = len(analysis.get('positives', []))
        return (verdict_rank, -positives)

    return sorted(listings, key=sort_key)


def build_listing_context(listing: dict, analysis: dict, rank: int, people: int) -> dict:
    """Build template context for a single listing."""
    price = listing.get('price_eur') or listing.get('price') or 0
    capacity = listing.get('capacity') or 1

    # Price per person: trust description if explicit, otherwise calculate
    desc_full = listing.get('description_full', '')
    desc_en = listing.get('description_en', '')
    description = desc_en if desc_en else desc_full

    price_pp, price_source = extract_price_from_description(desc_full, capacity)
    if price_pp is None:
        price_pp = round(price / capacity) if capacity else price
        price_source = 'calculated'

    size = listing.get('size_sqm') or 0
    beds = listing.get('capacity') or '?'
    baths = listing.get('baths') or '?'
    utilities = listing.get('utilities_eur') or 0
    amenities = listing.get('amenities', [])
    raw_images = listing.get('images_local') or listing.get('images', [])
    images = [image_to_data_uri(img) for img in raw_images[:3] if img]
    phone = listing.get('contact_phone', '')
    email = listing.get('contact_email', '')

    verdict = analysis.get('verdict', 'Untested')
    verdict_class = analysis.get('verdict_class', 'decent')
    positives = analysis.get('positives', [])
    negatives = analysis.get('negatives', [])
    restrictions = analysis.get('restrictions', [])
    rental_period = analysis.get('rental_period', '')
    who_allowed = analysis.get('who_allowed', '')
    people_offered = analysis.get('people_offered', '')
    costs_included = analysis.get('costs_included', '')
    avg_utilities = analysis.get('avg_utilities', '')
    available = analysis.get('available', '?')

    # Fallback: extract utilities from description if analysis didn't provide it
    if not avg_utilities:
        desc_for_utils = (desc_full or '').lower()
        if 'stroški vključeni' in desc_for_utils or 'vsi stroški' in desc_for_utils or 'vključenimi stroški' in desc_for_utils:
            avg_utilities = 'Included'
        elif 'stroški niso vključeni' in desc_for_utils:
            avg_utilities = 'Not included'
        elif 'režije' in desc_for_utils or 'stroški' in desc_for_utils:
            util_match = re.search(r'(\d+)\s*(?:€|eur|evrov?)\s*(?:stroški|stroškov|režije)', desc_for_utils)
            if util_match:
                avg_utilities = f'~€{util_match.group(1)}/mo'

    has_key_info = bool(rental_period or who_allowed or people_offered or costs_included or avg_utilities)

    # Build compact verdict summary from LLM analysis
    summary_parts = []
    if verdict == 'Recommended':
        if positives:
            summary_parts.append('Strong match: ' + ', '.join(positives[:3]).lower())
    elif verdict == 'Decent':
        if positives:
            summary_parts.append('Good: ' + ', '.join(positives[:2]).lower())
        if negatives:
            summary_parts.append('But: ' + ', '.join(negatives[:2]).lower())
    elif verdict == 'Skip':
        if restrictions:
            summary_parts.append('Rejected: ' + ', '.join(restrictions[:2]).lower())
        elif negatives:
            summary_parts.append('Rejected: ' + ', '.join(negatives[:2]).lower())

    verdict_summary = '. '.join(summary_parts) + '.' if summary_parts else ''

    title = generate_title(listing)

    return {
        'RANK': str(rank),
        'IS_TOP': rank <= 3,
        'IS_NEW': listing.get('is_new', False),
        'VERDICT': verdict,
        'VERDICT_CLASS': verdict_class,
        'TITLE': title,
        'ADDRESS': listing.get('address', '') or listing.get('location', ''),
        'PRICE': str(price),
        'PRICE_PP': str(price_pp),
        'PRICE_SOURCE': price_source,
        'SIZE': str(size) if size else '?',
        'BEDS': str(beds),
        'BATHS': str(baths),
        'AVAILABLE': available,
        'HAS_UTILITIES': bool(utilities or (avg_utilities and avg_utilities not in ('', '—'))),
        'UTILITIES': f'€{utilities}' if utilities else avg_utilities,
        'HAS_KEY_INFO': has_key_info,
        'RENTAL_PERIOD': rental_period,
        'WHO_ALLOWED': who_allowed,
        'PEOPLE_OFFERED': people_offered,
        'COSTS_INCLUDED': costs_included,
        'AVG_UTILITIES': avg_utilities,
        'POSITIVES': positives,
        'NEGATIVES': negatives,
        'RESTRICTIONS': restrictions,
        'HAS_DESCRIPTION_EN': bool(description),
        'DESCRIPTION_EN': description[:600] if description else '',
        'HAS_AMENITIES': bool(amenities),
        'AMENITIES': amenities,
        'HAS_IMAGES': bool(images),
        'IMAGES': images[:3],
        'HAS_PHONE': bool(phone),
        'PHONE': phone,
        'HAS_EMAIL': bool(email),
        'EMAIL': email,
        'URL': listing.get('url', ''),
        'HAS_VERDICT_SUMMARY': bool(verdict_summary),
        'VERDICT_SUMMARY': verdict_summary,
    }


def generate_title(listing: dict) -> str:
    """Generate a descriptive title from listing attributes."""
    title = listing.get('title', '')
    addr = listing.get('address', '')
    capacity = listing.get('capacity')
    size = listing.get('size_sqm')
    price = listing.get('price_eur') or listing.get('price') or 0

    city = 'Koper'
    for c in ['Izola', 'Portorož', 'Piran', 'Lucija', 'Ankaran']:
        if c.lower() in addr.lower():
            city = c
            break

    parts = []
    if capacity and capacity <= 1:
        parts.append('Single room')
    elif capacity and capacity == 2:
        parts.append('Double room')
    elif size and size >= 60:
        parts.append('Spacious apartment')
    elif size and size >= 40:
        parts.append('Apartment')
    elif 'soba' in title.lower():
        parts.append('Room')
    elif 'stanovanje' in title.lower():
        parts.append('Apartment')
    else:
        parts.append('Listing')

    if size:
        parts.append(f'{size}m²')
    if capacity:
        parts.append(f'{capacity} beds')

    parts.append(city)

    if capacity and capacity > 0:
        pp = round(price / capacity)
        parts.append(f'€{pp}/pp')

    return ' | '.join(parts)


def render_template(template: str, context: dict) -> str:
    """Simple mustache-like template renderer with multi-pass nested tag support."""
    result = template

    list_pattern = re.compile(r'\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}', re.DOTALL)
    for match in list_pattern.finditer(result):
        var_name = match.group(1)
        block_content = match.group(2)
        value = context.get(var_name)

        if isinstance(value, bool):
            if value:
                rendered_block = render_template(block_content, context)
                result = result.replace(match.group(0), rendered_block)
            else:
                result = result.replace(match.group(0), '')
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            rendered = []
            for item in value:
                block = block_content
                for _pass in range(10):
                    nested_pattern = re.compile(r'\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}', re.DOTALL)
                    changed = False
                    for nm in list(nested_pattern.finditer(block)):
                        nv = item.get(nm.group(1))
                        if isinstance(nv, bool) and nv:
                            block = block.replace(nm.group(0), nm.group(2))
                            changed = True
                        elif isinstance(nv, bool) and not nv:
                            block = block.replace(nm.group(0), '')
                            changed = True
                        elif isinstance(nv, list) and nv:
                            inner = nm.group(2)
                            if isinstance(nv[0], str):
                                inner_rendered = ''.join([inner.replace('{{.}}', str(v)) for v in nv])
                                block = block.replace(nm.group(0), inner_rendered)
                            else:
                                block = block.replace(nm.group(0), inner)
                            changed = True
                        elif not nv:
                            block = block.replace(nm.group(0), '')
                            changed = True
                        else:
                            block = block.replace(nm.group(0), nm.group(2))
                            changed = True
                    if not changed:
                        break

                for k, v in item.items():
                    if isinstance(v, (str, int, float)):
                        block = block.replace('{{' + k + '}}', str(v) if v else '')
                    elif v is None:
                        block = re.sub(r'\{\{' + k + r'\}\}', '', block)

                rendered.append(block)
            result = result.replace(match.group(0), ''.join(rendered))
        elif isinstance(value, list) and value and isinstance(value[0], str):
            rendered = []
            for item in value:
                rendered.append(block_content.replace('{{.}}', str(item)))
            result = result.replace(match.group(0), ''.join(rendered))
        else:
            result = result.replace(match.group(0), '')

    inv_pattern = re.compile(r'\{\{\^(\w+)\}\}(.*?)\{\{/\1\}\}', re.DOTALL)
    for match in inv_pattern.finditer(result):
        var_name = match.group(1)
        block_content = match.group(2)
        value = context.get(var_name)
        if not value:
            result = result.replace(match.group(0), block_content)
        else:
            result = result.replace(match.group(0), '')

    for key, value in context.items():
        if isinstance(value, (str, int, float)):
            result = result.replace('{{' + key + '}}', str(value))

    result = re.sub(r'\{\{.*?\}\}', '', result)
    return result


def generate_report_for_inquiry(inquiry_path: Path, today_str: str, today_display: str):
    """Generate a report for a single inquiry."""
    inquiry = load_inquiry(inquiry_path)
    inquiry_name = inquiry_path.stem

    print(f"Generating report: {inquiry_name}...", file=sys.stderr)

    with open(TEMPLATES_DIR / 'report.html') as f:
        template = f.read()

    enriched_path = DATA_DIR / f"enriched_{today_str}.json"
    if not enriched_path.exists():
        print(f"ERROR: No enriched data for {today_str}. Run enrich.py first.", file=sys.stderr)
        return

    with open(enriched_path) as f:
        enriched = json.load(f)

    all_listings = enriched.get('listings', [])

    # Load analysis for this inquiry
    analysis_map = load_analysis_for_inquiry(today_str, inquiry_name)

    people = inquiry.get('people', 1)
    max_price = inquiry.get('max_price_per_person', 300)

    # Sort by verdict
    sorted_listings = sort_listings(all_listings, analysis_map, people)

    # Take top N for display
    top_listings = sorted_listings[:MAX_LISTINGS_IN_REPORT]

    listing_contexts = []
    for i, listing in enumerate(top_listings, 1):
        url = listing.get('url', '')
        analysis = analysis_map.get(url, {})
        ctx = build_listing_context(listing, analysis, i, people)
        listing_contexts.append(ctx)

    new_count = sum(1 for l in all_listings if l.get('is_new', False))

    date_range_str = ''
    for dr in inquiry.get('date_ranges', []):
        if isinstance(dr, dict):
            date_range_str += f"{dr.get('from', '')} → {dr.get('to', '')}, "
        else:
            date_range_str += f"{dr}, "

    context = {
        'DATE': today_display,
        'REPORT_TITLE': inquiry.get('name', 'Housing Report'),
        'TOTAL': str(len(all_listings)),
        'SHOWING': str(len(top_listings)),
        'NEW_COUNT': str(new_count),
        'MAX_PRICE': str(max_price),
        'PEOPLE_NEEDED': str(people),
        'LOCATION': inquiry.get('location', 'Koper'),
        'DATE_RANGE': date_range_str.rstrip(', ') or 'See inquiry',
        'GENDER': inquiry.get('gender', ''),
        'LISTINGS': listing_contexts,
        'TIMESTAMP': date.today().strftime('%Y-%m-%d %H:%M'),
    }

    html = render_template(template, context)

    html_path = REPORTS_DIR / f"report_{inquiry_name}_{today_str}.html"
    with open(html_path, 'w') as f:
        f.write(html)

    print(f"✅ Report: {html_path}", file=sys.stderr)
    return str(html_path)


def generate_all_reports():
    """Generate a report for each inquiry file."""
    today = date.today()
    today_str = today.strftime('%Y-%m-%d')
    today_display = today.strftime('%d.%m.%Y')

    for inquiry_file in sorted(INQUIRIES_DIR.glob('*.yaml')):
        generate_report_for_inquiry(inquiry_file, today_str, today_display)


if __name__ == "__main__":
    generate_all_reports()
