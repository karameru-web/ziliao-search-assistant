# -*- coding: utf-8 -*-
"""桌面应用启动器：后台启动 Flask，前台用 pywebview 原生窗口显示。"""

import socket
import threading
import time
import urllib.request

import webview

import app as kaoyan_app


def _find_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_server(url, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.2)
    return False


def main():
    port = _find_free_port()
    url = f"http://127.0.0.1:{port}"
    threading.Thread(
        target=lambda: kaoyan_app.app.run(
            host="127.0.0.1", port=port, threaded=True, use_reloader=False
        ),
        daemon=True,
    ).start()
    _wait_server(url)
    webview.create_window(
        "资料搜索助手",
        url,
        width=1280,
        height=880,
        min_size=(1024, 700),
    )
    webview.start()


if __name__ == "__main__":
    main()
