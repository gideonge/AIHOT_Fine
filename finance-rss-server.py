#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""China Finance RSS Bridge

Lightweight RSS bridge server that converts Chinese financial news sources
into standard RSS 2.0 feeds.

Sources: CLS (财联社), Eastmoney (东方财富), THS (同花顺), Jin10, Wallstreetcn, CSRC (证监会), PBoC (央行), NDRC (发改委), Sina Finance (新浪财经), Cnstock (上证报)

Usage:
    python server.py
    PORT=9000 python server.py

Dependencies:
    - websocket-client (optional, only for Xueqiu CDP mode)
"""

import os
import json
import re
import signal
import sys
import urllib.request
import hashlib
from html import unescape
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.parse import parse_qs, urlencode, urlparse
from datetime import datetime, timedelta, timezone
from time import time
from email.utils import formatdate
from xml.etree import ElementTree as ET

# Configuration via environment variables
PORT = int(os.getenv('PORT', '8053'))
CDP_URL = os.getenv('CDP_URL', 'http://localhost:9222')  # Chrome DevTools Protocol URL
CACHE_TTL = int(os.getenv('CACHE_TTL', '300'))  # Cache TTL in seconds (default: 5 min)
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '10'))
PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', '').rstrip('/')

# In-memory cache
cache = {}
jin10_public_headers = None


def fetch_json(url, headers=None):
    """Fetch URL with in-memory cache."""
    now = time()
    if url in cache and now - cache[url]['time'] < CACHE_TTL:
        return cache[url]['data']

    req = Request(url, headers=headers or {})
    with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        data = resp.read().decode('utf-8')

    cache[url] = {'data': data, 'time': now}
    return data


def escape_xml(text):
    """Escape special XML characters."""
    return (str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;'))


def timestamp_to_rfc822(ts):
    """Convert Unix timestamp to RFC 822 date string."""
    return formatdate(timeval=ts, localtime=False, usegmt=True)


def parse_china_datetime_to_rfc822(value):
    """Parse a China-local datetime string into an RFC 822 UTC date."""
    dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
    dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))
    return formatdate(timeval=dt.timestamp(), localtime=False, usegmt=True)


def strip_html(text):
    """Strip simple HTML tags from upstream snippets."""
    text = re.sub(r'<[^>]+>', '', str(text or ''))
    return unescape(re.sub(r'\s+', ' ', text)).strip()


def cls_serialize_sign_value(value, key):
    """Serialize a value the same way the CLS frontend signs params."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return f'{key}={value}'
    if isinstance(value, list):
        if not value:
            return f'{key}[]'
        return '&'.join(filter(None, (
            cls_serialize_sign_value(item, f'{key}[{index}]')
            for index, item in enumerate(value)
        )))
    if isinstance(value, dict):
        return '&'.join(filter(None, (
            cls_serialize_sign_value(value[item_key], f'{key}[{item_key}]')
            for item_key in sorted(value, key=lambda item: str(item).upper())
        )))
    return None


def cls_sign_params(params):
    """Sign CLS request params using the public web frontend algorithm."""
    serialized = '&'.join(filter(None, (
        cls_serialize_sign_value(params[key], key)
        for key in sorted(params, key=lambda item: str(item).upper())
    )))
    sha1_digest = hashlib.sha1(serialized.encode('utf-8')).hexdigest()
    return hashlib.md5(sha1_digest.encode('utf-8')).hexdigest()


def extract_jin10_public_app_id(bundle_text):
    """Extract Jin10's public frontend app id from its web bundle."""
    match = re.search(r'"x-app-id":"([^"]+)"', bundle_text)
    if not match:
        raise ValueError('Jin10 public app id not found in frontend bundle')
    return match.group(1)


