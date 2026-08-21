#!/usr/bin/env python3
"""One-time backfill: collect each article's cover image URL.

Images aren't per-article in the original scrape. Fetching them one issue
page at a time (JSON-LD ItemList lists every article + image for that
issue in one request) is far cheaper than one request per article --
~611 issue requests instead of ~29,583 article requests.

Writes to a SEPARATE file (data/gvm_image_index.json), not
gvm_index_full.json, so this can run safely at the same time as
backfill_summaries.py without both scripts fighting over the same file.
build_curation_index.py merges this in when it rebuilds the slim dataset.

Resumable via a checkpoint file, same pattern as backfill_summaries.py.

Usage:
    python3 scripts/backfill_images.py
"""
import json
import re
import time
import random
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA_FILE = REPO / 'data' / 'gvm_index_full.json'
OUT_FILE = REPO / 'data' / 'gvm_image_index.json'
PROGRESS_FILE = REPO / 'scripts' / '.image_backfill_progress.json'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0 Safari/537.36'
}
LDJSON_RE = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL)
ARTICLE_ID_RE = re.compile(r'/article/(\d+)')

SAVE_EVERY = 50
SLEEP_MIN = 0.3
SLEEP_MAX = 0.5
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3


def fetch(url):
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                return resp.read().decode('utf-8', errors='replace')
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise last_err


def parse_issue_images(text):
    m = LDJSON_RE.search(text)
    if not m:
        return {}
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return {}
    graph = data.get('@graph', [])
    item_list = next((n for n in graph if n.get('@type') == 'ItemList'), None)
    if not item_list:
        return {}
    out = {}
    for el in item_list.get('itemListElement', []):
        art = el.get('item', {})
        url, img = art.get('url', ''), art.get('image', '')
        aid_m = ARTICLE_ID_RE.search(url)
        if aid_m and img:
            out[aid_m.group(1)] = img
    return out


def main():
    data = json.loads(DATA_FILE.read_text(encoding='utf-8'))
    issues = sorted({(a['issue_id'], a['issue_kind']) for a in data['articles']})

    images = json.loads(OUT_FILE.read_text(encoding='utf-8')) if OUT_FILE.exists() else {}
    done = set(json.loads(PROGRESS_FILE.read_text(encoding='utf-8'))) if PROGRESS_FILE.exists() else set()

    todo = [(iid, kind) for iid, kind in issues if f'{kind}:{iid}' not in done]
    print(f'Total issues to fetch: {len(todo)} (skipping {len(done)} already done)', flush=True)

    for n, (issue_id, kind) in enumerate(todo, start=1):
        path = 'published' if kind == 'published' else 'special'
        url = f'https://www.gvm.com.tw/magazine/{path}/{issue_id}'
        try:
            text = fetch(url)
            images.update(parse_issue_images(text))
        except Exception as e:
            print(f'issue {issue_id} ({kind}) failed: {e}', flush=True)
        done.add(f'{kind}:{issue_id}')

        if n % SAVE_EVERY == 0:
            OUT_FILE.write_text(json.dumps(images, ensure_ascii=False), encoding='utf-8')
            PROGRESS_FILE.write_text(json.dumps(sorted(done)), encoding='utf-8')
            print(f'[{n}/{len(todo)}] checkpoint saved, {len(images)} images collected so far', flush=True)

        time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))

    OUT_FILE.write_text(json.dumps(images, ensure_ascii=False), encoding='utf-8')
    PROGRESS_FILE.write_text(json.dumps(sorted(done)), encoding='utf-8')
    print(f'Done. {len(images)} article images collected across {len(done)} issues.', flush=True)


if __name__ == '__main__':
    main()
