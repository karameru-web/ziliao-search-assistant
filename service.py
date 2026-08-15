# -*- coding: utf-8 -*-
"""搜索编排：抓取 4 个来源，先做核心词过滤，再交给 processor 归纳成资料组。"""

import time

import crawler
import keyword_utils
import processor


def run_full_search(keyword, bili_pages=3, bing_pages=3, zhihu_pages=3, progress_cb=None):
    def _cb(added):
        if progress_cb:
            progress_cb(added)

    # 提取核心词（去掉“考研/考博”等通用词），构造强制短语查询和标题过滤器
    core_tokens = keyword_utils.extract_core_tokens(keyword)
    phrase_query = keyword_utils.build_phrase_query(keyword, core_tokens)
    title_filter = keyword_utils.make_title_filter(core_tokens)

    filtered = {"B站": 0, "Bing网页": 0, "知乎": 0}

    def _make_filter(source):
        def _check(title):
            if title_filter is not None and not title_filter(title):
                filtered[source] += 1
                return False
            return True

        return _check

    t0 = time.time()
    videos, articles, bili_warnings = crawler.fetch_bilibili(
        keyword, pages=bili_pages, progress_cb=_cb, title_filter=_make_filter("B站")
    )
    bing_results, bing_warnings = crawler.fetch_bing(
        phrase_query,
        pages=bing_pages,
        progress_cb=_cb,
        title_filter=_make_filter("Bing网页"),
    )
    zhihu_results, zhihu_warnings = crawler.fetch_zhihu(
        phrase_query,
        pages=zhihu_pages,
        progress_cb=_cb,
        title_filter=_make_filter("知乎"),
    )

    raw_entries = videos + articles + bing_results + zhihu_results
    result = processor.build(raw_entries, core_tokens=core_tokens)
    result["elapsed"] = round(time.time() - t0, 1)
    result["stats"]["fetched_before_filter"] = result["stats"]["total_raw"] + sum(
        filtered.values()
    )
    result["stats"]["core_filtered"] = sum(filtered.values())
    result["stats"]["core_filtered_by_source"] = dict(filtered)
    result["core_phrase"] = "、".join(core_tokens) if core_tokens else ""
    warnings = bili_warnings + bing_warnings + zhihu_warnings
    return result, warnings