def get_jin10_public_headers():
    """Build Jin10 headers from public frontend assets without hardcoded ids."""
    global jin10_public_headers
    if jin10_public_headers:
        return dict(jin10_public_headers)

    base_headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.jin10.com/'}
    html = fetch_json('https://www.jin10.com/', base_headers)
    script_match = re.search(r'(?:https:)?//www\.jin10\.com/new/js/index\.[^"\']+\.js', html)
    if not script_match:
        script_match = re.search(r'/new/js/index\.[^"\']+\.js', html)
    if not script_match:
        raise ValueError('Jin10 frontend bundle not found')

    script_url = script_match.group(0)
    if script_url.startswith('//'):
        script_url = 'https:' + script_url
    elif script_url.startswith('/'):
        script_url = 'https://www.jin10.com' + script_url

    bundle = fetch_json(script_url, base_headers)
    app_id = extract_jin10_public_app_id(bundle)
    jin10_public_headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json,text/plain,*/*',
        'Referer': 'https://www.jin10.com/',
        'Origin': 'https://www.jin10.com',
        'x-app-id': app_id,
        'x-version': '1.0.0',
    }
    return dict(jin10_public_headers)


def generate_rss(title, link, description, items, feed_url=None):
    """Generate standard RSS 2.0 XML."""
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
<title>{escape_xml(title)}</title>
<link>{escape_xml(link)}</link>
<description>{escape_xml(description)}</description>
<lastBuildDate>{formatdate(timeval=None, localtime=False, usegmt=True)}</lastBuildDate>
'''
    if feed_url:
        xml += (f'<atom:link href="{escape_xml(feed_url)}" rel="self" '
                'type="application/rss+xml"/>\n')

    for item in items:
        xml += '<item>\n'
        xml += f'<title>{escape_xml(item["title"])}</title>\n'
        xml += f'<link>{escape_xml(item["link"])}</link>\n'
        xml += f'<description>{escape_xml(item["description"])}</description>\n'
        xml += f'<pubDate>{item["pubDate"]}</pubDate>\n'
        xml += f'<guid isPermaLink="false">{escape_xml(item["guid"])}</guid>\n'
        xml += '</item>\n'

    xml += '</channel>\n</rss>'
    return xml


def parse_cls_items(payload):
    """Convert CLS roll_data payload into RSS item dictionaries."""
    items = []
    for item in payload.get('data', {}).get('roll_data', []):
        item_id = item.get('id', '')
        items.append({
            'title': item.get('brief') or item.get('content', '')[:100],
            'link': f'https://www.cls.cn/telegraph/{item_id}',
            'description': item.get('content', ''),
            'pubDate': timestamp_to_rfc822(item.get('ctime', 0)),
            'guid': f'cls_{item_id}',
        })
    return items


def parse_jin10_items(payload):
    """Convert Jin10 flash API payload into RSS item dictionaries."""
    items = []
    for item in payload.get('data', []):
        item_id = item.get('id', '')
        data = item.get('data') or {}
        title = data.get('title') or strip_html(data.get('content', ''))[:100]
        content = strip_html(data.get('content') or title)
        link = data.get('source_link') or f'https://flash.jin10.com/detail/{item_id}'
        try:
            pubdate = parse_china_datetime_to_rfc822(item.get('time', ''))
        except Exception:
            pubdate = formatdate(timeval=None, localtime=False, usegmt=True)

        items.append({
            'title': title,
            'link': link,
            'description': content,
            'pubDate': pubdate,
            'guid': f'jin10_{item_id}',
        })
    return items


def parse_wallstreetcn_items(payload):
    """Convert Wallstreetcn live API payload into RSS item dictionaries."""
    items = []
    for item in payload.get('data', {}).get('items', []):
        item_id = item.get('id', '')
        description = item.get('content_text') or strip_html(item.get('content', ''))
        title = item.get('title') or description[:100]
        pub_ts = item.get('display_time') or item.get('created_at') or 0

        items.append({
            'title': title,
            'link': item.get('uri') or f'https://wallstreetcn.com/livenews/{item_id}',
            'description': description,
            'pubDate': timestamp_to_rfc822(int(pub_ts)),
            'guid': f'wallstreetcn_{item_id}',
        })
    return items


def generate_error_rss(title, link, description, error, feed_url=None):
    """Generate a valid RSS feed that explains an upstream failure."""
    error_text = str(error) or error.__class__.__name__
    items = [{
        'title': f'{title} temporarily unavailable',
        'link': link,
        'description': f'Upstream fetch failed: {error_text}',
        'pubDate': formatdate(timeval=None, localtime=False, usegmt=True),
        'guid': f'error_{title}'
    }]
    return generate_rss(title, link, description, items, feed_url=feed_url)


def generate_opml(base_url):
    """Generate an OPML subscription list for all built-in feeds."""
    base_url = (base_url or '').rstrip('/')
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
<head>
<title>China Finance RSS Bridge feeds</title>
</head>
<body>
<outline text="China Finance RSS Bridge" title="China Finance RSS Bridge">
'''
    for path, (name, _) in ROUTES.items():
        xml += (f'<outline text="{escape_xml(name)}" title="{escape_xml(name)}" '
                f'type="rss" xmlUrl="{escape_xml(base_url + path)}"/>\n')

    xueqiu_path = '/xueqiu/user/1247347556'
    xueqiu_name = 'Xueqiu User Example (雪球)'
    xml += (f'<outline text="{escape_xml(xueqiu_name)}" title="{escape_xml(xueqiu_name)}" '
            f'type="rss" xmlUrl="{escape_xml(base_url + xueqiu_path)}"/>\n')
    xml += '</outline>\n</body>\n</opml>'
    return xml


# ── Source handlers ──────────────────────────────────────────────────────────

def handle_cls_telegraph(feed_url=None):
    """CLS Telegraph (财联社电报) - Real-time financial news flashes."""
    url = 'https://www.cls.cn/v1/roll/get_roll_list'
    params = {
        'refresh_type': 1,
        'rn': 50,
        'last_time': 0,
        'os': 'web',
        'sv': '8.7.9',
        'app': 'CailianpressWeb',
    }
    params['sign'] = cls_sign_params(params)
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.cls.cn/telegraph'}

    data = json.loads(fetch_json(f'{url}?{urlencode(params)}', headers))

    return generate_rss(
        '财联社电报',
        'https://www.cls.cn/telegraph',
        '财联社实时快讯',
        parse_cls_items(data),
        feed_url=feed_url
    )


def handle_eastmoney_kuaixun(feed_url=None):
    """Eastmoney 7x24 News (东方财富快讯)."""
    url = 'https://newsapi.eastmoney.com/kuaixun/v1/getlist_102_ajaxResult_50_1_.html'
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://kuaixun.eastmoney.com/'}

    data = fetch_json(url, headers)
    match = re.search(r'var ajaxResult=(\{.*\});?', data, re.DOTALL)
    if not match:
        return generate_rss(
            '东方财富快讯',
            'https://kuaixun.eastmoney.com/',
            '东方财富7x24快讯',
            [],
            feed_url=feed_url
        )

    result = json.loads(match.group(1))
    items = []

    for item in result.get('LivesList', []):
        showtime = item.get('showtime', '')
        try:
            pubdate = parse_china_datetime_to_rfc822(showtime)
        except Exception:
            pubdate = formatdate(timeval=None, localtime=False, usegmt=True)

        items.append({
            'title': item.get('title', ''),
            'link': f"https://kuaixun.eastmoney.com/a/{item.get('newsid', '')}",
            'description': item.get('digest', ''),
            'pubDate': pubdate,
            'guid': f"eastmoney_{item.get('newsid', '')}"
        })

    return generate_rss(
        '东方财富快讯',
        'https://kuaixun.eastmoney.com/',
        '东方财富7x24快讯',
        items,
        feed_url=feed_url
    )


def handle_ths_kuaixun(feed_url=None):
    """THS 7x24 News (同花顺快讯)."""
    url = 'https://news.10jqka.com.cn/tapp/news/push/stock/?page=1&tag=&track=website&pagesize=50'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://news.10jqka.com.cn/'
    }

    data = json.loads(fetch_json(url, headers))
    items = []

    for item in data.get('data', {}).get('list', []):
        items.append({
            'title': item.get('title', ''),
            'link': f"https://news.10jqka.com.cn/{item.get('seq', '')}",
            'description': item.get('digest', item.get('remark', '')),
            'pubDate': timestamp_to_rfc822(int(item.get('ctime', 0))),
            'guid': f"ths_{item.get('seq', '')}"
        })

    return generate_rss(
        '同花顺快讯',
        'https://news.10jqka.com.cn/',
        '同花顺7x24快讯',
        items,
        feed_url=feed_url
    )


def handle_jin10_flash(feed_url=None):
    """Jin10 7x24 flash news (金十快讯)."""
    url = 'https://flash-api.jin10.com/get_flash_list?channel=-8200&limit=50'
    data = json.loads(fetch_json(url, get_jin10_public_headers()))
    return generate_rss(
        '金十快讯',
        'https://www.jin10.com/',
        '金十数据7x24快讯',
        parse_jin10_items(data),
        feed_url=feed_url
    )


def handle_wallstreetcn_live(feed_url=None):
    """Wallstreetcn 7x24 live news (华尔街见闻快讯)."""
    url = 'https://api-one-wscn.awtmt.com/apiv1/content/lives?channel=global-channel&client=pc&limit=50'
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json,text/plain,*/*',
        'Referer': 'https://wallstreetcn.com/live',
    }

    data = json.loads(fetch_json(url, headers))
    return generate_rss(
        '华尔街见闻快讯',
        'https://wallstreetcn.com/live',
        '华尔街见闻7x24快讯',
        parse_wallstreetcn_items(data),
        feed_url=feed_url
    )


