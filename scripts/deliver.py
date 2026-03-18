#!/usr/bin/env python3
"""Deliver housing reports to Luka via Telegram — one PDF per inquiry."""

import sys
import json
import requests
from datetime import date
from pathlib import Path

def get_telegram_config():
    config_path = Path.home() / '.openclaw' / 'openclaw.json'
    try:
        import subprocess
        result = subprocess.run(
            ['node', '-e', f"const fs=require('fs'); const c=require('json5').parse(fs.readFileSync('{config_path}','utf8')); console.log(JSON.stringify(c.channels.telegram))"],
            capture_output=True, text=True, timeout=5
        )
        return json.loads(result.stdout)
    except Exception:
        return {
            "botToken": "8540864591:AAHaKH4bFOel-muUWC2P75CJXx6MQpqmT_I",
        }

TELEGRAM_CHAT_ID = "7994748223"
REPORTS_DIR = Path(__file__).parent.parent / 'reports'


def get_today_pdfs():
    today = date.today().strftime('%Y-%m-%d')
    return sorted(REPORTS_DIR.glob(f"report_*_{today}.pdf"))


def get_latest_analysis():
    today = date.today().strftime('%Y-%m-%d')
    # Try all inquiry-specific analysis files
    texts = []
    for f in sorted(REPORTS_DIR.glob(f"analysis_*_{today}.txt")):
        with open(f) as fh:
            texts.append(fh.read())
    if texts:
        return "\n\n".join(texts)
    # Fallback to shared
    analysis_path = REPORTS_DIR / f"analysis_{today}.txt"
    if analysis_path.exists():
        with open(analysis_path) as f:
            return f.read()
    return None


def send_message(bot_token: str, text: str):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': text,
        'parse_mode': 'Markdown',
    }
    resp = requests.post(url, json=payload, timeout=15)
    return resp.json()


def send_document(bot_token: str, filepath: str, caption: str = ""):
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    with open(filepath, 'rb') as f:
        files = {'document': f}
        data = {
            'chat_id': TELEGRAM_CHAT_ID,
            'caption': caption,
        }
        resp = requests.post(url, files=files, data=data, timeout=30)
    return resp.json()


def main():
    today = date.today().strftime('%Y-%m-%d')
    
    # Skip if already delivered today
    flag_file = Path(__file__).parent.parent / 'data' / f'.delivered_{today}.json'
    if flag_file.exists():
        print(f"Already delivered today ({today}), skipping", file=sys.stderr)
        return
    
    config = get_telegram_config()
    bot_token = config.get('botToken', '')

    if not bot_token:
        print("ERROR: No bot token found", file=sys.stderr)
        sys.exit(1)

    # 1. Send analysis text if available
    analysis = get_latest_analysis()
    if analysis:
        print("Sending analysis...", file=sys.stderr)
        for i in range(0, len(analysis), 4000):
            chunk = analysis[i:i+4000]
            send_message(bot_token, chunk)
    else:
        send_message(bot_token, f"🏠 Housing reports for {today} are ready!")

    # 2. Send all PDFs
    pdfs = get_today_pdfs()
    if pdfs:
        for pdf in pdfs:
            # Extract inquiry name from filename: report_inquiry-name_2026-03-13.pdf
            parts = pdf.stem.split('_')
            inquiry = parts[1] if len(parts) > 2 else 'report'
            caption = f"🏠 {inquiry.replace('-', ' ').title()} — {today}"
            print(f"Sending: {pdf.name}", file=sys.stderr)
            result = send_document(bot_token, str(pdf), caption)
            if result.get('ok'):
                print(f"  ✅ Sent!", file=sys.stderr)
            else:
                print(f"  ❌ Failed: {result}", file=sys.stderr)
    else:
        print("⚠️ No PDFs found", file=sys.stderr)
        send_message(bot_token, "⚠️ No report PDFs found for today.")

    # Mark as delivered
    flag_file.write_text(json.dumps({'date': today, 'sent_at': __import__('datetime').datetime.now().isoformat()}))
    print(f"✅ Delivery complete, flag saved", file=sys.stderr)


if __name__ == "__main__":
    main()
