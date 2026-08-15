# -*- coding: utf-8 -*-
"""把用户提供的图片居中裁剪为正方形，并生成 Mac 应用图标 icon.icns。

用法：.venv/bin/python make_icon_from_image.py <图片路径>
"""

import os
import sys

from PIL import Image


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "icon.png"
    img = Image.open(src).convert("RGBA")
    w, h = img.size
    # 居中裁剪为正方形
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))
    # 缩放到 1024 基准，并生成多尺寸 icns
    base = img.resize((1024, 1024), Image.LANCZOS)
    base.save("icon.png")
    sizes = [1024, 512, 256, 128, 64, 32, 16]
    images = [base] + [base.resize((s, s), Image.LANCZOS) for s in sizes[1:]]
    images[0].save("icon.icns", format="ICNS", append_images=images[1:])
    print(f"来源: {src}（{w}x{h}，已居中裁剪为 {side}x{side}）")
    print("icon.icns 生成完成，大小:", os.path.getsize("icon.icns"))


if __name__ == "__main__":
    main()
