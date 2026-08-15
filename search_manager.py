# -*- coding: utf-8 -*-
"""搜索任务管理：把一次搜索放到后台线程跑，实时记录已抓条数。"""

import threading
import time
import uuid

import service

_STATE = {}
_LOCK = threading.Lock()
MAX_STATES = 30


def start_search(keyword):
    """启动一次后台搜索，返回 search_id。"""
    search_id = uuid.uuid4().hex[:10]
    state = {
        "id": search_id,
        "keyword": keyword,
        "status": "running",
        "count": 0,
        "done": False,
        "error": None,
        "warnings": [],
        "result": None,
        "started": time.time(),
    }
    with _LOCK:
        _STATE[search_id] = state
        # 简单清理：只保留最近的已完成任务，避免内存无限增长
        if len(_STATE) > MAX_STATES:
            finished = [sid for sid, st in _STATE.items() if st.get("done")]
            for sid in finished[: len(_STATE) - MAX_STATES]:
                _STATE.pop(sid, None)

    def _run():
        def progress(added):
            state["count"] += added

        try:
            result, warnings = service.run_full_search(keyword, progress_cb=progress)
            state["result"] = result
            state["warnings"] = warnings
            state["status"] = "done"
        except Exception as exc:  # noqa: BLE001
            state["status"] = "error"
            state["error"] = str(exc)
        finally:
            state["done"] = True

    threading.Thread(target=_run, daemon=True).start()
    return search_id


def get_state(search_id):
    with _LOCK:
        return _STATE.get(search_id)
