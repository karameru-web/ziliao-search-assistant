# -*- coding: utf-8 -*-
"""运行路径：区分开发模式与打包后的可执行程序模式。

开发模式：资源与数据都在项目目录；
PyInstaller（Windows .exe）：资源在临时解包目录 _MEIPASS，数据放在 .exe 旁边；
py2app（Mac .app）：资源在包内 Resources，数据放在 .app 旁边；
旁边不可写时退回用户目录的 Application Support/AppData。
"""

import os
import sys
from pathlib import Path


def is_frozen():
    if getattr(sys, "frozen", False):
        return True
    # py2app 不一定设置 sys.frozen：若当前文件旁没有项目入口 app.py，视为打包模式
    return not (Path(__file__).resolve().parent / "app.py").exists()


def bundle_root():
    """打包后 .app 的 Contents 目录（包含 Resources 和 MacOS 的那一层）。"""
    exe = Path(sys.executable).resolve()
    for parent in exe.parents:
        if (parent / "Resources").is_dir() and (parent / "MacOS").is_dir():
            return parent
    return exe.parent


def resource_dir():
    """只读资源（templates / static）所在目录。"""
    if is_frozen():
        if getattr(sys, "_MEIPASS", None):  # PyInstaller 解包目录
            return Path(sys._MEIPASS)
        return bundle_root() / "Resources"
    return Path(__file__).resolve().parent


def data_dir():
    """可写数据（bookshelf、progress.db）所在目录。"""
    if is_frozen():
        if getattr(sys, "_MEIPASS", None):  # PyInstaller：.exe 所在目录
            base = Path(sys.executable).resolve().parent
        else:
            base = bundle_root().parent.parent  # 包含 .app 的那一层文件夹
        try:
            probe = base / ".write_test_tmp"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return str(base)
        except OSError:
            if os.name == "nt":
                fallback = Path.home() / "AppData" / "Roaming" / "资料搜索助手"
            else:
                fallback = Path.home() / "Library" / "Application Support" / "资料搜索助手"
            fallback.mkdir(parents=True, exist_ok=True)
            return str(fallback)
    return str(Path(__file__).resolve().parent)
