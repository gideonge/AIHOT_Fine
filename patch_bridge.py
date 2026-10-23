# -*- coding: utf-8 -*-
"""Patch finance-rss server.py: add CSRC / PBC / NDRC / Sina / Cnstock handlers."""
import io, re

path = r"D:/workspace/aihot-finance/finance-rss-server.py"
s = io.open(path, encoding="utf-8").read()

NEW_HELPERS = '''

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
        title = unescape(re.sub(r'\\s+', ' ', title)).strip()
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
        r'<a\\s+href="(/csrc/[^"]*content\\.shtml)"[^>]*>(.*?)</a>',
        date_regex=r'<span\\s+class="date">([0-9]{4}-[0-9]{2}-[0-9]{2})</span>',
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
        r'<a\\s+href="(/goutongjiaoliu/113456/113469/[^"]*/index\\.html)"[^>]*>(.*?)</a>',
        date_regex=r'<span\\s+class="hui12">([0-9]{4}-[0-9]{2}-[0-9]{2})</span>',
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
        r'<a\\s+href="(\\./20[0-9]{4}/t[0-9_]+\\.html)"[^>]*>(.*?)</a>',
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

'''

# Insert new handlers right before the HTTP server section.
marker = "# ── HTTP Server ──────────────────────────────────────────────────────────────"
assert marker in s, "HTTP server marker not found"
s = s.replace(marker, NEW_HELPERS + "\n" + marker, 1)

# Extend ROUTES.
old_routes = """ROUTES = {
    '/cls/telegraph': ('CLS Telegraph (财联社电报)', handle_cls_telegraph),
    '/eastmoney/kuaixun': ('Eastmoney News (东方财富快讯)', handle_eastmoney_kuaixun),
    '/ths/kuaixun': ('THS News (同花顺快讯)', handle_ths_kuaixun),
    '/jin10/flash': ('Jin10 Flash (金十快讯)', handle_jin10_flash),
    '/wallstreetcn/live': ('Wallstreetcn Live (华尔街见闻快讯)', handle_wallstreetcn_live),
}"""
new_routes = """ROUTES = {
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
}"""
assert old_routes in s, "ROUTES block not found"
s = s.replace(old_routes, new_routes, 1)

old_meta = """ROUTE_META = {
    '/cls/telegraph': ('财联社电报', 'https://www.cls.cn/telegraph', '财联社实时快讯'),
    '/eastmoney/kuaixun': ('东方财富快讯', 'https://kuaixun.eastmoney.com/', '东方财富7x24快讯'),
    '/ths/kuaixun': ('同花顺快讯', 'https://news.10jqka.com.cn/', '同花顺7x24快讯'),
    '/jin10/flash': ('金十快讯', 'https://www.jin10.com/', '金十数据7x24快讯'),
    '/wallstreetcn/live': ('华尔街见闻快讯', 'https://wallstreetcn.com/live', '华尔街见闻7x24快讯'),
}"""
new_meta = """ROUTE_META = {
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
}"""
assert old_meta in s, "ROUTE_META block not found"
s = s.replace(old_meta, new_meta, 1)

# Update module docstring source list.
s = s.replace(
    "Sources: CLS (财联社), Eastmoney (东方财富), THS (同花顺), Xueqiu (雪球)",
    "Sources: CLS (财联社), Eastmoney (东方财富), THS (同花顺), Jin10, Wallstreetcn, CSRC (证监会), PBoC (央行), NDRC (发改委), Sina Finance (新浪财经), Cnstock (上证报)",
)

io.open(path, "w", encoding="utf-8").write(s)
print("patched OK")