def xueqiu_fetch_via_cdp(api_path):
    """Fetch Xueqiu API via Chrome CDP to bypass WAF.

    Requires:
    - Chrome running with --remote-debugging-port
    - A Xueqiu tab open and logged in
    - pip install websocket-client
    """
    try:
        import websocket as ws_mod  # noqa: lazy import
    except ImportError:
        return None

    try:
        tabs = json.loads(urllib.request.urlopen(f"{CDP_URL}/json", timeout=5).read())
        xq_tab = next((t for t in tabs if 'xueqiu' in t.get('url', '')), None)
        if not xq_tab:
            return None

        ws_url = xq_tab['webSocketDebuggerUrl']
        # Replace localhost with CDP_URL host if connecting remotely
        cdp_host = urlparse(CDP_URL).hostname
        ws_url = ws_url.replace('127.0.0.1', cdp_host).replace('localhost', cdp_host)

        ws = ws_mod.create_connection(ws_url, timeout=15)
        js = f'fetch("{api_path}").then(r=>r.json()).then(d=>JSON.stringify(d))'
        ws.send(json.dumps({
            'id': 1,
            'method': 'Runtime.evaluate',
            'params': {'expression': js, 'awaitPromise': True, 'returnByValue': True}
        }))
        result = json.loads(ws.recv())
        ws.close()
        return json.loads(result.get('result', {}).get('result', {}).get('value', '{}'))
    except Exception:
        return None


