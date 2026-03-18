---
name: housing
description: Automated daily apartment hunting pipeline for mojcimer.si (Slovenian rental platform). Scrapes listings, filters by criteria (price, location, capacity, dates), analyzes with LLM, generates PDF reports, and delivers to Telegram. Use when user asks about housing listings, apartment reports, or the housing pipeline.
metadata:
  openclaw:
    version: 1
---

# Housing Pipeline Skill

Automated daily scraping, analysis, and reporting for apartment listings on mojcimer.si (Slovenian rental platform).

## Purpose

Finds apartments matching specific criteria (price, location, capacity, dates), analyzes them with an LLM, and delivers formatted PDF reports to Telegram. Runs daily via cron at 8:00 AM Europe/Zagreb.

## Dependencies

- Python 3 with `requests`, `yaml`, `Pillow` (PIL)
- Node.js with `playwright-core` (for PDF generation)
- OpenClaw gateway running (for cron + agent analysis)
- OpenRouter API key (in `~/.openclaw/openclaw.json`)
- Chromium (installed via Playwright at `~/.cache/ms-playwright/`)

## Directory Structure

```
housing/
├── SKILL.md                    # This file
├── scripts/
│   ├── enrich.py               # Scrape + fetch details + translate + download images
│   ├── score.py                # Programmatic pre-filtering and ranking
│   ├── report.py               # Generate HTML reports from template
│   ├── deliver.py              # Send PDFs to Telegram
│   └── cron_daily.sh           # Daily pipeline orchestration
├── lib/
│   ├── mojcimer.py             # Scraper: fetch pages, details, images, translate
│   ├── parser.py               # Parse and normalize listing data
│   ├── config.py               # Scraper configuration (date ranges, etc.)
│   └── main.py                 # Main scraper pipeline (run_pipeline)
├── templates/
│   └── report.html             # HTML report template (Mustache-style)
├── inquiries/
│   ├── summer-1p.yaml          # Summer 1-person inquiry
│   └── school-year-4p.yaml     # School year 4-person inquiry
├── data/                       # Generated: enriched + filtered JSON
├── reports/                    # Generated: HTML, PDF, analysis JSON
│   ├── images/                 # Downloaded listing images (URL-hash filenames)
│   ├── report_*_YYYY-MM-DD.{html,pdf}
│   └── analysis_*_YYYY-MM-DD.json
└── logs/                       # Pipeline logs
```

## Pipeline Flow

```
Heartbeat trigger (8:00-9:30 AM)
  → Sub-agent runs full pipeline:
    → scripts/enrich.py        # Scrape all pages, fetch 40 details, translate, download images
    → scripts/score.py         # Pre-filter (reject girls-only, wrong dates, over-budget), rank top 25
    → scripts/analyze.py       # LLM analysis of top 25 per inquiry (Hunter model via OpenRouter)
    → scripts/report.py        # Generate per-inquiry HTML reports (top 20)
    → Playwright → PDF         # Convert HTML to PDF
    → scripts/deliver.py       # Send PDFs to Telegram
```

## Inquiry Configuration

Each YAML file in `inquiries/` defines search criteria:

```yaml
name: "School Year 2026-27 (4 People)"
description: "Looking for housing for 4 people for the school year"

people: 4
max_price_per_person: 300
currency: EUR
gender: "male (all boys group)"

date_ranges:
  - from: "2026-10-01"
    to: "2027-06-30"

location: "Koper"
max_distance_from_center_km: 3
min_size_sqm: 40
```

## Key Design Decisions

### Image Deduplication
The site reuses the same image URLs across many listings. Images are saved with URL-hash filenames (`md5(url)[:12].jpg`) so duplicates map to the same file. Report renderer also deduplicates by base64 content.

### Translation System
- Primary: MyMemory API (free, daily quota ~100 texts)
- Fallback: Hunter batch translation (10 texts per API call, via OpenRouter)
- Nemotron 120B: Reasoning model, unusable (outputs `reasoning` not `content`)

### Pre-filtering
Deterministic scoring before LLM analysis reduces workload from ~200 listings to ~25 per inquiry:
- Auto-reject: girls-only, wrong dates, way over budget
- Score by: price/person match, capacity, size, dates, utilities, location

### Template Rendering
Mustache-style with multi-pass nested tag resolution (up to 10 passes). Supports:
- Boolean blocks: `{{#VAR}}...{{/VAR}}`
- String lists: `{{#VAR}}<tag>{{.}}</tag>{{/VAR}}`
- Dict lists: `{{#VAR}}...{{KEY}}...{{/VAR}}`
- Negation: `{{^VAR}}...{{/VAR}}`
- Images embedded as base64 data URIs (required for Chromium PDF mode)

## Common Tasks

### Run pipeline manually
```bash
cd /home/luka/.openclaw/workspace
python3 skills/housing/scripts/enrich.py
python3 skills/housing/scripts/score.py
python3 skills/housing/scripts/analyze.py    # LLM analysis (uses OpenRouter/Hunter)
python3 skills/housing/scripts/report.py
# Convert to PDF (see heartbeat for Playwright command)
python3 skills/housing/scripts/deliver.py
```

### Test scoring only
```bash
python3 housing/scripts/score.py
```

### Check cron logs
```bash
tail -50 /home/luka/.openclaw/workspace/housing/logs/cron.log
```

### Add new inquiry
Create a new YAML in `inquiries/` following the format above. Pipeline automatically picks it up.

## Cron Configuration

- **Trigger:** Heartbeat (8:00-9:30 AM Europe/Zagreb)
- **Analysis:** Direct via `scripts/analyze.py` (OpenRouter Hunter model)
- **Enrich limit:** 40 detail page fetches per run
- **Report max:** 20 listings per inquiry
- **Analysis model:** `openrouter/hunter-alpha`

## Troubleshooting

| Issue | Fix |
|-------|-----|
| No analysis files | Check OpenClaw cron exists: `openclaw cron list` |
| Images duplicated | Check URL-hash naming in `lib/mojcimer.py` |
| Translation missing | MyMemory quota exhausted; Hunter fallback should work |
| PDF blank/wrong | Check base64 images; Chromium needs data URIs |
| Script path errors | All scripts use `Path(__file__).parent.parent` as BASE_DIR |
