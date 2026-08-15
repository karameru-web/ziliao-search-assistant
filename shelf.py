# -*- coding: utf-8 -*-
"""书架/下载管理：bookshelf/ 目录保存下载与上传的文件，index.json 记录元数据。"""

import json
import os
import threading
import time
import uuid
from urllib.parse import urlparse

import requests
from werkzeug.utils import secure_filename

import paths

BASE_DIR = paths.data_dir()
BOOKSHELF_DIR = os.path.join(BASE_DIR, "bookshelf")
UPLOADS_DIR = os.path.join(BOOKSHELF_DIR, "uploads")
INDEX_PATH = os.path.join(BOOKSHELF_DIR, "index.json")

FILE_EXTS = (
    ".pdf", ".doc", ".docx", ".zip", ".rar", ".7z", ".txt", ".epub",
    ".mobi", ".ppt", ".pptx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg",
)
MAX_DOWNLOAD_BYTES = 60 * 1024 * 1024  # 单个文件最多 60MB

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_INDEX_LOCK = threading.RLock()  # 可重入：add_entry 持锁后会调用 _save_index


def new_id(prefix):
    """生成带前缀的唯一 id（避免同一毫秒上传多个文件时撞 id）。"""
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _ensure_dirs():
    os.makedirs(BOOKSHELF_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)


def _load_index():
    _ensure_dirs()
    if not os.path.exists(INDEX_PATH):
        return []
    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_index(items):
    _ensure_dirs()
    with _INDEX_LOCK:
        tmp = INDEX_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        os.replace(tmp, INDEX_PATH)  # 原子替换，避免写一半损坏


def add_entry(entry):
    with _INDEX_LOCK:
        items = _load_index()
        items.append(entry)
        _save_index(items)
    return entry


def list_entries(kind=None):
    items = _load_index()
    if kind:
        items = [it for it in items if it.get("kind") == kind]
    return list(reversed(items))  # 最新在前


def remove_entry(entry_id):
    with _INDEX_LOCK:
        items = _load_index()
        kept = [it for it in items if it.get("id") != entry_id]
        _save_index(kept)
    return len(items) != len(kept)


def looks_like_file(url):
    """判断链接路径是否带常见文件后缀（网盘/详情页链接不算）。"""
    path = urlparse(url or "").path.lower()
    return path.endswith(FILE_EXTS)


def _unique_path(directory, filename):
    """避免重名：hello.pdf -> hello(1).pdf。"""
    name, ext = os.path.splitext(filename)
    candidate = os.path.join(directory, filename)
    n = 1
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{name}({n}){ext}")
        n += 1
    return candidate


def safe_filename(name):
    """保留中文等原始字符，只去掉路径分隔符等危险字符。"""
    name = (name or "").replace("\\", "_").replace("/", "_").replace("\x00", "")
    name = name.strip().strip(".")
    while name.startswith(".."):
        name = name[2:].lstrip("._- ")
    return name or "upload"


def get_file_stats(path, ext):
    """返回文件大小（人性化）、PDF页数或 TXT/DOCX 字数。"""
    size = 0
    size_human = "—"
    pages = None
    chars = None
    try:
        size = os.path.getsize(path)
        if size < 1024 * 1024:
            size_human = f"{size / 1024:.1f} KB"
        else:
            size_human = f"{size / 1024 / 1024:.1f} MB"
    except OSError:
        pass
    if ext == ".pdf":
        try:
            import pypdf
            pages = len(pypdf.PdfReader(path).pages)
        except Exception:
            pages = None
    elif ext == ".txt":
        try:
            with open(path, "r", encoding="utf-8") as f:
                chars = len(f.read())
        except (OSError, UnicodeDecodeError):
            chars = None
    elif ext == ".docx":
        try:
            import zipfile
            with zipfile.ZipFile(path) as z:
                xml = z.read("word/document.xml").decode("utf-8", "ignore")
            import re
            chars = len(re.sub(r"<[^>]+>", "", xml))
        except Exception:
            chars = None
    return {"size": size, "size_human": size_human, "pages": pages, "chars": chars}


