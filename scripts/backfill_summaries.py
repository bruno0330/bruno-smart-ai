#!/usr/bin/env python3
"""One-time backfill for data/gvm_index_full.json.

The original scraper only captured a real summary (the 'e' field) for
~3.8% of articles (1,120 / 29,583). Spot-checks across 1987-2026 confirmed
gvm.com.tw actually serves a real <meta name="description"> on essentially
every article page -- the gap was a scraper bug, not missing content. This
script re-fetches just that one field for every article currently missing
it, using the exact regex validated against live pages during investigation.

Resumable: writes a checkpoint of attempted article ids every SAVE_EVERY
articles, and both the main data file and the checkpoint are safe to
interrupt (Ctrl-C / process kill) and re-run.

Usage:
    python3 scripts/backfill_summaries.py
"""
import json
import re
import html
import time
import random
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA_FILE = REPO / 'data' / 'gvm_index_full.json'
PROGRESS_FILE = REPO / 'scripts' / '.backfill_progress.json'
ERROR_LOG = REPO / 'scripts' / '.backfill_errors.json'

DESC_RE = re.compile(r'<meta\s+name="description"\s+content="([^"]*)"', re.IGNORECASE)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0 Safari/537.36'
}

SAVE_EVERY = 200
SLEEP_MIN = 0.3
SLEEP_MAX = 0.5
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3


def fetch_description(url):
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                raw = resp.read()
            text = raw.decode('utf-8', errors='replace')
            m = DESC_RE.search(text)
            return html.unescape(m.group(1)).strip() if m else ''
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise last_err


def load_progress():
    if PROGRESS_FILE.exists():
        return set(json.loads(PROGRESS_FILE.read_text(encoding='utf-8')))
    return set()


def save_progress(attempted):
    PROGRESS_FILE.write_text(json.dumps(sorted(attempted)), encoding='utf-8')


def save_data(data):
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    data = json.loads(DATA_FILE.read_text(encoding='utf-8'))
    articles = data['articles']

    attempted = load_progress()
    errors = {}

    def year_key(a):
        y = (a.get('y') or '').split('/')[0]
        return int(y) if y.isdigit() else 0

    targets = [a for a in articles if not a['e'].strip() and a['i'] not in attempted]
    targets.sort(key=year_key, reverse=True)  # newest first, so recent content (e.g. 國際焦點) fills in quickly
    total = len(targets)
    print(f'Total to backfill: {total} (skipping {len(attempted)} already attempted this run), newest-first order', flush=True)

    for done_count, a in enumerate(targets, start=1):
        try:
            a['e'] = fetch_description(a['source_url'])
        except Exception as e:
            errors[a['i']] = str(e)
        attempted.add(a['i'])

        if done_count % SAVE_EVERY == 0:
            save_data(data)
            save_progress(attempted)
            if errors:
                ERROR_LOG.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f'[{done_count}/{total}] checkpoint saved, last id={a["i"]}', flush=True)

        time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))

    data['summary_backfilled_at'] = datetime.now(timezone.utc).isoformat()
    save_data(data)
    save_progress(attempted)
    if errors:
        ERROR_LOG.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding='utf-8')

    got = sum(1 for a in articles if a['e'].strip())
    print(f'Done. {got}/{len(articles)} articles now have a summary. Errors: {len(errors)}', flush=True)


if __name__ == '__main__':
    main()