def handle_xueqiu_user(uid, feed_url=None):
    """Xueqiu user timeline (雪球用户动态).

    Uses Chrome CDP to bypass Alibaba Cloud WAF.
    """
    data = xueqiu_fetch_via_cdp(f'/v4/statuses/user_timeline.json?user_id={uid}&page=1&type=0')

    if not data:
        return generate_rss(
            '雪球用户动态', f'https://xueqiu.com/u/{uid}',
            'Error: Chrome CDP not available or Xueqiu tab not found. '
            'See README for setup instructions.', [], feed_url=feed_url
        )

    items = []
    for item in data.get('statuses', []):
        created_at = item.get('created_at', 0) // 1000
        items.append({
            'title': item.get('title', item.get('text', ''))[:100],
            'link': f"https://xueqiu.com/{item.get('id', '')}",
            'description': item.get('description', item.get('text', '')),
            'pubDate': timestamp_to_rfc822(created_at),
            'guid': f"xueqiu_{item.get('id', '')}"
        })

    username = data.get('statuses', [{}])[0].get('user', {}).get('screen_name', uid)
    return generate_rss(
        f'雪球-{username}',
        f'https://xueqiu.com/u/{uid}',
        f'{username}的雪球动态',
        items,
        feed_url=feed_url
    )




