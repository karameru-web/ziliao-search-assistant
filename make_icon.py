# -*- coding: utf-8 -*-
"""生成简单占位图标：暖色圆角方块 + “资料”两个白字，再转成 .icns。"""

import os
from PIL import Image, ImageDraw, ImageFont


def main():
    size = 1024
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # 圆角方块（暖珊瑚色）
    draw.rounded_rectangle([64, 64, size - 64, size - 64], radius=190, fill=(242, 169, 127, 255))
    # 尝试写“资料”两个白字
    font = None
    for font_path in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
    ):
        try:
            font = ImageFont.truetype(font_path, 300)
            break
        except OSError:
            continue
    if font is not None:
        text = "资料"
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        draw.text(
            ((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]),
            text,
            font=font,
            fill=(255, 255, 255, 255),
        )
    img.save("icon.png")
    img.save("icon.icns", format="ICNS")  # Pillow 原生支持 icns
    print("icon.icns 生成完成，大小:", os.path.getsize("icon.icns"))


if __name__ == "__main__":
    main()
