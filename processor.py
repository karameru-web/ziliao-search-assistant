# -*- coding: utf-8 -*-
"""打标签 / 去重 / 贪心聚类 模块"""

import difflib
import re
from collections import Counter

TAG_RULES = [
    ("免费可下", ["网盘", "提取码", "下载", "PDF", "分享"]),
    ("引流私信", ["私信", "加V", "加微信", "公众号", "完整版找我"]),
    ("付费购买", ["购买", "价格", "¥", "元", "课程", "下单"]),
]

TAG_CSS = {
    "免费可下": "text-bg-success",
    "引流私信": "text-bg-warning",
    "付费购买": "text-bg-danger",
}

TAG_PRIORITY = {"付费购买": 3, "引流私信": 2, "免费可下": 1}

QUALITY_RULES = [
    ("AI生成", ["首先", "其次", "综上所述", "一方面", "另一方面", "值得一提的是"]),
    ("经验帖", ["上岸", "心得", "学长", "学姐", "经验分享", "二战"]),
    ("机构广告", ["机构", "报名", "试听", "保过", "协议班", "辅导班"]),
]

# 旧年份只取 2020-2024：避免把“历年真题年份”（如 1998-2018）误判为过时
OLD_YEARS = {"2020", "2021", "2022", "2023", "2024"}
NEW_YEARS = {"2025", "2026"}


def normalize_title(title):
    """规范化标题用于相似度比较：去掉【...】、括号、数字和标点。"""
    t = (title or "").lower()
    t = re.sub(r"【[^】]*】", " ", t)
    t = re.sub(r"[（(][^）)]*[)）]", " ", t)
    t = re.sub(r"\d+", " ", t)
    t = re.sub(r"[\W_]+", "", t)
    return t.strip()


def tag_names(entry):
    """按关键词规则给单条结果打标签，返回标签名列表。"""
    text = f"{entry.get('title', '')} {entry.get('desc', '')}"
    return [name for name, keywords in TAG_RULES if any(k in text for k in keywords)]


def quality_assess(entry):
    """质量标签（可多选）+ 1~5 星评分。"""
    title = entry.get("title", "")
    text = f"{title} {entry.get('desc', '')}"
    tags = []
    for name, keywords in QUALITY_RULES:
        if any(k in text for k in keywords):
            tags.append(name)
    years = set(re.findall(r"20\d{2}", title))
    if years & OLD_YEARS and not years & NEW_YEARS:
        tags.append("可能过时")

    stars = 3
    if "经验帖" in tags:
        stars += 1
    for bad in ("AI生成", "可能过时", "机构广告"):
        if bad in tags:
            stars -= 1
    stars = max(1, min(5, stars))
    return tags, stars


def _tag_dict(name):
    return {"name": name, "css": TAG_CSS.get(name, "text-bg-secondary")}


def similarity(a, b):
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def deduplicate(entries, threshold=0.8):
    """对全部标题两两比较，相似度 > 0.8 的标记为重复（并查集合并成组）。

    返回若干个组，每组第一个条目是主条目，其余是折叠隐藏的重复项。
    """
    n = len(entries)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n):
        for j in range(i + 1, n):
            if similarity(entries[i]["title"], entries[j]["title"]) > threshold:
                union(i, j)

    groups = {}
    for i, entry in enumerate(entries):
        groups.setdefault(find(i), []).append(entry)
    return list(groups.values())


def _greedy_cluster(main_entries, threshold):
    """贪心聚类：与已有簇代表标题（规范化后）相似度 > threshold 则并入。"""
    clusters = []
    for entry in main_entries:
        norm = normalize_title(entry["title"])
        best = None
        best_ratio = threshold
        for c in clusters:
            r = similarity(norm, c["norm_rep"])
            if r > best_ratio:
                best = c
                best_ratio = r
        if best is not None:
            best["main"].append(entry)
        else:
            clusters.append(
                {"rep_title": entry["title"], "norm_rep": norm, "main": [entry]}
            )
    return clusters


def _pick_rep_title(titles):
    """在簇内挑一个“最典型”的标题：与簇内其他标题平均相似度最高。"""
    norms = [normalize_title(t) for t in titles]
    best_title, best_score = titles[0], -1.0
    for i, title in enumerate(titles):
        score = sum(similarity(norms[i], n) for n in norms if n)
        # 标题更长往往描述更完整，作为代表更清晰，给少量加分
        score += min(len(title), 40) * 0.01
        if score > best_score:
            best_score = score
            best_title = title
    return best_title


TOPIC_PRIORITY = [
    ("老师·田静", ["田静"]),
    ("老师·唐迟", ["唐迟"]),
    ("老师·颉斌斌", ["颉斌斌"]),
    ("老师·刘晓艳", ["刘晓艳"]),
    ("老师·张剑", ["张剑"]),
    ("题型·阅读", ["阅读"]),
    ("题型·翻译", ["翻译"]),
    ("题型·完形", ["完形", "完型"]),
    ("题型·单词", ["单词", "词汇", "词根"]),
    ("题型·作文", ["作文"]),
    ("形态·电子版下载", ["电子版", "pdf", "网盘", "提取码", "下载", "无水印"]),
    ("形态·在线刷题", ["在线", "官网", "刷题", "模考"]),
    ("话题·书测评", ["黄皮书", "考研真相", "测评", "怎么选"]),
    ("话题·备考方法", ["规划", "攻略", "怎么做", "方法", "避坑", "流程", "标准"]),
    ("话题·估分对答案", ["估分", "对答案", "出分"]),
    ("话题·知乎", ["知乎"]),
    ("其他·数学", ["数学", "数一", "数二", "数三", "高数"]),
    ("其他·408计算机", ["408", "王道", "计算机"]),
    ("其他·教育学", ["教育学", "333"]),
    ("其他·四六级", ["四六级", "四级", "六级"]),
    ("其他·管理类联考", ["管理类联考", "199"]),
]

