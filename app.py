# -*- coding: utf-8 -*-
"""Flask 入口：考研资料搜索助手
四个板块：全网搜索 / 链接评估 / 上传评估 / 我的资料
"""

import os
import subprocess
import sys
import time
from urllib.parse import urlparse

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.exceptions import RequestEntityTooLarge

import evaluator
import paths
import progress_store
import search_manager
import shelf
import upload_manager

app = Flask(
    __name__,
    template_folder=str(paths.resource_dir() / "templates"),
    static_folder=str(paths.resource_dir() / "static"),
)
app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024  # 上传上限 30MB

FILE_EXTS = (
    ".pdf", ".doc", ".docx", ".zip", ".rar", ".7z", ".txt", ".epub",
    ".mobi", ".ppt", ".pptx", ".xls", ".xlsx",
)
SUPPORTED_UPLOAD_EXTS = {".pdf", ".txt", ".docx"}


def _looks_like_file(url):
    path = urlparse(url or "").path.lower()
    return path.endswith(FILE_EXTS)


def _enrich(result):
    """给搜索结果条目补充展示用标记（不改变聚类与搜索逻辑）。"""
    if not result:
        return
    for cluster in result.get("clusters", []):
        for item in cluster.get("entries", []):
            item["is_free"] = any(
                t.get("name") == "免费可下" for t in item.get("tags", [])
            )
            item["is_file_link"] = _looks_like_file(item.get("url", ""))


def _decorate_uploads(uploads):
    """给上传条目补充文件大小/页数等展示信息（历史条目可能没有）。"""
    for e in uploads:
        rel = e.get("rel") or ""
        path = os.path.join(shelf.BASE_DIR, rel) if rel else ""
        if not os.path.exists(path):
            continue
        if not e.get("size_human"):
            stats = shelf.get_file_stats(path, os.path.splitext(path)[1].lower())
            e["size_human"] = stats["size_human"]
            e["pages"] = stats["pages"]
            e["chars"] = stats["chars"]
    return uploads


@app.route("/", methods=["GET", "POST"])
def index():
    """板块一：全网搜索。"""
    if request.method == "POST":
        keyword = (request.form.get("keyword") or "").strip()
        if keyword:
            search_id = search_manager.start_search(keyword)
            return render_template(
                "progress.html",
                keyword=keyword,
                search_id=search_id,
                not_found=False,
                active="search",
            )
    return render_template(
        "index.html", keyword="", result=None, warnings=[], active="search"
    )


@app.route("/search", methods=["GET", "POST"])
def search_alias():
    """主搜索接口别名：兼容前端把搜索请求提交到 /search 的情况。"""
    if request.method == "POST":
        keyword = (request.form.get("keyword") or "").strip()
        if keyword:
            search_id = search_manager.start_search(keyword)
            return render_template(
                "progress.html",
                keyword=keyword,
                search_id=search_id,
                not_found=False,
                active="search",
            )
    return redirect(url_for("index"))


@app.route("/search_status/<search_id>", methods=["GET", "POST"])
def search_status(search_id):
    """进度状态接口：返回当前已抓条数、是否完成、是否超时。"""
    state = search_manager.get_state(search_id)
    if not state:
        return jsonify({"error": "任务不存在或已过期"}), 404
    elapsed = time.time() - state["started"]
    return jsonify(
        {
            "status": state["status"],
            "count": state["count"],
            "done": state["done"],
            "error": state.get("error"),
            "elapsed": round(elapsed, 1),
            "timed_out": elapsed > 120,
        }
    )


@app.route("/result/<search_id>", methods=["GET", "POST"])
def result(search_id):
    state = search_manager.get_state(search_id)
    if not state:
        return render_template(
            "progress.html",
            keyword="",
            search_id=search_id,
            not_found=True,
            active="search",
        )
    if not state.get("done"):
        return render_template(
            "progress.html",
            keyword=state["keyword"],
            search_id=search_id,
            not_found=False,
            active="search",
        )
    _enrich(state["result"])
    return render_template(
        "index.html",
        keyword=state["keyword"],
        result=state["result"],
        warnings=state.get("warnings", []),
        active="search",
    )


