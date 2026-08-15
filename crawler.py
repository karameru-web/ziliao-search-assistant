# -*- coding: utf-8 -*-
"""抓取模块：B站视频 / B站专栏 / Bing 网页 / 知乎（经 Bing site: 限定）"""

import base64
import re
import time
import urllib.parse

import requests
from bs4 import BeautifulSoup

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

BILI_HEADERS = {
    "User-Agent": BROWSER_UA,
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

BING_HEADERS = {
    "User-Agent": BROWSER_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
}

TAG_HTML_RE = re.compile(r"<[^>]+>")


def clean_title(text):
    """去掉 B站 标题里的 <em class='keyword'> 等 HTML 标签。"""
    if not text:
        return ""
    return TAG_HTML_RE.sub("", text).strip()


def _new_bili_session():
    """初始化 B站 会话：先访问首页拿 buvid 等 cookie，降低 -412 风险。"""
    session = requests.Session()
    session.headers.update(BILI_HEADERS)
    try:
        session.get("https://www.bilibili.com/", timeout=15)
    except requests.RequestException:
        pass
    return session


def _search_all_v2(session, keyword, page):
    url = "https://api.bilibili.com/x/web-interface/search/all/v2"
    try:
        resp = session.get(url, params={"keyword": keyword, "page": page}, timeout=20)
        return resp.json()
    except (requests.RequestException, ValueError):
        return {}


def _search_type(session, keyword, page, search_type):
    """备用接口：分别按类型搜索（video / article）。"""
    url = "https://api.bilibili.com/x/web-interface/search/type"
    try:
        resp = session.get(
            url,
            params={"search_type": search_type, "keyword": keyword, "page": page},
            timeout=20,
        )
        return resp.json()
    except (requests.RequestException, ValueError):
        return {}


def _article_url(item):
    """B站 search/type 的专栏结果没有 url 字段，需要按 id 拼链接。"""
    return item.get("url") or (
        f"https://www.bilibili.com/read/cv{item['id']}" if item.get("id") else ""
    )


def fetch_bilibili(
    keyword,
    pages=3,
    article_limit=30,
    delay=2.0,
    progress_cb=None,
    title_filter=None,
    deadline=None,
):
    """抓取 B站 视频 + 专栏，返回 (视频列表, 专栏列表, 警告列表)。

    视频走 all/v2（每页 20 条）；专栏走 search/type?search_type=article，
    因为 all/v2 常常不带专栏区块。
    """
    videos, articles, warnings = [], [], []
    seen_video_urls = set()
    session = _new_bili_session()

    for page in range(1, pages + 1):
        if deadline and time.time() > deadline:
            break
        v0 = len(videos)
        data = _search_all_v2(session, keyword, page)
        code = data.get("code")
        if code == -412:
            warnings.append(f"B站第 {page} 页触发 -412 风控，重新初始化会话后重试")
            time.sleep(delay)
            session = _new_bili_session()
            data = _search_all_v2(session, keyword, page)

        code = data.get("code")
        if code == 0 and data.get("data"):
            for section in data["data"].get("result", []):
                rtype = section.get("result_type")
                if rtype == "video":
                    for item in section.get("data") or []:
                        title = clean_title(item.get("title") or "")
                        url = item.get("arcurl") or ""
                        if not title or url in seen_video_urls:
                            continue
                        if title_filter and not title_filter(title):
                            continue
                        seen_video_urls.add(url)
                        videos.append(
                            {
                                "source": "B站视频",
                                "title": title,
                                "url": url,
                                "desc": (item.get("description") or "").strip(),
                            }
                        )
        else:
            warnings.append(f"B站 all/v2 第 {page} 页返回 code={code}，视频改用 search/type 备用接口")
            for item in (data.get("data") or {}).get("result") or []:
                title = clean_title(item.get("title") or "")
                url = item.get("arcurl") or ""
                if not title or url in seen_video_urls:
                    continue
                if title_filter and not title_filter(title):
                    continue
                seen_video_urls.add(url)
                videos.append(
                    {
                        "source": "B站视频",
                        "title": title,
                        "url": url,
                        "desc": (item.get("description") or "").strip(),
                    }
                )
        if progress_cb:
            added = len(videos) - v0
            if added:
                progress_cb(added)
        time.sleep(delay)

    # 专栏：显式按类型抓前 3 页
    seen_article_urls = set()
    for page in range(1, pages + 1):
        if deadline and time.time() > deadline:
            break
        a0 = len(articles)
        d2 = _search_type(session, keyword, page, "article")
        if d2.get("code") == -412:
            warnings.append(f"B站专栏第 {page} 页触发 -412，重新初始化会话后重试")
            time.sleep(delay)
            session = _new_bili_session()
            d2 = _search_type(session, keyword, page, "article")
        for item in (d2.get("data") or {}).get("result") or []:
            title = clean_title(item.get("title") or "")
            url = _article_url(item)
            if not title or not url or url in seen_article_urls:
                continue
            if title_filter and not title_filter(title):
                continue
            seen_article_urls.add(url)
            articles.append(
                {
                    "source": "B站专栏",
                    "title": title,
                    "url": url,
                    "desc": (item.get("desc") or item.get("summary") or "").strip(),
                }
            )
            if len(articles) >= article_limit:
                break
        if progress_cb:
            added = len(articles) - a0
            if added:
                progress_cb(added)
        if len(articles) >= article_limit:
            break
        time.sleep(delay)

    return videos, articles, warnings


def _bing_real_url(href):
    """把 Bing 的 /ck/a 跳转链接还原成真实网址。"""
    if "bing.com/ck/a" not in href:
        return href
    params = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
    u = (params.get("u") or [None])[0]
    if u:
        try:
            padded = u + "=" * (-len(u) % 4)
            decoded = base64.urlsafe_b64decode(padded).decode("utf-8", "ignore")
            if decoded.startswith("http"):
                return decoded
        except Exception:
            pass
    return href


def _fetch_bing_page(query, first, site):
    """抓取一页 Bing 结果，返回 (条目列表, 是否疑似被拦截)。"""
    url = "https://www.bing.com/search"
    try:
        resp = requests.get(
            url,
            params={"q": query, "first": first},
            headers=BING_HEADERS,
            timeout=20,
        )
    except requests.RequestException:
        return [], True

    if resp.status_code != 200 or "b_algo" not in resp.text:
        return [], True

    soup = BeautifulSoup(resp.text, "lxml")
    items = []
    for li in soup.select("li.b_algo"):
        a = li.select_one("h2 a")
        if not a:
            continue
        title = a.get_text(" ", strip=True)
        href = _bing_real_url(a.get("href") or "")
        if site and site not in href:
            continue
        if not title or not href.startswith("http"):
            continue
        snippet_el = li.select_one(".b_caption p") or li.select_one("p")
        snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
        items.append(
            {
                "source": "知乎" if site else "Bing网页",
                "title": title,
                "url": href,
                "desc": snippet,
            }
        )
    return items, False


def fetch_bing(
    keyword,
    site=None,
    pages=3,
    per_page=10,
    delay=2.0,
    progress_cb=None,
    title_filter=None,
    deadline=None,
):
    """抓取 Bing 网页（可选 site 限定），返回 (结果列表, 警告列表)。"""
    results, warnings = [], []
    for first in range(1, pages * per_page, per_page):
        if deadline and time.time() > deadline:
            break
        before = len(results)
        query = keyword if not site else f"{keyword} site:{site}"
        items, blocked = _fetch_bing_page(query, first, site)
        if not items and blocked:
            warnings.append(f"{'知乎' if site else 'Bing'} 第 {first} 页疑似被反爬拦截，等待后重试")
            time.sleep(delay)
            items, _ = _fetch_bing_page(query, first, site)
        for item in items:
            if title_filter and not title_filter(item["title"]):
                continue
            results.append(item)
        if progress_cb:
            added = len(results) - before
            if added:
                progress_cb(added)
        time.sleep(delay)
    return results, warnings


def fetch_zhihu(
    keyword,
    pages=3,
    target=20,
    delay=2.0,
    progress_cb=None,
    title_filter=None,
    deadline=None,
):
    """通过 Bing 抓知乎：Bing 的 site: 限定每页只混入少量知乎链接，
    所以组合三种查询写法，并按网址去重，尽量凑到 20 条。"""
    results, warnings = [], []
    seen = set()
    variants = [
        f"{keyword} site:zhihu.com",
        f"{keyword} 知乎",
        f"{keyword} 知乎 讨论",
        f"{keyword.replace(' ', '')} 知乎",
    ]
    for variant in variants:
        if deadline and time.time() > deadline:
            break
        if len(results) >= target:
            break
        for first in range(1, pages * 10, 10):
            if deadline and time.time() > deadline:
                break
            if len(results) >= target:
                break
            before = len(results)
            items, blocked = _fetch_bing_page(variant, first, "zhihu.com")
            if not items and blocked:
                warnings.append(f"知乎搜索（{variant[:20]}…）第 {first} 页疑似被拦截，等待后重试")
                time.sleep(delay)
                items, _ = _fetch_bing_page(variant, first, "zhihu.com")
            for item in items:
                if title_filter and not title_filter(item["title"]):
                    continue
                if item["url"] not in seen:
                    seen.add(item["url"])
                    results.append(item)
                if len(results) >= target:
                    break
            if progress_cb:
                added = len(results) - before
                if added:
                    progress_cb(added)
            time.sleep(delay)
    return results, warnings


if __name__ == "__main__":
    import json

    kw = "考研英语 真题"
    vs, arts, warns = fetch_bilibili(kw)
    bing, bw = fetch_bing(kw)
    zhihu, zw = fetch_bing(kw, site="zhihu.com", pages=2)
    print(json.dumps(
        {
            "video": len(vs),
            "article": len(arts),
            "bing": len(bing),
            "zhihu": len(zhihu),
            "warnings": warns + bw + zw,
            "samples": (vs + arts + bing + zhihu)[:5],
        },
        ensure_ascii=False,
        indent=2,
    ))