def download_file(url, title, source):
    """下载文件直链到 bookshelf/，并写入书架索引。"""
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        return {"ok": False, "message": "下载失败，请查看原文手动保存"}
    if not looks_like_file(url):
        return {"ok": False, "code": "not_file",
                "message": "该链接不是文件直链，请复制链接或查看原文"}
    _ensure_dirs()
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": BROWSER_UA, "Accept-Language": "zh-CN,zh;q=0.9"},
            timeout=30,
            stream=True,
        )
        if resp.status_code != 200:
            return {"ok": False, "message": "下载失败，请查看原文手动保存"}
        filename = safe_filename(os.path.basename(urlparse(url).path))
        if not filename:
            filename = safe_filename(title or "download") or "download"
            ctype = resp.headers.get("Content-Type", "")
            if "pdf" in ctype:
                filename += ".pdf"
        filename = safe_filename(filename) or "download"
        dest = _unique_path(BOOKSHELF_DIR, filename)
        size = 0
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                size += len(chunk)
                if size > MAX_DOWNLOAD_BYTES:
                    f.close()
                    os.remove(dest)
                    return {"ok": False, "message": "文件过大，下载失败，请查看原文手动保存"}
                f.write(chunk)
        add_entry(
            {
                "id": new_id("dl"),
                "kind": "download",
                "title": title or filename,
                "source": source or "",
                "url": url,
                "file": filename,
                "rel": f"bookshelf/{filename}",
                "added_at": time.strftime("%Y-%m-%d %H:%M"),
            }
        )
        return {"ok": True, "message": f"已下载到 bookshelf/{filename}", "file": filename}
    except requests.RequestException:
        return {"ok": False, "message": "下载失败，请查看原文手动保存"}


def extract_pdf_text(path):
    """尝试用 pypdf 读取 PDF 文字；扫描版/加密返回空字符串。"""
    try:
        import pypdf

        reader = pypdf.PdfReader(path)
        parts = []
        for page in reader.pages:
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            parts.append(text)
        return "\n".join(parts).strip()
    except Exception:
        return ""


def save_upload(file_storage):
    """保存上传文件并尽力读取文字，返回评估信息。"""
    _ensure_dirs()
    original = secure_filename(file_storage.filename or "upload") or "upload"
    dest = _unique_path(UPLOADS_DIR, original)
    file_storage.save(dest)
    rel = f"bookshelf/uploads/{os.path.basename(dest)}"
    lower = original.lower()

    text = ""
    if lower.endswith(".pdf"):
        text = extract_pdf_text(dest)
        if not text:
            add_entry(
                {
                    "id": new_id("up"),
                    "kind": "upload",
                    "title": original,
                    "source": "本地上传",
                    "url": "",
                    "file": os.path.basename(dest),
                    "rel": rel,
                    "type_guess": "无法识别（无法读取文字）",
                    "added_at": time.strftime("%Y-%m-%d %H:%M"),
                }
            )
            return {
                "ok": False,
                "readable": False,
                "message": "无法读取该PDF文字内容（可能是扫描版或加密文件）",
                "rel": rel,
            }
    elif lower.endswith(".txt"):
        try:
            with open(dest, "r", encoding="utf-8") as f:
                text = f.read()
        except UnicodeDecodeError:
            try:
                with open(dest, "r", encoding="gbk") as f:
                    text = f.read()
            except Exception:
                text = ""
        if not text.strip():
            return {
                "ok": False,
                "readable": False,
                "message": "无法读取该文件文字内容",
                "rel": rel,
            }
    else:
        add_entry(
            {
                "id": new_id("up"),
                "kind": "upload",
                "title": original,
                "source": "本地上传",
                "url": "",
                "file": os.path.basename(dest),
                "rel": rel,
                "type_guess": "暂不支持读取该格式",
                "added_at": time.strftime("%Y-%m-%d %H:%M"),
            }
        )
        return {
            "ok": False,
            "readable": False,
            "message": "暂不支持读取该格式的文字内容（请上传 PDF 或 TXT）",
            "rel": rel,
        }

    add_entry(
        {
            "id": new_id("up"),
            "kind": "upload",
            "title": original,
            "source": "本地上传",
            "url": "",
            "file": os.path.basename(dest),
            "rel": rel,
            "type_guess": "",
            "added_at": time.strftime("%Y-%m-%d %H:%M"),
        }
    )
    return {"ok": True, "readable": True, "message": "上传成功，已读取内容并加入书架", "text": text, "rel": rel}


def store_upload_file(file_storage):
    """只保存上传文件并写入书架索引（不评估内容），返回 (rel, 绝对路径)。"""
    _ensure_dirs()
    original = file_storage.filename or "upload"
    filename = safe_filename(original) or "upload"
    dest = _unique_path(UPLOADS_DIR, filename)
    file_storage.save(dest)
    rel = f"bookshelf/uploads/{os.path.basename(dest)}"
    stats = get_file_stats(dest, os.path.splitext(dest)[1].lower())
    add_entry(
        {
            "id": new_id("up"),
            "kind": "upload",
            "title": original,
            "source": "本地上传",
            "url": "",
            "file": os.path.basename(dest),
            "rel": rel,
            "type_guess": "",
            "size_human": stats["size_human"],
            "pages": stats["pages"],
            "chars": stats["chars"],
            "added_at": time.strftime("%Y-%m-%d %H:%M"),
        }
    )
    return rel, dest