NON_ENGLISH_TOPICS = {
    "其他·数学",
    "其他·408计算机",
    "其他·教育学",
    "其他·四六级",
}

MISC_REP = "其他方向内容（数学 / 408 / 教育学 / 四六级等，非考研英语）"


def _cluster_topic(cluster):
    """按优先级给种子簇打一个主题标签。"""
    text = " ".join(m["title"] for m in cluster["main"]).lower()
    for name, keywords in TOPIC_PRIORITY:
        if any(k in text for k in keywords):
            return name
    return "其他·未分类"


def cluster(main_entries, base_threshold=0.5, target_max=15):
    """两步聚类：
    1) 先按 0.5 阈值做 difflib 贪心聚类（保留用户指定的基础算法），得到种子簇；
    2) 同主题种子簇归并成资料簇；非英语方向的杂项单独收成“其他内容”卡；
       仍超过目标簇数时，把最小簇并入与其代表标题最相似的簇（difflib）。"""
    seeds = _greedy_cluster(main_entries, base_threshold)
    for s in seeds:
        s["topic"] = _cluster_topic(s)

    groups = []
    for s in seeds:
        for g in groups:
            if g["topic"] == s["topic"]:
                g["main"].extend(s["main"])
                break
        else:
            groups.append({"topic": s["topic"], "main": list(s["main"])})
    groups.sort(key=lambda g: (len(g["main"]), g["topic"]), reverse=True)

    # 非英语方向的杂项合并成一张“其他内容”卡
    misc = [g for g in groups if g["topic"] in NON_ENGLISH_TOPICS]
    keep = [g for g in groups if g["topic"] not in NON_ENGLISH_TOPICS]
    if misc:
        merged_main = [m for g in misc for m in g["main"]]
        keep.append({"topic": "其他·杂项", "main": merged_main, "is_misc": True})
        keep.sort(key=lambda g: (len(g["main"]), g["topic"]), reverse=True)

    # 仍超过目标簇数：把最小簇并入与其代表标题最相似的簇
    while len(keep) > target_max:
        small = min(keep, key=lambda g: len(g["main"]))
        keep.remove(small)
        small_norm = normalize_title(small["main"][0]["title"])
        best, best_r = None, 0.0
        for g in keep:
            r = similarity(small_norm, normalize_title(g["main"][0]["title"]))
            if r > best_r:
                best_r = r
                best = g
        if best is None:
            keep.append(small)
            break
        best["main"].extend(small["main"])

    return [
        {
            "rep_title": g["main"][0]["title"],
            "main": g["main"],
            "is_misc": g.get("is_misc", False),
            "misc_rep": MISC_REP if g.get("is_misc") else None,
        }
        for g in keep
    ]


def build(entries, core_tokens=None, **cluster_kwargs):
    """完整流程：打标签 -> 去重 -> 聚类 -> 资料组核心词校验 -> 汇总统计。"""
    for entry in entries:
        entry["tags"] = tag_names(entry)

    dup_groups = deduplicate(entries)
    main_entries = [g[0] for g in dup_groups]
    main_to_group = {id(g[0]): g for g in dup_groups}

    raw_clusters = cluster(main_entries, **cluster_kwargs)

    # 资料组守卫：如果一组里大部分结果都不含用户的核心词，整组不展示
    if core_tokens:
        lowered = [c.lower() for c in core_tokens]
        kept = []
        for c in raw_clusters:
            mains = c["main"]
            if not mains:
                continue
            hits = sum(
                1
                for m in mains
                if all(core in (m.get("title") or "").lower() for core in lowered)
            )
            if hits / len(mains) >= 0.5:
                kept.append(c)
        raw_clusters = kept

    clusters = []
    for c in raw_clusters:
        rep_title = (
            c["misc_rep"]
            if c.get("misc_rep")
            else _pick_rep_title([m["title"] for m in c["main"]])
        )
        items = []
        tag_counter = Counter()
        for main in c["main"]:
            group = main_to_group[id(main)]
            for idx, item in enumerate(group):
                quality_tags, stars = quality_assess(item)
                items.append(
                    {
                        "source": item["source"],
                        "title": item["title"],
                        "url": item["url"],
                        "desc": item.get("desc", ""),
                        "tags": [_tag_dict(t) for t in item["tags"]],
                        "quality_tags": quality_tags,
                        "stars": stars,
                        "is_dup": idx > 0,
                    }
                )
                for t in item["tags"]:
                    tag_counter[t] += 1

        total = len(items)
        merged = total - len(c["main"])
        all_tag_names = sorted(
            tag_counter,
            key=lambda n: (-tag_counter[n], -TAG_PRIORITY.get(n, 0)),
        )
        all_tags = [_tag_dict(n) for n in all_tag_names]
        clusters.append(
            {
                "rep_title": rep_title,
                "total": total,
                "merged": merged,
                "main_count": len(c["main"]),
                "dominant": all_tags[0] if all_tags else None,
                "all_tags": all_tags,
                "entries": items,
            }
        )

    # 簇按包含条数从多到少排列，最热门的内容放最前面
    clusters.sort(key=lambda c: c["total"], reverse=True)

    per_source = Counter(e["source"] for e in entries)
    stats = {
        "total_raw": len(entries),
        "per_source": dict(per_source),
        "main_count": len(main_entries),
        "merged_count": sum(len(g) - 1 for g in dup_groups),
        "cluster_count": len(clusters),
    }
    return {
        "stats": stats,
        "clusters": clusters,
        "raw_ordered": [
            {"source": e["source"], "title": e["title"]} for e in entries
        ],
    }
