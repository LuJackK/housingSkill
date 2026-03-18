# housingSkill

Housing skill for AI agents like Openclaw or Claude Code that scrapes Slovenian real-estate websites for rental listings. Provides analysis and ranking based on the users criteria and compiles scheduled reports.

## Features

- **Multi-source scraping** – fetches rental listings from [nepremicnine.net](https://www.nepremicnine.net) and [bolha.com](https://www.bolha.com)
- **Hard filtering** – exclude listings that don't meet mandatory criteria (price range, size, rooms, location, furnished status)
- **Soft scoring & ranking** – score each listing on price, size, location preference, keyword match and furnished preference using configurable weights
- **Report generation** – produce formatted plain-text and machine-readable JSON reports
- **Scheduled reports** – run the full scrape → analyse → report cycle at a fixed interval in a background thread
- **CLI** – use `housing-skill` (or `python main.py`) directly from the command line
- **AI-agent API** – call `HousingSkill.search()` / `HousingSkill.run()` from any Python-based agent

---

## Installation

```bash
pip install -r requirements.txt
# or, for development (includes pytest):
pip install -e ".[dev]"
```

---

## Quick start

### Python API

```python
from housing_skill import HousingSkill
from housing_skill.models import ListingCriteria
from pathlib import Path

skill = HousingSkill()

criteria = ListingCriteria(
    max_price_eur=900,
    min_size_m2=40,
    min_rooms=2,
    locations=["Ljubljana"],
    preferred_locations=["Ljubljana Center"],
    furnished=True,
    keywords=["parking", "balcony"],
    max_results=10,
    price_weight=0.6,
    size_weight=0.4,
)

# One-shot search – returns ranked Listing objects
listings = skill.search(criteria)
for l in listings:
    print(f"[{l.score:.2f}] {l.title} – €{l.price_eur}/mo – {l.url}")

# Full run – also generates reports and optionally saves them
result = skill.run(criteria, output_dir=Path("reports"))
print(result["text_report"])

# Scheduled run – execute every hour, save reports to disk
scheduler = skill.schedule(criteria, interval_seconds=3600, output_dir=Path("reports"))
scheduler.start()
# ... later ...
scheduler.stop()
```

### Command-line interface

```bash
# Basic search
python main.py --location Ljubljana --max-price 900 --min-size 40 --min-rooms 2

# With preferred locations, keywords and JSON output
python main.py \
  --location Ljubljana \
  --prefer-location "Ljubljana Center" \
  --max-price 1000 \
  --min-rooms 2 \
  --furnished yes \
  --keyword parking \
  --keyword balcony \
  --format json \
  --output-dir reports/

# Scheduled run every 2 hours
python main.py --location Ljubljana --max-price 900 --schedule 7200 --output-dir reports/
```

Run `python main.py --help` for a full list of options.

---

## Project structure

```
housingSkill/
├── housing_skill/
│   ├── __init__.py          # Public API: HousingSkill, Listing, ListingCriteria
│   ├── skill.py             # HousingSkill – main orchestrator
│   ├── analyzer.py          # ListingAnalyzer – scoring & ranking
│   ├── reporter.py          # ReportGenerator – text & JSON reports
│   ├── scheduler.py         # ReportScheduler – background scheduling
│   ├── models/
│   │   ├── listing.py       # Listing and ListingCriteria dataclasses
│   └── scrapers/
│       ├── base.py          # BaseScraper – shared logic & hard filters
│       ├── nepremicnine.py  # Scraper for nepremicnine.net
│       └── bolha.py         # Scraper for bolha.com
├── tests/                   # pytest test suite (61 tests)
├── main.py                  # CLI entry point
├── requirements.txt
├── requirements-dev.txt
└── pyproject.toml
```

---

## Running the tests

```bash
pytest
```

---

## Adding a new scraper

1. Create `housing_skill/scrapers/mysite.py` with a class extending `BaseScraper`.
2. Implement `_fetch_listings(self, criteria) -> list[Listing]`.
3. Register it in `HousingSkill.__init__` (or pass it via the `scrapers=` parameter).

