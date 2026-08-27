#!/usr/bin/env python3
"""Full scrape of esg.gvm.com.tw (ESG遠見共好圈) into data/esg_index_full.json.

Unlike the main 遠見雜誌 site, esg.gvm.com.tw is WordPress and exposes its own
public REST API (no auth, allowed by robots.txt) -- one page of the API
already returns real title/date/category/excerpt/content/author/image for up
to 100 posts, so this doesn't need the per-issue-then-per-article crawl the
main-site scripts use. ~4,289 posts total as of 2026-08-27.

Schema mirrors data/gvm_index_full.json (i/t/e/y/n/m/s/a/source_url) so the
existing smart-curation search/scoring logic (SYNONYM_GROUPS, scoreArticle,
etc.) can run against this dataset unchanged once it's wired up in a later
stage -- this script's only job is producing a complete, real dataset.
'n' (magazine issue number) has no ESG equivalent -- left as '' since
formatSource() in the app already drops empty n gracefully.

Usage:
    python3 scripts/scrape_esg.py
"""
import html
import json
import re
import time
import random
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_FILE = REPO / 'data' / 'esg_index_full.json'

API_BASE = 'https://esg.gvm.com.tw/wp-json/wp/v2'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0 Safari/537.36'
}
PER_PAGE = 100
REQUEST_TIMEOUT = 20
MAX_RETRIES = 3
SLEEP_MIN = 0.4
SLEEP_MAX = 0.8

TAG_RE = re.compile(r'<[^>]+>')
SCRIPT_STYLE_RE = re.compile(r'<(script|style)[^>]*>.*?</\1>', re.DOTALL | re.IGNORECASE)
COMMENT_RE = re.compile(r'<!--.*?-->', re.DOTALL)
WS_RE = re.compile(r'[ \t]+')
BLANKLINES_RE = re.compile(r'\n{3,}')


def html_to_text(raw):
    if not raw:
        return ''
    text = SCRIPT_STYLE_RE.sub(' ', raw)
    text = COMMENT_RE.sub(' ', text)
    text = re.sub(r'<(p|div|li|br|/h[1-6])\b[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = TAG_RE.sub('', text)
    text = html.unescape(text)
    text = WS_RE.sub(' ', text)
    text = BLANKLINES_RE.sub('\n\n', text)
    return text.strip()


def fetch_json(url):
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 400:
                return None  # past the last page
            last_err = e
        except Exception as e:
            last_err = e
        time.sleep(1.5 * (attempt + 1))
    raise last_err


def fetch_categories():
    cats = {}
    page = 1
    while True:
        batch = fetch_json(f'{API_BASE}/categories?per_page=100&page={page}')
        if not batch:
            break
        for c in batch:
            cats[c['id']] = html.unescape(c['name']).strip()
        if len(batch) < 100:
            break
        page += 1
    return cats


def category_name(post, cats):
    ids = post.get('categories') or []
    named = [cats[i] for i in ids if i in cats and cats[i] != '未分類']
    if named:
        return named[0]
    return cats.get(ids[0], '') if ids else ''


def embedded_first(post, key, field):
    emb = post.get('_embedded', {}).get(key)
    if not emb:
        return ''
    first = emb[0]
    return first.get(field, '') if isinstance(first, dict) else ''


def convert_post(post, cats):
    date = post.get('date', '')  # site-local time, e.g. "2026-08-27T16:29:42"
    y = date[:7].replace('-', '/') if len(date) >= 7 else ''
    title = html.unescape(post.get('title', {}).get('rendered', '')).strip()
    title = TAG_RE.sub('', title)
    excerpt = html_to_text(post.get('excerpt', {}).get('rendered', ''))
    content = html_to_text(post.get('content', {}).get('rendered', ''))
    img = embedded_first(post, 'wp:featuredmedia', 'source_url')
    author = embedded_first(post, 'author', 'name')
    return {
        'i': str(post['id']),
        't': title,
        'e': excerpt or content[:200],
        'full': content,
        'y': y,
        'n': '',
        'm': '',
        's': category_name(post, cats),
        'a': author,
        'source_url': post.get('link', ''),
        'img': img,
    }


def main():
    print('Fetching category list...')
    cats = fetch_categories()
    print(f'  {len(cats)} categories')

    first = fetch_json(f'{API_BASE}/posts?per_page=1')
    if first is None:
        raise RuntimeError('could not reach esg.gvm.com.tw REST API')

    articles = []
    page = 1
    while True:
        url = f'{API_BASE}/posts?per_page={PER_PAGE}&page={page}&orderby=date&order=desc&_embed=1'
        batch = fetch_json(url)
        if not batch:
            break
        for post in batch:
            articles.append(convert_post(post, cats))
        print(f'  page {page}: {len(batch)} posts (total so far: {len(articles)})')
        if len(batch) < PER_PAGE:
            break
        page += 1
        time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))

    out = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'source': 'https://esg.gvm.com.tw/ (WordPress REST API)',
        'article_count': len(articles),
        'articles': articles,
    }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Wrote {len(articles)} articles to {OUT_FILE} ({OUT_FILE.stat().st_size / 1024 / 1024:.1f} MB)')


if __name__ == '__main__':
    main()
