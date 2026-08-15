# -*- coding: utf-8 -*-
"""关键词处理：提取核心词、构造强制短语查询、标题过滤器。"""

import re

# 搜索词里的通用词：去掉它们之后剩下的才是真正的主体
GENERIC_TERMS = ["考研", "考博"]

_TOKEN_SPLIT = re.compile(r"[\s,，、;；:：/|]+")


def extract_core_tokens(keyword):
    """从用户输入里提取核心词。

    规则：按空白/标点切分，去掉“考研/考博”这类通用词，剩下的部分就是核心词。
    例如：“比较文学考研” -> [“比较文学”]；“考研英语 真题” -> [“英语”, “真题”]。
    """
    cores = []
    for token in _TOKEN_SPLIT.split((keyword or "").strip()):
        t = token
        # 通用词可能出现在词首或词尾，反复剥除
        for _ in range(3):
            changed = False
            for g in GENERIC_TERMS:
                if t.startswith(g):
                    t = t[len(g):]
                    changed = True
                if t.endswith(g):
                    t = t[: -len(g)]
                    changed = True
            if not changed:
                break
        t = t.strip()
        if len(t) >= 2:  # 太短（如只剩单字）不作为核心词，避免误伤
            cores.append(t)
    return cores


def build_phrase_query(keyword, core_tokens):
    """构造整词查询。

    实测 Bing 对中文引号短语不生效，且对含“考研”后缀的长查询会退化到
    只匹配最前面两个字（例如“比较文学考研”只返回“比较”的结果），
    因此单个核心词时只把“学科核心词”整体作为查询词（如“比较文学”）；
    多个核心词（如“考研英语 真题”）保持原关键词不变。
    """
    if len(core_tokens) == 1 and len(core_tokens[0]) >= 2:
        return core_tokens[0]
    return keyword


def make_title_filter(core_tokens):
    """返回标题过滤器：标题必须包含全部核心词，否则返回 False 丢弃。"""
    if not core_tokens:
        return None
    lowered = [c.lower() for c in core_tokens]

    def _filter(title):
        t = (title or "").lower()
        return all(c in t for c in lowered)

    return _filter