@app.route("/eval", methods=["GET", "POST"])
def evaluate_page():
    """板块三：链接评估（自动识别链接 + 手动补充内容）。"""
    link = ""
    manual = ""
    report = None
    error = None
    if request.method == "POST":
        pasted = (request.form.get("link") or "").strip()
        manual = (request.form.get("manual") or "").strip()
        links = evaluator.extract_links(pasted)
        link = pasted
        if not links:
            error = "没找到有效链接，请重新粘贴"
        else:
            url = links[0]
            fetch_result = evaluator.fetch_link_content(url)
            merged = evaluator.merge_content(fetch_result, manual)
            report = evaluator.evaluate(merged)
            report["fetch"] = fetch_result
            report["manual_provided"] = bool(manual)
            report["merged_text"] = merged
            report["used_url"] = url
    return render_template(
        "eval.html",
        link=link,
        manual=manual,
        report=report,
        error=error,
        active="eval",
    )


@app.route("/upload", methods=["GET", "POST"])
def upload_page():
    """板块四：上传评估（先上传、后勾选、再评估）。"""
    analysis = None
    message = None
    message_type = None
    job_id = request.args.get("job", "").strip()
    if job_id:
        job = upload_manager.get_job(job_id)
        if job and job.get("done"):
            analysis = job.get("result")
            if job.get("error"):
                message = f"处理出错：{job['error']}"
                message_type = "warning"
    if request.method == "POST":
        # 无 JS 时的兜底：只保存文件，然后回到列表页
        files = [f for f in request.files.getlist("files") if f and f.filename]
        if not files:
            message = "请先选择要上传的文件"
            message_type = "warning"
        else:
            saved = []
            skipped = []
            for f in files:
                ext = os.path.splitext(f.filename)[1].lower()
                if ext not in SUPPORTED_UPLOAD_EXTS:
                    skipped.append(f.filename)
                    continue
                rel, path = shelf.store_upload_file(f)
                saved.append(f.filename)
            if saved:
                message = f"已上传 {len(saved)} 个文件，请在下方勾选后开始评估"
                if skipped:
                    message += f"；{len(skipped)} 个文件格式暂不支持，请先导出为PDF或Word再上传"
                message_type = "success"
            else:
                message = "该格式暂不支持，请先导出为PDF或Word再上传"
                message_type = "warning"
    uploads = shelf.list_entries(kind="upload")
    uploads = _decorate_uploads(uploads)
    return render_template(
        "upload.html",
        analysis=analysis,
        message=message,
        message_type=message_type,
        uploads=uploads,
        bookshelf_path=shelf.BOOKSHELF_DIR,
        active="upload",
    )


@app.route("/upload/add", methods=["POST"])
def upload_add():
    """上传入口（JS 异步路径）：只保存文件并返回结果，不自动评估。"""
    files = [f for f in request.files.getlist("files") if f and f.filename]
    if not files:
        return jsonify({"ok": False, "message": "请先选择要上传的文件"}), 400
    names, skipped = [], []
    for f in files:
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in SUPPORTED_UPLOAD_EXTS:
            skipped.append(f.filename)
            continue
        rel, path = shelf.store_upload_file(f)
        names.append(f.filename)
    if not names:
        return jsonify({"ok": False, "message": "该格式暂不支持，请先导出为PDF或Word再上传"}), 400
    msg = f"已添加 {len(names)} 个文件到列表"
    if skipped:
        msg += f"；{len(skipped)} 个文件格式暂不支持，请先导出为PDF或Word再上传"
    return jsonify({"ok": True, "added": len(names), "names": names, "message": msg})


@app.route("/upload/evaluate", methods=["POST"])
def upload_evaluate():
    """按用户勾选的文件启动查重评估（异步，轮询进度）。"""
    data = request.get_json(silent=True) or {}
    ids = [str(x).strip() for x in (data.get("ids") or []) if str(x).strip()]
    if len(ids) < 2:
        return jsonify({"ok": False, "message": "请先勾选至少两份资料进行对比"}), 400
    all_uploads = shelf.list_entries(kind="upload")
    by_id = {str(e.get("id")): e for e in all_uploads}
    checked = []
    for i in ids:
        entry = by_id.get(i)
        if not entry:
            continue
        rel = entry.get("rel") or ""
        path = os.path.join(shelf.BASE_DIR, rel) if rel else ""
        if not os.path.exists(path):
            continue
        checked.append(
            (entry.get("title") or os.path.basename(path), path,
             os.path.splitext(path)[1].lower())
        )
    if len(checked) < 2:
        return jsonify({"ok": False, "message": "请先勾选至少两份资料进行对比"}), 400
    existing = [e for e in all_uploads if str(e.get("id")) not in ids]
    job_id = upload_manager.start_job(checked, existing)
    return jsonify({"ok": True, "job_id": job_id})


@app.route("/upload_status/<job_id>")
def upload_status(job_id):
    job = upload_manager.get_job(job_id)
    if not job:
        return jsonify({"error": "任务不存在或已过期"}), 404
    return jsonify(
        {
            "total": job["total"],
            "current": job["current"],
            "done": job["done"],
            "error": job.get("error"),
        }
    )


