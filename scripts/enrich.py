#!/usr/bin/env python3
"""Enrich scraped listings with translations.

Step 2 of the pipeline. Reads from raw_{date}.json (produced by scrape_unified.py),
translates Slovenian descriptions to English, outputs enriched_{date}.json.

Usage:
    python3 enrich.py [--input data/raw_YYYY-MM-DD.json]
"""

import json
import sys
import time
import subprocess
import re
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.mojcimer import translate_to_english, translate_batch_nemotron, clean_slovenian_text, fetch_page, fetch_listing_details

DATA_DIR = Path(__file__).parent.parent / 'data'
IMAGES_DIR = Path(__file__).parent.parent / 'reports' / 'images'
MOJCIMER_BASE = "https://www.mojcimer.si"


def download_image(url: str, dest: Path) -> bool:
    try:
        result = subprocess.run(["curl", "-s", "-L", "-o", str(dest), url], timeout=15)
        return dest.exists() and dest.stat().st_size > 0
    except Exception:
        return False


def fetch_mojcimer_images(url: str, listing_id: str, global_seen_hashes: set) -> list:
    """Download images from mojcimer listing page."""
    import hashlib

    html = fetch_page(url)
    if not html:
        return []

    img_matches = re.findall(r'src="(/storage/image/[^"]+/crop/[^"]+\.(?:jpg|png|jpeg))"', html)
    img_urls = list(set([MOJCIMER_BASE + img for img in img_matches]))[:6]

    local_images = []
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    for img_url in img_urls:
        ext = img_url.rsplit('.', 1)[-1]
        tmp_path = IMAGES_DIR / f"tmp_{listing_id}_{len(local_images)}.{ext}"
        if not download_image(img_url, tmp_path):
            continue

        with open(tmp_path, 'rb') as f:
            content_hash = hashlib.md5(f.read()).hexdigest()[:12]

        if content_hash in global_seen_hashes:
            tmp_path.unlink(missing_ok=True)
            continue

        global_seen_hashes.add(content_hash)
        final_path = IMAGES_DIR / f"{listing_id}_{len(local_images)}.{ext}"
        import shutil
        shutil.move(str(tmp_path), str(final_path))
        local_images.append(str(final_path))
        if len(local_images) >= 3:
            break

    return local_images


def main():
    today = date.today()
    today_str = today.strftime('%Y-%m-%d')

    # Load raw scraped data
    raw_path = DATA_DIR / f"raw_{today_str}.json"
    if not raw_path.exists():
        print(f"ERROR: No raw data for {today_str}", file=sys.stderr)
        print(f"Run scrape_unified.py first!", file=sys.stderr)
        sys.exit(1)

    with open(raw_path) as f:
        raw_data = json.load(f)

    all_listings = raw_data.get('listings', [])
    by_source = raw_data.get('by_source', {})
    print(f"Loaded {len(all_listings)} raw listings", file=sys.stderr)
    for src, count in by_source.items():
        print(f"  {src}: {count}", file=sys.stderr)

    # Enrich mojcimer listings (need detail fetch + images)
    global_seen_hashes = set()
    mojcimer = [l for l in all_listings if l.get('source') == 'mojcimer']
    others = [l for l in all_listings if l.get('source') != 'mojcimer']

    if mojcimer:
        print(f"\nEnriching {len(mojcimer)} mojcimer listings...", file=sys.stderr)
        for i, listing in enumerate(mojcimer):
            url = listing.get('url', '')
            lid = listing.get('listing_id', f'unknown_{i}')

            if i < 40 and url:
                print(f"  [{i+1}/{min(len(mojcimer), 40)}] {listing.get('title', '?')[:40]}", file=sys.stderr)

                try:
                    details = fetch_listing_details(url)
                    if details:
                        for key in ['description_full', 'size_sqm', 'capacity', 'baths',
                                   'amenities', 'contact_phone', 'contact_email', 'address']:
                            if key in details and details[key]:
                                listing[key] = details[key]

                        desc = details.get('description_full', '')
                        if desc:
                            listing['description_en'] = translate_to_english(desc)
                            time.sleep(0.3)

                    imgs = fetch_mojcimer_images(url, lid, global_seen_hashes)
                    if imgs:
                        listing['images_local'] = imgs
                except Exception as e:
                    print(f"    Error: {e}", file=sys.stderr)

    # Translate non-mojcimer descriptions
    print(f"\nTranslating {len(others)} non-mojcimer listings...", file=sys.stderr)
    for i, listing in enumerate(others):
        desc = listing.get('description_full', '') or listing.get('description', '')
        if desc and not listing.get('description_en'):
            if any(c in desc for c in 'ščžŠČŽ'):
                print(f"  [{i+1}] {listing.get('title', '?')[:40]}", file=sys.stderr)
                listing['description_en'] = translate_to_english(desc)
                time.sleep(0.3)

    # Batch translate remaining
    needs_translation = {}
    for i, listing in enumerate(all_listings):
        desc_en = listing.get('description_en', '')
        desc_full = clean_slovenian_text(listing.get('description_full', '') or listing.get('description', ''))
        if desc_full and (not desc_en or desc_en == desc_full or len(desc_en) < 10):
            if any(c in desc_full for c in 'ščžŠČŽ'):
                needs_translation[str(i)] = desc_full[:500]

    if needs_translation:
        print(f"\nBatch translating {len(needs_translation)} remaining...", file=sys.stderr)
        translations = translate_batch_nemotron(needs_translation)
        count = 0
        for idx_str, translated in translations.items():
            idx = int(idx_str)
            if idx < len(all_listings) and translated:
                all_listings[idx]['description_en'] = translated
                count += 1
        print(f"  Translated {count}/{len(needs_translation)}", file=sys.stderr)

    # Save
    output = {
        'date': today_str,
        'total': len(all_listings),
        'listings': all_listings
    }

    output_path = DATA_DIR / f"enriched_{today_str}.json"
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n✅ {len(all_listings)} listings → {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
