# -*- coding: utf-8 -*-
"""Windows 桌面启动器：后台启动 Flask，自动用默认浏览器打开界面（无黑框）。"""

import socket
import threading
import time
import urllib.request
import webbrowser

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
    webbrowser.open(url)
    # 保持进程存活，直到用户关闭（任务管理器结束或注销）
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
