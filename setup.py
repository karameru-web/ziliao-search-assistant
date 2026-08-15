# -*- coding: utf-8 -*-
"""py2app 打包配置：生成 资料搜索助手.app。"""

import os

from setuptools import setup

APP = [{"script": "desktop_app.py"}]

# 把 templates / static 整目录打进 Contents/Resources
DATA_FILES = []
for root in ("templates", "static"):
    for dirpath, _dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, ".")
        files = [os.path.join(dirpath, f) for f in filenames]
        if files:
            DATA_FILES.append((rel, files))

LOCAL_MODULES = [
    "app", "crawler", "processor", "service", "evaluator", "keyword_utils",
    "search_manager", "upload_manager", "shelf", "progress_store", "paths",
]

OPTIONS = {
    "argv_emulation": False,
    "iconfile": "icon.icns",
    "includes": LOCAL_MODULES,
    "packages": [
        "flask", "requests", "bs4", "lxml", "pypdf", "webview", "bottle",
        "werkzeug", "jinja2", "markupsafe", "click", "itsdangerous", "blinker",
    ],
    "plist": {
        "CFBundleName": "资料搜索助手",
        "CFBundleDisplayName": "资料搜索助手",
        "CFBundleIdentifier": "com.ziliao.search.assistant",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "11.0",
        "NSRequiresAquaSystemAppearance": False,
    },
}

setup(
    app=APP,
    name="资料搜索助手",
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
)
