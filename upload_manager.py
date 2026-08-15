# -*- coding: utf-8 -*-
"""上传评估：批量查重 + 完整度对比。

说明：不做“引流/营销”分析——用户上传的是自己的笔记/真题，出现“必考”“必中”
等词只是资料内容本身。这里只做两件事：找出高度重复的文件、对比谁更全。
"""

import html as _html
import os
import re
import threading
import time
import uuid
import zipfile

import shelf

SUPPORTED_EXTS = (".pdf", ".txt", ".docx")
REPORT_THRESHOLD = 0.50    # 达到该重合度就展示对比
HIGHLY_SIMILAR = 0.60      # 达到该重合度判定为“高度重复”

_JOBS = {}


def extract_text(path, ext):
    """按格式提取文字；读取失败返回空字符串。"""
    if ext == ".pdf":
        return shelf.extract_pdf_text(path)
    if ext == ".txt":
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            try:
                with open(path, "r", encoding="gbk") as f:
                    return f.read()
            except Exception:
                return ""
        except OSError:
            return ""
    if ext == ".docx":
        try:
            with zipfile.ZipFile(path) as z:
                xml = z.read("word/document.xml").decode("utf-8", "ignore")
            xml = re.sub(r"<w:p[ >]", "\n", xml)
            text = re.sub(r"<[^>]+>", "", xml)
            return _html.unescape(text)
        except Exception:
            return ""
    return ""


def _normalize(text):
    return re.sub(r"[\s\u3000]+", "", text or "").lower()


def _shingles(text, n=8, limit=300000):
    t = _normalize(text)[:limit]
    if not t:
        return set()
    if len(t) < n:
        return {t}
    return {t[i:i + n] for i in range(len(t) - n + 1)}


def similarity(a, b):
    """两段文字的重合度（Jaccard 相似度，0~1）。"""
    return similarity_sets(_shingles(a), _shingles(b))


def similarity_sets(sa, sb):
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def char_count(text):
    return len(_normalize(text))


def page_count(path, ext, text):
    if ext == ".pdf":
        try:
            import pypdf
            return len(pypdf.PdfReader(path).pages)
        except Exception:
            return 0
    return max(1, round(char_count(text) / 500))  # TXT/DOCX 按字数估算页数


def _doc_record(name, path, ext, text, readable, note, pages, chars, is_lib):
    return {
        "name": name,
        "path": path,
        "ext": ext,
        "text": text,
        "readable": readable,
        "note": note,
        "pages": pages,
        "chars": chars,
        "is_lib": is_lib,
        "shingles": _shingles(text),
    }


def analyze(saved, existing_entries, progress=None):
    """批量查重：saved 为本次上传的 [(name, path, ext)]，existing_entries 为资料库旧条目。
    返回报告 dict。"""
    docs = []          # 可读文件
    skipped = []       # 读取失败/格式不支持
    files = []         # 每个文件的统计

    # 先处理本次上传的新文件（进度只统计这些）
    for i, (name, path, ext) in enumerate(saved):
        if progress:
            progress(i + 1)
        if ext not in SUPPORTED_EXTS:
            skipped.append({"name": name, "reason": "该格式暂不支持，请先导出为PDF或Word再上传"})
            files.append({"name": name, "readable": False, "pages": 0, "chars": 0, "note": "格式暂不支持"})
            continue
        text = extract_text(path, ext)
        if not text.strip():
            skipped.append({"name": name, "reason": "无法读取该文件文字，已跳过"})
            files.append({"name": name, "readable": False, "pages": 0, "chars": 0, "note": "无法读取"})
            continue
        rec = _doc_record(
            name, path, ext, text, True, "",
            page_count(path, ext, text), char_count(text), False,
        )
        docs.append(rec)
        files.append({
            "name": name,
            "readable": True,
            "pages": rec["pages"],
            "chars": rec["chars"],
            "note": "",
        })

    # 再读取资料库旧文件用于对比（不计入进度）
    for entry in existing_entries:
        rel = entry.get("rel") or ""
        if not rel:
            continue
        path = os.path.join(shelf.BASE_DIR, rel)
        if not os.path.exists(path):
            continue
        name = entry.get("title") or os.path.basename(path)
        ext = os.path.splitext(path)[1].lower()
        if ext not in SUPPORTED_EXTS:
            continue
        text = extract_text(path, ext)
        if not text.strip():
            continue
        rec = _doc_record(
            name, path, ext, text, True, "",
            page_count(path, ext, text), char_count(text), True,
        )
        docs.append(rec)

    pairs = []
    for i in range(len(docs)):
        for j in range(i + 1, len(docs)):
            a, b = docs[i], docs[j]
            sim = similarity_sets(a["shingles"], b["shingles"])
            if sim < REPORT_THRESHOLD:
                continue
            recommend = ""
            reason = ""
            if sim >= HIGHLY_SIMILAR:
                if a["is_lib"] or b["is_lib"]:
                    lib, cur = (a, b) if a["is_lib"] else (b, a)
                    recommend = f"《{cur['name']}》与资料库中的《{lib['name']}》高度相似，可能不值得再花时间看"
                else:
                    # 谁更全：页数优先，其次字数
                    if a["pages"] != b["pages"]:
                        keep = a if a["pages"] > b["pages"] else b
                        reason = f"{keep['name']}页数更多、内容更全"
                    elif a["chars"] != b["chars"]:
                        keep = a if a["chars"] > b["chars"] else b
                        reason = f"{keep['name']}字数更多、内容更全"
                    else:
                        keep = a
                        reason = "两者页数与字数相当"
                    recommend = f"推荐保留《{keep['name']}》，因为{reason}"
            pairs.append({
                "a": a["name"],
                "b": b["name"],
                "sim": round(sim * 100),
                "a_pages": a["pages"],
                "b_pages": b["pages"],
                "a_chars": a["chars"],
                "b_chars": b["chars"],
                "diff_chars": a["chars"] - b["chars"],
                "diff_pages": a["pages"] - b["pages"],
                "recommend": recommend,
                "reason": reason,
                "highly": sim >= HIGHLY_SIMILAR,
            })

    return {
        "files": files,
        "pairs": sorted(pairs, key=lambda p: -p["sim"]),
        "skipped": skipped,
    }


def start_job(saved, existing_entries):
    """启动后台批量查重任务，返回 job_id。"""
    job_id = uuid.uuid4().hex[:10]
    state = {
        "id": job_id,
        "total": len(saved),
        "current": 0,
        "done": False,
        "error": None,
        "result": None,
        "started": time.time(),
    }
    _JOBS[job_id] = state

    def _run():
        try:
            def progress(i):
                state["current"] = i
            state["result"] = analyze(saved, existing_entries, progress=progress)
        except Exception as exc:  # noqa: BLE001
            state["error"] = str(exc)
        finally:
            state["done"] = True

    threading.Thread(target=_run, daemon=True).start()
    return job_id


def get_job(job_id):
    return _JOBS.get(job_id)
