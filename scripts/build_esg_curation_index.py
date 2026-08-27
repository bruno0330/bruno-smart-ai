#!/usr/bin/env python3
"""Rebuild smart-curation/data/{esg_curation_index.json, esg_summaries/{year}.json}
from data/esg_index_full.json.

Mirrors build_curation_index.py's two-stage split (light search index vs.
per-year full-text files, fetched lazily) so the existing smart-curation
search/scoring JS can run against either dataset unchanged -- only the data
files differ, not the app logic. Lives in the same smart-curation/data/
folder (not a separate esg-curation/ directory) because the plan is one
page with a top switcher between two data sources, not two separate pages.

Unlike the main site, esg_index_full.json already carries the cover image
URL directly per article (from the WP REST API's featured media) -- no
separate image-index merge step needed.

Re-run this any time esg_index_full.json changes (after a re-scrape).

Usage:
    python3 scripts/build_esg_curation_index.py
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE_FILE = REPO / 'data' / 'esg_index_full.json'
OUT_FILE = REPO / 'smart-curation' / 'data' / 'esg_curation_index.json'
SUMMARIES_DIR = REPO / 'smart-curation' / 'data' / 'esg_summaries'

SNIPPET_LEN = 60


def main():
    data = json.loads(SOURCE_FILE.read_text(encoding='utf-8'))
    articles = [a for a in data['articles'] if a.get('e', '').strip()]

    slim = []
    by_year = {}
    for a in articles:
        year = (a.get('y') or '').split('/')[0] or 'unknown'
        # 'e' is WordPress's own editorial excerpt (avg ~106 chars) -- the right length for
        # the app's "推薦閱讀文字" card field. 'full' is the entire article body (avg ~2000
        # chars) and stays in esg_index_full.json only; using it here would blow out the
        # card textarea the way the main site's short meta-description summary never does.
        by_year.setdefault(year, {})[a['i']] = a.get('e', '')

        slim.append({
            'i': a['i'],
            't': a['t'],
            'es': a['e'][:SNIPPET_LEN],
            'y': a['y'],
            'n': a.get('n', ''),
            's': a['s'],
            'a': a['a'],
            'url': a['source_url'],
            'img': a.get('img', ''),
        })

    out = {
        'generated_at': data.get('generated_at'),
        'source': data.get('source'),
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