# ── New source handlers (A-share / macro focus) ─────────────────────────────

import zlib

BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}


def decode_body(raw):
    """Decode a response body that may be UTF-8 or GBK (gov sites often use GBK)."""
    if isinstance(raw, str):
        return raw
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return raw.decode('gbk', errors='replace')


def fetch_text(url, headers=None):
    """Fetch URL text with in-memory cache (5 min)."""
    now = time()
    if url in cache and now - cache[url]['time'] < CACHE_TTL:
        return cache[url]['data']

    req = Request(url, headers={**BROWSER_HEADERS, **(headers or {})})
    with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        raw = resp.read()
    data = decode_body(raw)

    cache[url] = {'data': data, 'time': now}
    return data


def html_anchor_items(html_text, href_regex, date_regex=None, limit=50,
                      link_prefix='', title_attr=True):
    """Extract (title, href, date) triples from an HTML list page.

    href_regex must capture the href in group 1 and the anchor text in group 2.
    date_regex (optional) captures a date in group 1 from the surrounding text.
    """
    items = []
    seen = set()
    for match in re.finditer(href_regex, html_text, re.DOTALL):
        href, title = match.group(1), re.sub(r'<[^>]+>', '', match.group(2))
        title = unescape(re.sub(r'\s+', ' ', title)).strip()
        if not title or href in seen or href.startswith('#') or href.startswith('javascript'):
            continue
        seen.add(href)
        date_str = None
        if date_regex:
            tail = html_text[match.end():match.end() + 400]
            date_match = re.search(date_regex, tail)
            if date_match:
                date_str = date_match.group(1)
        items.append({'title': title, 'link': link_prefix + href, 'date': date_str})
        if len(items) >= limit:
            break
    return items


def parse_date_or_now(date_str):
    """Parse 'YYYY-MM-DD' or 'YYYY/MM/DD' into RFC 822; fall back to now."""
    if date_str:
        normalized = date_str.replace('/', '-')
        for fmt in ('%Y-%m-%d',):
            try:
                dt = datetime.strptime(normalized, fmt).replace(tzinfo=timezone(timedelta(hours=8)))
                return formatdate(timeval=dt.timestamp(), localtime=False, usegmt=True)
            except ValueError:
                pass
    return formatdate(timeval=None, localtime=False, usegmt=True)


def items_to_rss(feed_title, feed_link, feed_desc, items, feed_url=None, guid_prefix='src'):
    """Turn (title, link, date[, description]) dicts into an RSS feed."""
    rss_items = []
    for index, item in enumerate(items):
        rss_items.append({
            'title': item['title'],
            'link': item['link'],
            'description': item.get('description') or item['title'],
            'pubDate': parse_date_or_now(item.get('date')),
            'guid': f"{guid_prefix}_{hashlib.md5(item['link'].encode('utf-8')).hexdigest()[:12]}_{index}",
        })
    return generate_rss(feed_title, feed_link, feed_desc, rss_items, feed_url=feed_url)


def handle_csrc_news(feed_url=None):
    """CSRC news releases (中国证监会新闻发布)."""
    url = 'https://www.csrc.gov.cn/csrc/c100028/common_list.shtml'
    html_text = fetch_text(url)
    items = html_anchor_items(
        html_text,
        r'<a\s+href="(/csrc/[^"]*content\.shtml)"[^>]*>(.*?)</a>',
        date_regex=r'<span\s+class="date">([0-9]{4}-[0-9]{2}-[0-9]{2})</span>',
        limit=50,
        link_prefix='https://www.csrc.gov.cn',
    )
    return items_to_rss('中国证监会', 'https://www.csrc.gov.cn/csrc/c100028/common_list.shtml',
                        '中国证监会新闻发布与监管执法', items, feed_url=feed_url, guid_prefix='csrc')


