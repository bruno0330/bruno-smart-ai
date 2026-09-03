#!/usr/bin/env python3
"""Build smart-curation/data/podcast_index.json — the 【ESG共好圈】 episodes of
遠見ON AIR, for the 會員溝通信件生成 tab.

Why two sources instead of one
------------------------------
Neither public source alone is sufficient, and this was verified, not assumed:

- www.gvm.com.tw/podcast/category/43 (the obvious one) is CAPPED at 115
  episodes no matter how many pages you request. Three of the five episodes in
  the real member email this feature was built from are missing from it
  entirely. Do not "simplify" this script back to the category page.
- The XML sitemaps (sitemap-podcast1/2.xml) list all 1,023 podcast URLs with
  their gvm.com.tw ids and full titles -- complete -- but every
  <news:publication_date> is the placeholder 1970-01-01, so they carry no
  usable date.
- The Firstory RSS feed (the show's real host) has correct pubDate values but
  its <link> points at open.firstory.me, not the gvm.com.tw URL the email
  needs.

So: sitemaps supply the id/title/link, RSS supplies the date, matched on a
whitespace-normalised title. ~97% match; unmatched episodes keep an empty date
rather than a guessed one.

Title format
------------
Raw titles look like:
    S3 EP346／【ESG共好圈】{標題} ft. {來賓}
Spacing is inconsistent in the source ("EP346／" vs "EP319 ／", "？ ft." vs
"？ft."), so the parsing is deliberately whitespace-tolerant. The 來賓 is
split out into its own field because the email renders it OUTSIDE the
markdown link: [標題](url) ft. 來賓

Usage:
    python3 scripts/build_podcast_index.py
"""
import json
import re
import unicodedata
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_FILE = REPO / 'smart-curation' / 'data' / 'podcast_index.json'

SITEMAPS = ['https://www.gvm.com.tw/xml/sitemap-podcast%d.xml' % n for n in (1, 2)]
RSS_URL = 'https://open.firstory.me/rss/user/cku20zuxm0fra0896lldnujbe'
CATEGORY = 'ESG共好圈'
SNIPPET_LEN = 90
REQUEST_TIMEOUT = 60

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0 Safari/537.36'
}

TITLE_PREFIX = re.compile(r'^\s*S\d+\s*EP\s*\d+\s*[／/]\s*【[^】]*】\s*')
EPISODE_NO = re.compile(r'^\s*(S\d+\s*EP\s*\d+)')
FT_SPLIT = re.compile(r'\s*ft\.\s*', re.I)
# 節目摘要前面常掛一段業配。兩種寫法都要切掉，否則關鍵字會搜到贊助商而不是節目內容。
AD_MARKER = re.compile(r'——\s*以上為.{0,40}?廣告\s*——')
AD_LINK = re.compile(r'https?://fstry\.pse\.is/\S+')


def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
        return r.read().decode('utf-8', 'replace')


def norm(s):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', s)).strip().lower()


def strip_tags(s):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s)).strip()


def strip_ad(text):
    m = AD_MARKER.search(text)
    if m:
        return text[m.end():].lstrip(' —-').strip()
    # 沒有分隔線的業配（例如國泰航空那批）：切到開頭區段最後一條業配短網址之後
    head = text[:600]
    links = list(AD_LINK.finditer(head))
    if links:
        return text[links[-1].end():].lstrip(' —-').strip()
    return text


def load_sitemap_episodes():
    """gvm podcast id -> raw title, for 【ESG共好圈】 only."""
    eps = {}
    for url in SITEMAPS:
        xml = fetch(url)
        for block in re.findall(r'<url>(.*?)</url>', xml, re.S):
            loc = re.search(r'<loc>\s*(\S+?)\s*</loc>', block)
            title = re.search(r'<news:title>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</news:title>', block, re.S)
            if not (loc and title):
                continue
            m = re.search(r'/podcast/(\d+)', loc.group(1))
            if not m:
                continue  # 分類頁等非集數網址也在同一份 sitemap 裡
            raw = re.sub(r'\s+', ' ', title.group(1)).strip()
            if CATEGORY in raw:
                eps[m.group(1)] = raw
    return eps


def load_rss():
    """normalised title -> (pubDate datetime, cleaned show-notes text)."""
    xml = fetch(RSS_URL)
    out = {}
    for block in re.findall(r'<item>(.*?)</item>', xml, re.S):
        t = re.search(r'<title>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</title>', block, re.S)
        d = re.search(r'<pubDate>(.*?)</pubDate>', block)
        desc = re.search(r'<description>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</description>', block, re.S)
        if not t:
            continue
        when = None
        if d:
            try:
                when = parsedate_to_datetime(d.group(1).strip())
            except (TypeError, ValueError):
                when = None
        notes = strip_ad(strip_tags(desc.group(1))) if desc else ''
        out[norm(t.group(1))] = (when, notes)
    return out


def main():
    sitemap_eps = load_sitemap_episodes()
    rss = load_rss()
    print('sitemap 內【%s】集數：%d' % (CATEGORY, len(sitemap_eps)))
    print('RSS 集數：%d' % len(rss))

    episodes, undated = [], 0
    for eid, raw in sitemap_eps.items():
        ep_no = EPISODE_NO.match(raw)
        body = TITLE_PREFIX.sub('', raw)
        parts = FT_SPLIT.split(body, 1)
        title = parts[0].strip()
        guest = parts[1].strip() if len(parts) > 1 else ''

        when, notes = rss.get(norm(raw), (None, ''))
        if when is None:
            undated += 1

        episodes.append({
            'i': eid,
            't': title,
            'ft': guest,
            'es': notes[:SNIPPET_LEN],
            'y': when.strftime('%Y/%m') if when else '',
            'd': when.date().isoformat() if when else '',
            'n': re.sub(r'\s+', ' ', ep_no.group(1)).strip() if ep_no else '',
            's': CATEGORY,
            'url': 'https://www.gvm.com.tw/podcast/%s' % eid,
        })

    # 有日期的排前面、由新到舊；沒日期的（比對不到 RSS）排最後，不假造順序
    episodes.sort(key=lambda e: (e['d'] == '', e['d']), reverse=False)
    episodes = sorted(episodes, key=lambda e: e['d'] or '0000-00-00', reverse=True)

    with_guest = sum(1 for e in episodes if e['ft'])
    print('產出集數：%d｜有來賓 ft.：%d｜無日期：%d' % (len(episodes), with_guest, undated))

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps({
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'source': 'gvm.com.tw sitemap + Firstory RSS',
        'category': CATEGORY,
        'count': len(episodes),
        'episodes': episodes,
    }, ensure_ascii=False, indent=1), encoding='utf-8')
    print('已寫入 %s' % OUT_FILE.relative_to(REPO))


if __name__ == '__main__':
    main()