@app.route("/shelf", methods=["GET"])
def shelf_page():
    """板块二：我的资料（已下载 / 收藏 / 上传）。"""
    entries = shelf.list_entries()
    statuses = progress_store.get_all_statuses()
    for e in entries:
        e["progress"] = statuses.get(str(e.get("id")), "not_started")
    return render_template(
        "shelf.html",
        entries=entries,
        bookshelf_path=shelf.BOOKSHELF_DIR,
        active="shelf",
    )


@app.route("/progress/update", methods=["POST"])
def progress_update():
    """手动进度标记：只保存状态到 SQLite。"""
    data = request.get_json(silent=True) or {}
    entry_id = str(data.get("entry_id") or "").strip()
    status = str(data.get("status") or "").strip()
    if not entry_id:
        return jsonify({"ok": False, "message": "缺少条目"}), 400
    ok = progress_store.set_status(entry_id, status)
    if not ok:
        return jsonify({"ok": False, "message": "无效的状态"}), 400
    return jsonify({"ok": True, "message": "进度已保存"})


@app.route("/download", methods=["POST"])
def download():
    """下载文件直链到 bookshelf/。"""
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    title = (data.get("title") or "").strip()
    source = (data.get("source") or "").strip()
    return jsonify(shelf.download_file(url, title, source))


@app.route("/shelf/add", methods=["POST"])
def shelf_add():
    """把链接收藏到书架。"""
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    title = (data.get("title") or "").strip() or url
    source = (data.get("source") or "").strip()
    if not url:
        return jsonify({"ok": False, "message": "收藏失败：缺少链接"}), 400
    shelf.add_entry(
        {
                "id": shelf.new_id("bk"),
            "kind": "bookmark",
            "title": title,
            "source": source or "手动收藏",
            "url": url,
            "file": "",
            "rel": "",
            "added_at": time.strftime("%Y-%m-%d %H:%M"),
        }
    )
    return jsonify({"ok": True, "message": "已收藏到书架"})


@app.route("/shelf/add_many", methods=["POST"])
def shelf_add_many():
    """批量存入我的资料库（只存元数据与链接，不下载文件）。"""
    data = request.get_json(silent=True) or {}
    items = data.get("items") or []
    added = 0
    for it in items:
        url = (it.get("url") or "").strip()
        if not url:
            continue
        shelf.add_entry(
            {
                "id": shelf.new_id("bk"),
                "kind": "bookmark",
                "title": (it.get("title") or "").strip() or url,
                "source": (it.get("source") or "").strip() or "手动收藏",
                "url": url,
                "file": "",
                "rel": "",
                "added_at": time.strftime("%Y-%m-%d %H:%M"),
            }
        )
        added += 1
    return jsonify({"ok": True, "added": added, "message": f"已存入 {added} 条到我的资料库"})


@app.route("/shelf/remove", methods=["POST"])
def shelf_remove():
    data = request.get_json(silent=True) or {}
    entry_id = (data.get("id") or "").strip()
    ok = shelf.remove_entry(entry_id)
    if ok:
        progress_store.delete_status(entry_id)  # 删除时一并清掉进度记录
    return jsonify({"ok": ok, "message": "已移除" if ok else "条目不存在"})


@app.route("/shelf_file/<path:filename>")
def shelf_file(filename):
    # filename 形如 bookshelf/xxx.pdf 或 bookshelf/uploads/xxx.pdf，以项目目录为基准
    return send_from_directory(shelf.BASE_DIR, filename)


@app.route("/open_file/<path:rel>")
def open_file(rel):
    """用系统默认程序打开本地的已下载/上传文件（仅本机本地项目）。"""
    base = os.path.normpath(shelf.BASE_DIR)
    full = os.path.normpath(os.path.join(base, rel))
    if not full.startswith(base + os.sep) or not os.path.exists(full):
        return jsonify({"ok": False, "message": "文件不存在"}), 404
    try:
        if os.name == "nt":
            os.startfile(full)  # Windows：用系统默认程序打开
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-g", full])  # macOS
        else:
            subprocess.Popen(["xdg-open", full])  # Linux
        return jsonify({"ok": True, "message": "已尝试用系统默认程序打开"})
    except Exception:
        return jsonify({"ok": False, "message": "打开失败，请手动打开文件"})


@app.errorhandler(RequestEntityTooLarge)
def too_large(_e):
    return "文件过大，请上传 30MB 以内的文件", 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