def handle_pbc_news(feed_url=None):
    """PBoC news releases (中国人民银行新闻)."""
    url = 'https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/index.html'
    html_text = fetch_text(url)
    items = html_anchor_items(
        html_text,
        r'<a\s+href="(/goutongjiaoliu/113456/113469/[^"]*/index\.html)"[^>]*>(.*?)</a>',
        date_regex=r'<span\s+class="hui12">([0-9]{4}-[0-9]{2}-[0-9]{2})</span>',
        limit=50,
        link_prefix='https://www.pbc.gov.cn',
    )
    return items_to_rss('中国人民银行', 'https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/index.html',
                        '中国人民银行货币政策与新闻发布', items, feed_url=feed_url, guid_prefix='pbc')


def handle_ndrc_news(feed_url=None):
    """NDRC news releases (国家发展改革委新闻发布)."""
    url = 'https://www.ndrc.gov.cn/xwdt/xwfb/index.html'
    html_text = fetch_text(url)
    items = html_anchor_items(
        html_text,
        r'<a\s+href="(\./20[0-9]{4}/t[0-9_]+\.html)"[^>]*>(.*?)</a>',
        date_regex=r'<span>([0-9]{4}/[0-9]{2}/[0-9]{2})</span>',
        limit=50,
        link_prefix='https://www.ndrc.gov.cn/xwdt/xwfb/',
    )
    return items_to_rss('国家发展改革委', 'https://www.ndrc.gov.cn/xwdt/xwfb/index.html',
                        '国家发展改革委新闻发布与政策文件', items, feed_url=feed_url, guid_prefix='ndrc')


def handle_sina_roll(feed_url=None):
    """Sina Finance rolling news (新浪财经滚动新闻)."""
    url = 'https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2515&k=&num=50&page=1'
    data = json.loads(fetch_text(url))
    items = []
    for entry in data.get('result', {}).get('data', []):
        items.append({
            'title': entry.get('title', ''),
            'link': entry.get('url', ''),
            'description': entry.get('title', ''),
            'date': None,
            '_ts': int(entry.get('ctime', 0) or 0),
        })
    rss_items = []
    for index, item in enumerate(items):
        rss_items.append({
            'title': item['title'],
            'link': item['link'],
            'description': item['description'],
            'pubDate': timestamp_to_rfc822(item.get('_ts', 0)),
            'guid': f"sina_{hashlib.md5(item['link'].encode('utf-8')).hexdigest()[:12]}_{index}",
        })
    return generate_rss('新浪财经滚动', 'https://finance.sina.com.cn/',
                        '新浪财经7x24滚动新闻', rss_items, feed_url=feed_url)


def handle_cnstock_news(feed_url=None):
    """Cnstock (上证报) latest news via __NEXT_DATA__."""
    url = 'https://news.cnstock.com/'
    html_text = fetch_text(url)
    match = re.search(r'__NEXT_DATA__[^>]*>(.*?)</script>', html_text, re.DOTALL)
    if not match:
        return generate_rss('上海证券报', 'https://news.cnstock.com/', '上海证券报新闻', [], feed_url=feed_url)
    payload = json.loads(match.group(1))
    groups = payload.get('props', {}).get('pageProps', {}).get('data', {}).get('pageInfo', {}).get('list', [])
    current_year = datetime.now().year
    items = []
    for group in groups:
        for child in group.get('childList', []):
            name = (child.get('name') or '').strip()
            cont_id = child.get('contId') or ''
            pub_time = (child.get('pubTime') or '').strip()
            summary = strip_html(child.get('summary') or '')
            if not name or not cont_id:
                continue
            items.append({
                'title': name,
                'link': f'https://news.cnstock.com/news/detail?contId={cont_id}',
                'description': summary or name,
                'date': f'{current_year}-{pub_time}' if re.match(r'^[0-9]{2}-[0-9]{2}$', pub_time) else None,
            })
            if len(items) >= 50:
                break
        if len(items) >= 50:
            break
    return items_to_rss('上海证券报', 'https://news.cnstock.com/', '上海证券报（中国证券网）新闻',
                        items, feed_url=feed_url, guid_prefix='cnstock')


# ── HTTP Server ──────────────────────────────────────────────────────────────

