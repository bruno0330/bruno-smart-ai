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

This also embeds the site's category hierarchy (category_tree) so the
會員溝通信件生成 tab can offer the same two-level category picker the ESG site's
own top nav uses. It matters because the index's own 's' field stores the LEAF
category ("企業案例", "全球趨勢"), while the nav shows PARENTS ("實踐案例",
"趨勢新知") -- filtering on the nav names against 's' directly would match
almost nothing (實踐案例 is 8 articles as a leaf, 580 rolled up).

The hierarchy is fetched from the WP REST API at BUILD time and baked into the
JSON. That is not a violation of the zero-API rule: the rule is about the code
that ships to the public site, which still makes no external calls at runtime.

Re-run this any time esg_index_full.json changes (after a re-scrape).

Usage:
    python3 scripts/build_esg_curation_index.py
"""
import json
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE_FILE = REPO / 'data' / 'esg_index_full.json'
OUT_FILE = REPO / 'smart-curation' / 'data' / 'esg_curation_index.json'
SUMMARIES_DIR = REPO / 'smart-curation' / 'data' / 'esg_summaries'

SNIPPET_LEN = 60

CATEGORIES_API = 'https://esg.gvm.com.tw/wp-json/wp/v2/categories?per_page=100'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0 Safari/537.36'
}


def fetch_category_tree():
    """{leaf category name: parent category name}. A top-level category maps to
    itself, so callers can roll any article up with a single lookup.

    Returns {} on failure rather than raising -- a missing tree degrades the
    category picker to a flat list, which is far better than failing the whole
    index rebuild over a nav nicety."""
    try:
        req = urllib.request.Request(CATEGORIES_API, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as r:
            cats = json.loads(r.read().decode('utf-8'))
    except Exception as exc:                                    # noqa: BLE001
        print(f'  ! category tree unavailable ({exc}); shipping without it')
        return {}
    by_id = {c['id']: c for c in cats}
    tree = {}
    for c in cats:
        parent = by_id.get(c['parent'])
        tree[c['name']] = parent['name'] if parent else c['name']
    return tree


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

    tree = fetch_category_tree()
    # 只保留索引裡真的用得到的分類，別把官網有、我們沒文章的分類也帶進去，
    # 免得選單列出永遠搜不到東西的項目。
    used = {a['s'] for a in slim}
    tree = {k: v for k, v in tree.items() if k in used}
    missing = sorted(used - set(tree))
    if missing:
        print(f'  ! {len(missing)} categories have no parent mapping: {missing}')

    out = {
        'generated_at': data.get('generated_at'),
        'source': data.get('source'),
        'count': len(slim),
        'category_tree': tree,
        'articles': slim,
    }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'Wrote {len(slim)} articles to {OUT_FILE} ({OUT_FILE.stat().st_size / 1024:.1f} KB)')
    parents = sorted(set(tree.values()))
    print(f'Category tree: {len(tree)} leaf categories under {len(parents)} parents -- {parents}')

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
