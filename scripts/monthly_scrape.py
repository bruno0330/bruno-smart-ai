#!/usr/bin/env python3
"""Incremental monthly scrape for data/gvm_index_full.json.

遠見雜誌 ships one new regular issue per month at /magazine/published/{id}.
This script tries the next issue id(s) after the last one already in the
dataset; an issue that exists but has 0 articles listed means it's just a
theme-announcement placeholder (gvm.com.tw creates these before articles
are populated) and is treated as "not published yet" -- the script stops
and leaves it for a later run to pick up, rather than recording it empty.

Field extraction is validated against live pages (see project memory):
- title / url / author: JSON-LD ItemList on the issue page
- year/month + issue number ("第NNN期"): <p class="magazine-info_issue">
  pair on the issue page
- issue theme title ('m'): JSON-LD BreadcrumbList, 3rd item's name
- category ('s') + summary ('e'): per-article page (breadcrumb 2nd item,
  and <meta name="description">) -- same extraction the backfill script uses

Intended to run monthly via GitHub Actions (see .github/workflows/monthly-scrape.yml),
which opens a PR for human review rather than pushing directly.

Usage:
    python3 scripts/monthly_scrape.py
"""
import json
import re
import html
import time
import random
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA_FILE = REPO / 'data' / 'gvm_index_full.json'
SUMMARY_FILE = REPO / 'scripts' / '.monthly_scrape_summary.txt'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0 Safari/537.36'
}
LDJSON_RE = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL)
ISSUE_INFO_RE = re.compile(
    r'magazine-info_issue[^"]*"[^>]*>\s*(\d{4})\s*年\s*(\d{1,2})\s*月號\s*</p>\s*'
    r'<p class="magazine-info_issue[^"]*"[^>]*>\s*(第\d+期)'
)
DESC_RE = re.compile(r'<meta\s+name="description"\s+content="([^"]*)"', re.IGNORECASE)
BREADCRUMB_CAT_RE = re.compile(
    r'breadcrumbs_link[^>]*href="[^"]*"\s+title="遠見線上讀"[^>]*>.*?</a>\s*</div>\s*'
    r'<div class="breadcrumbs_item">\s*<a class="breadcrumbs_link[^>]*title="([^"]*)"',
    re.DOTALL
)
ARTICLE_ID_RE = re.compile(r'/article/(\d+)')

MAX_ISSUES_PER_RUN = 3
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3
SLEEP_MIN = 0.3
SLEEP_MAX = 0.5


def fetch(url):
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                return resp.read().decode('utf-8', errors='replace')
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last_err = e
        except Exception as e:
            last_err = e
        time.sleep(1.5 * (attempt + 1))
    raise last_err


def parse_issue_page(text):
    """Returns (theme_title, year_month, issue_no, items) or None if not yet populated."""
    m = LDJSON_RE.search(text)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None

    graph = data.get('@graph', [])
    item_list = next((n for n in graph if n.get('@type') == 'ItemList'), None)
    breadcrumb = next((n for n in graph if n.get('@type') == 'BreadcrumbList'), None)
    if not item_list or int(item_list.get('numberOfItems', 0)) == 0:
        return None

    theme_title = ''
    if breadcrumb:
        crumbs = breadcrumb.get('itemListElement', [])
        if len(crumbs) >= 3:
            theme_title = crumbs[2]['item']['name']

    info_m = ISSUE_INFO_RE.search(text)
    if not info_m:
        raise ValueError('could not find magazine-info_issue year/month/issue-number on issue page')
    year, month, issue_no = info_m.group(1), info_m.group(2).zfill(2), info_m.group(3)
    year_month = f'{year}/{month}'

    items = []
    for el in item_list.get('itemListElement', []):
        art = el.get('item', {})
        url = art.get('url', '')
        aid_m = ARTICLE_ID_RE.search(url)
        if not aid_m:
            continue
        items.append({
            'i': aid_m.group(1),
            't': art.get('headline', '').strip(),
            'url': url,
            'a': ((art.get('author') or {}).get('name') or '').strip(),
        })
    return theme_title, year_month, issue_no, items


def fetch_article_extra(url):
    """Returns (summary, category) for one article page."""
    text = fetch(url)
    if text is None:
        return '', ''
    desc_m = DESC_RE.search(text)
    summary = html.unescape(desc_m.group(1)).strip() if desc_m else ''
    cat_m = BREADCRUMB_CAT_RE.search(text)
    category = html.unescape(cat_m.group(1)).strip() if cat_m else ''
    return summary, category


def main():
    data = json.loads(DATA_FILE.read_text(encoding='utf-8'))
    articles = data['articles']
    existing_ids = {a['i'] for a in articles}

    next_id = data['id_range'][1] + 1
    new_articles_total = []
    scraped_issue_labels = []

    for candidate_id in range(next_id, next_id + MAX_ISSUES_PER_RUN):
        url = f'https://www.gvm.com.tw/magazine/published/{candidate_id}'
        text = fetch(url)
        if text is None:
            print(f'issue {candidate_id}: 404, stopping (nothing more to try)')
            break

        parsed = parse_issue_page(text)
        if parsed is None:
            print(f'issue {candidate_id}: exists but not yet populated (0 articles), stopping here')
            break

        theme_title, year_month, issue_no, items = parsed
        print(f'issue {candidate_id}: {year_month} {issue_no} "{theme_title}" -- {len(items)} articles')

        for item in items:
            if item['i'] in existing_ids:
                continue
            time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))
            summary, category = fetch_article_extra(item['url'])
            new_articles_total.append({
                'i': item['i'],
                't': item['t'],
                'e': summary,
                'y': year_month,
                'n': issue_no,
                'm': theme_title,
                's': category,
                'a': item['a'],
                'issue_id': candidate_id,
                'issue_kind': 'published',
                'source_url': item['url'],
            })
            existing_ids.add(item['i'])

        data['done_ids'].append(candidate_id)
        data['id_range'][1] = candidate_id
        scraped_issue_labels.append(f'{year_month} {issue_no}')
        time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))

    if not new_articles_total:
        print('No new issue found this run.')
        SUMMARY_FILE.write_text('', encoding='utf-8')
        return

    articles.extend(new_articles_total)
    data['article_count'] = len(articles)
    data['generated_at'] = datetime.now(timezone.utc).isoformat()
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    summary = (f'Scraped {len(scraped_issue_labels)} new issue(s): {", ".join(scraped_issue_labels)} '
               f'-- {len(new_articles_total)} new articles.')
    print(summary)
    SUMMARY_FILE.write_text(summary, encoding='utf-8')


if __name__ == '__main__':
    main()