ROUTES = {
    '/cls/telegraph': ('CLS Telegraph (财联社电报)', handle_cls_telegraph),
    '/eastmoney/kuaixun': ('Eastmoney News (东方财富快讯)', handle_eastmoney_kuaixun),
    '/ths/kuaixun': ('THS News (同花顺快讯)', handle_ths_kuaixun),
    '/jin10/flash': ('Jin10 Flash (金十快讯)', handle_jin10_flash),
    '/wallstreetcn/live': ('Wallstreetcn Live (华尔街见闻快讯)', handle_wallstreetcn_live),
    '/csrc': ('CSRC News (中国证监会)', handle_csrc_news),
    '/pbc': ('PBoC News (中国人民银行)', handle_pbc_news),
    '/ndrc': ('NDRC News (国家发展改革委)', handle_ndrc_news),
    '/sina/roll': ('Sina Finance Roll (新浪财经)', handle_sina_roll),
    '/cnstock': ('Cnstock News (上海证券报)', handle_cnstock_news),
}

ROUTE_META = {
    '/cls/telegraph': ('财联社电报', 'https://www.cls.cn/telegraph', '财联社实时快讯'),
    '/eastmoney/kuaixun': ('东方财富快讯', 'https://kuaixun.eastmoney.com/', '东方财富7x24快讯'),
    '/ths/kuaixun': ('同花顺快讯', 'https://news.10jqka.com.cn/', '同花顺7x24快讯'),
    '/jin10/flash': ('金十快讯', 'https://www.jin10.com/', '金十数据7x24快讯'),
    '/wallstreetcn/live': ('华尔街见闻快讯', 'https://wallstreetcn.com/live', '华尔街见闻7x24快讯'),
    '/csrc': ('中国证监会', 'https://www.csrc.gov.cn/csrc/c100028/common_list.shtml', '证监会新闻发布与监管执法'),
    '/pbc': ('中国人民银行', 'https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/index.html', '央行货币政策与新闻发布'),
    '/ndrc': ('国家发展改革委', 'https://www.ndrc.gov.cn/xwdt/xwfb/index.html', '发改委新闻发布与政策文件'),
    '/sina/roll': ('新浪财经滚动', 'https://finance.sina.com.cn/', '新浪财经7x24滚动新闻'),
    '/cnstock': ('上海证券报', 'https://news.cnstock.com/', '上海证券报新闻'),
}


def count_rss_items(xml):
    """Return the number of RSS items in a generated feed."""
    root = ET.fromstring(xml)
    return len(root.findall('./channel/item'))


def build_health_payload(base_url, check_sources=False):
    """Build a JSON-serializable health payload."""
    feeds = []
    status = 'ok'

    for path, (name, handler) in ROUTES.items():
        entry = {
            'name': name,
            'path': path,
            'url': base_url + path,
            'status': 'configured',
        }

        if check_sources:
            try:
                xml = handler(feed_url=base_url + path)
                entry['status'] = 'ok'
                entry['items'] = count_rss_items(xml)
            except Exception as exc:
                entry['status'] = 'error'
                entry['error'] = str(exc)
                status = 'degraded'

        feeds.append(entry)

    feeds.append({
        'name': 'Xueqiu User Example (雪球)',
        'path': '/xueqiu/user/1247347556',
        'url': base_url + '/xueqiu/user/1247347556',
        'status': 'requires_chrome_cdp',
    })

    return {
        'status': status,
        'cache_ttl': CACHE_TTL,
        'request_timeout': REQUEST_TIMEOUT,
        'feeds': feeds,
    }


