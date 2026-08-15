# -*- coding: utf-8 -*-
"""链接评估：抓取链接公开内容 + 关键词分析，生成提示性《资料评估报告》。

说明：本模块只做“提示”，不替用户做决定。
"""

import re

import requests
from bs4 import BeautifulSoup

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# ------- 关键词规则 -------
SELL_KEYWORDS = [
    "卖", "出售", "出资料", "转卖", "付费", "价格", "¥", "元", "下单",
    "购买", "私信", "课程", "真题", "笔记", "资料", "讲义", "模板", "有偿",
]

TYPE_RULES = [
    ("真题", ["真题"]),
    ("笔记/整理", ["笔记", "手写", "整理", "重点", "浓缩"]),
    ("课程/带学", ["课程", "网课", "视频课", "带学", "跟学", "直播", "精讲"]),
    ("经验帖/规划", ["经验", "上岸", "心得", "避坑", "规划", "攻略"]),
    ("资料合集/电子版", ["资料", "合集", "电子版", "pdf", "讲义", "模板"]),
]

LEAD_GEN_KEYWORDS = [
    "私信我", "私信", "私我", "加V", "加v", "加微信", "评论区见", "评论区扣",
    "扣1", "扣 1", "扣一", "关注后", "主页", "滴滴", "蹲一个", "蹲", "来找我",
    "全套找我", "dd我", "DD我", "评论区留言", "留言区", "想买的扣", "公众号",
]

FREE_KEYWORDS = [
    "免费", "分享", "网盘", "提取码", "pdf", "PDF", "无偿", "白嫖", "免费送",
]

EXAGGERATION_KEYWORDS = [
    "全网最全", "最全", "独家", "绝版", "押题", "命中", "必考", "必中",
    "保过", "包过", "原题", "内部", "泄露", "天花板", "无敌", "第一",
    "压中", "直出",
]

# 从整段文字里提取 http/https 链接（排除中文标点，避免把标题当链接）
URL_PATTERN = re.compile(
    r"https?://[^\s，。、；;：:“”‘’（）()<>《》【】\[\]！!？?]+",
    re.IGNORECASE,
)


def extract_links(text):
    """从用户粘贴的整段文字中提取所有 http/https 链接。"""
    links = URL_PATTERN.findall(text or "")
    cleaned = []
    for link in links:
        cleaned.append(link.rstrip(".,;:!?，。；：！？"))
    return cleaned


def fetch_link_content(url):
    """尽力抓取链接的公开内容（标题/正文/图片说明）。

    小红书等平台限制访问时返回失败，不做多次重试，由用户手动补充内容。
    """
    empty = {"ok": False, "reason": "", "title": "", "desc": "", "imgs": []}
    url = (url or "").strip()
    if not url:
        return {**empty, "reason": "没有输入链接"}
    if not url.startswith(("http://", "https://")):
        return {**empty, "reason": "链接格式不正确（请以 http:// 或 https:// 开头）"}

    headers = {
        "User-Agent": BROWSER_UA,
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=8, allow_redirects=True)
    except requests.RequestException:
        return {**empty, "reason": "自动抓取失败（网络问题或对方网站拒绝访问）"}
    if resp.status_code != 200:
        return {
            **empty,
            "reason": f"自动抓取失败（网站返回状态码 {resp.status_code}，可能限制了访问）",
        }

    soup = BeautifulSoup(resp.text[:300000], "lxml")
    title = ""
    og = soup.find("meta", attrs={"property": "og:title"})
    if og and og.get("content"):
        title = og["content"].strip()
    else:
        tag = soup.find("title")
        if tag:
            title = tag.get_text(" ", strip=True)

    desc = ""
    ogd = soup.find("meta", attrs={"property": "og:description"})
    if ogd and ogd.get("content"):
        desc = ogd["content"].strip()
    else:
        md = soup.find("meta", attrs={"name": "description"})
        if md and md.get("content"):
            desc = md["content"].strip()

    imgs = [img.get("alt", "").strip() for img in soup.find_all("img") if img.get("alt")]

    page_text = soup.get_text(" ", strip=True)
    if len(page_text) < 60 or ("登录" in title and "小红书" in title):
        return {
            **empty,
            "reason": "抓取到的页面是登录/验证页，拿不到帖子正文（小红书限制访问）",
        }

    return {
        "ok": True,
        "reason": "",
        "title": title,
        "desc": desc,
        "imgs": imgs[:10],
    }


def merge_content(fetch_result, manual):
    """把自动抓到的内容与用户手动补充的内容合并成一段文本。"""
    parts = []
    if fetch_result.get("ok"):
        if fetch_result.get("title"):
            parts.append(f"【标题】{fetch_result['title']}")
        if fetch_result.get("desc"):
            parts.append(f"【正文/简介】{fetch_result['desc']}")
        if fetch_result.get("imgs"):
            parts.append("【图片说明】" + "；".join(fetch_result["imgs"]))
    manual = (manual or "").strip()
    if manual:
        parts.append(f"【用户补充】{manual}")
    return "\n".join(parts)


def _hits(text, keywords):
    """找出命中的关键词，并去重：包含关系或同词不同大小写只保留一个。"""
    low_text = text.lower()
    found = []
    for kw in keywords:
        k = kw.lower()
        if k not in low_text:
            continue
        # 已被更长/相同的词覆盖则跳过（如 私信 ⊂ 私信我；加V = 加v；PDF = pdf）
        if any(k in f.lower() for f in found):
            continue
        found.append(kw)
    return found


def evaluate(text):
    """对合并后的内容做关键词分析，生成提示性《资料评估报告》。"""
    text = (text or "").strip()
    selling = any(k in text for k in SELL_KEYWORDS) if text else None

    type_guess = "未识别出具体类型"
    if text:
        for name, kws in TYPE_RULES:
            if any(k in text for k in kws):
                type_guess = name
                break

    lead_gen = _hits(text, LEAD_GEN_KEYWORDS)
    exaggeration = _hits(text, EXAGGERATION_KEYWORDS)
    free_hints = _hits(text, FREE_KEYWORDS)

    if not text:
        verdict, level = "公开信息较少，请谨慎判断", "orange"
    elif lead_gen or exaggeration:
        verdict, level = "存在引流特征，请谨慎判断", "red"
    elif not selling or len(text) < 60:
        verdict, level = "公开信息较少，请谨慎判断", "orange"
    else:
        verdict, level = "来源清晰，内容较完整", "green"

    return {
        "text": text,
        "is_selling": selling,
        "type_guess": type_guess,
        "lead_gen": lead_gen,
        "exaggeration": exaggeration,
        "free_hints": free_hints,
        "verdict": verdict,
        "level": level,
    }
