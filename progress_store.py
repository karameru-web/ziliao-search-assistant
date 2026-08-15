# -*- coding: utf-8 -*-
"""我的资料库 · 手动进度标记（SQLite 持久化）。

只保存 entry_id 和进度状态，不保存任何视频内容或浏览数据。
状态：not_started（未开始）/ reading（在看）/ done（已完成）
"""

import os
import sqlite3
import threading

import paths

DB_PATH = os.path.join(paths.data_dir(), "progress.db")

ALLOWED = {"not_started", "reading", "done"}
_LOCK = threading.Lock()


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS progress ("
        " entry_id TEXT PRIMARY KEY,"
        " status TEXT NOT NULL DEFAULT 'not_started')"
    )
    return conn


def get_status(entry_id):
    try:
        conn = _connect()
        row = conn.execute(
            "SELECT status FROM progress WHERE entry_id = ?", (str(entry_id),)
        ).fetchone()
        conn.close()
        return row[0] if row and row[0] in ALLOWED else "not_started"
    except sqlite3.Error:
        return "not_started"


def get_all_statuses():
    try:
        conn = _connect()
        rows = conn.execute("SELECT entry_id, status FROM progress").fetchall()
        conn.close()
        return {eid: st for eid, st in rows if st in ALLOWED}
    except sqlite3.Error:
        return {}


def set_status(entry_id, status):
    if status not in ALLOWED:
        return False
    with _LOCK:
        try:
            conn = _connect()
            conn.execute(
                "INSERT INTO progress (entry_id, status) VALUES (?, ?) "
                "ON CONFLICT(entry_id) DO UPDATE SET status = excluded.status",
                (str(entry_id), status),
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error:
            return False


def delete_status(entry_id):
    with _LOCK:
        try:
            conn = _connect()
            conn.execute("DELETE FROM progress WHERE entry_id = ?", (str(entry_id),))
            conn.commit()
            conn.close()
        except sqlite3.Error:
            pass