class RSSHandler(BaseHTTPRequestHandler):
    """HTTP request handler for RSS feeds."""

    def log_message(self, format, *args):
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")

    def do_HEAD(self):
        self._handle_request(write_body=False)

    def do_GET(self):
        self._handle_request(write_body=True)

    def _handle_request(self, write_body=True):
        parsed = urlparse(self.path)
        path = parsed.path
        base_url = self._base_url()

        if path == '/':
            self._serve_index(write_body=write_body)
            return
        if path == '/opml.xml':
            self._send_text(200, 'text/x-opml; charset=utf-8',
                            generate_opml(base_url), write_body=write_body)
            return
        if path == '/healthz':
            query = parse_qs(parsed.query)
            check_sources = query.get('check', ['0'])[0] in ('1', 'true', 'yes')
            payload = build_health_payload(base_url, check_sources=check_sources)
            status_code = 503 if payload['status'] == 'degraded' else 200
            body = json.dumps(payload, ensure_ascii=False, indent=2)
            self._send_text(status_code, 'application/json; charset=utf-8',
                            body, cache=False, write_body=write_body)
            return
        if path in ROUTES:
            self._serve_feed(path, base_url, write_body=write_body)
            return
        if path.startswith('/xueqiu/user/'):
            uid = path.split('/')[-1]
            feed_url = base_url + path
            xml = handle_xueqiu_user(uid, feed_url=feed_url)
            self._send_text(200, 'application/rss+xml; charset=utf-8',
                            xml, write_body=write_body)
            return

        self.send_error(404, 'Not Found. Visit / for available feeds.')

    def _serve_feed(self, path, base_url, write_body=True):
        _, handler = ROUTES[path]
        feed_url = base_url + path
        try:
            xml = handler(feed_url=feed_url)
        except Exception as exc:
            title, link, description = ROUTE_META[path]
            xml = generate_error_rss(title, link, description, exc, feed_url=feed_url)

        self._send_text(200, 'application/rss+xml; charset=utf-8',
                        xml, write_body=write_body)

    def _base_url(self):
        if PUBLIC_BASE_URL:
            return PUBLIC_BASE_URL
        proto = self.headers.get('X-Forwarded-Proto', 'http').split(',')[0].strip()
        host = self.headers.get('X-Forwarded-Host') or self.headers.get('Host')
        return f'{proto}://{host or f"localhost:{PORT}"}'.rstrip('/')

    def _send_text(self, status_code, content_type, body, cache=True, write_body=True):
        body_bytes = body.encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body_bytes)))
        if cache:
            self.send_header('Cache-Control', f'public, max-age={CACHE_TTL}')
        self.end_headers()
        if write_body:
            self.wfile.write(body_bytes)

    def _serve_index(self, write_body=True):
        """Serve a simple index page listing available feeds."""
        lines = ['<html><head><title>China Finance RSS Bridge</title></head>',
                 '<body><h1>🇨🇳 China Finance RSS Bridge</h1><ul>']
        for path, (name, _) in ROUTES.items():
            lines.append(f'<li><a href="{path}">{name}</a></li>')
        lines.append(f'<li><a href="/xueqiu/user/1247347556">Xueqiu User Example (雪球)</a></li>')
        lines.append('</ul><p><a href="/opml.xml">Import OPML</a> | '
                     '<a href="/healthz?check=1">Source check</a></p>')
        lines.append('<p>Add any URL above to your RSS reader.</p></body></html>')
        html = '\n'.join(lines)
        self._send_text(200, 'text/html; charset=utf-8', html,
                        cache=False, write_body=write_body)


def main():
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    print(f'China Finance RSS Bridge running on http://localhost:{PORT}')
    print(f'Cache TTL: {CACHE_TTL}s | Timeout: {REQUEST_TIMEOUT}s | CDP: {CDP_URL}\n')
    print('Available feeds:')
    for path, (name, _) in ROUTES.items():
        print(f'  http://localhost:{PORT}{path}  — {name}')
    print(f'  http://localhost:{PORT}/xueqiu/user/{{uid}}  — Xueqiu User (雪球)')
    print(f'\nUtilities:')
    print(f'  http://localhost:{PORT}/opml.xml  — OPML subscription list')
    print(f'  http://localhost:{PORT}/healthz?check=1  — Source health check')
    print(f'\nNote: Xueqiu requires Chrome with CDP enabled + a logged-in Xueqiu tab.')
    print(f'Visit http://localhost:{PORT}/ for the web index.\n')

    server = HTTPServer(('0.0.0.0', PORT), RSSHandler)
    server.serve_forever()


if __name__ == '__main__':
    main()
