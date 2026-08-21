#!/usr/bin/env python3
"""Rebuild smart-curation/data/{curation_index.json, summaries/{year}.json}
from data/gvm_index_full.json.

Two-stage split to keep the up-front payload small:
- curation_index.json: light search index (title, year/issue, category,
  author, url, image, and a short excerpt SNIPPET for keyword matching).
  Full summaries are NOT included here.
- summaries/{year}.json: {article_id: full_summary_text}, one file per
  publication year. The browser only fetches the 1-5 year-files it
  actually needs, for the articles a search actually picked.

Re-run this any time gvm_index_full.json changes (after a backfill or a
monthly incremental scrape).

Usage:
    python3 scripts/build_curation_index.py
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE_FILE = REPO / 'data' / 'gvm_index_full.json'
IMAGE_INDEX_FILE = REPO / 'data' / 'gvm_image_index.json'
OUT_FILE = REPO / 'smart-curation' / 'data' / 'curation_index.json'
SUMMARIES_DIR = REPO / 'smart-curation' / 'data' / 'summaries'

SNIPPET_LEN = 60


def image_or_blank(url):
    """gvm.com.tw falls back to a generic default_pic.jpg for articles with no
    real cover image -- mostly older archive articles. Skip it rather than
    showing the same gray placeholder repeated across a set of results."""
    return '' if 'default_pic' in url else url


def main():
    data = json.loads(SOURCE_FILE.read_text(encoding='utf-8'))
    articles = [a for a in data['articles'] if a.get('e', '').strip()]

    images = json.loads(IMAGE_INDEX_FILE.read_text(encoding='utf-8')) if IMAGE_INDEX_FILE.exists() else {}

    slim = []
    by_year = {}
    for a in articles:
        year = (a.get('y') or '').split('/')[0] or 'unknown'
        by_year.setdefault(year, {})[a['i']] = a['e']

        slim.append({
            'i': a['i'],
            't': a['t'],
            'es': a['e'][:SNIPPET_LEN],
            'y': a['y'],
            'n': a['n'],
            's': a['s'],
            'a': a['a'],
            'url': a['source_url'],
            'img': image_or_blank(images.get(a['i'], '')),
        })

    out = {
        'generated_at': data.get('generated_at'),
        'count': len(slim),
        'articles': slim,
    }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'Wrote {len(slim)} articles to {OUT_FILE} ({OUT_FILE.stat().st_size / 1024:.1f} KB)')

    SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)
    for f in SUMMARIES_DIR.glob('*.json'):
        f.unlink()
    total_summary_bytes = 0
    for year, mapping in by_year.items():
        path = SUMMARIES_DIR / f'{year}.json'
        text = json.dumps(mapping, ensure_ascii=False, separators=(',', ':'))
        path.write_text(text, encoding='utf-8')
        total_summary_bytes += path.stat().st_size
    print(f'Wrote {len(by_year)} year-files to {SUMMARIES_DIR} '
          f'({total_summary_bytes / 1024:.1f} KB total, avg {total_summary_bytes / len(by_year) / 1024:.1f} KB/year)')


if __name__ == '__main__':
    main()
