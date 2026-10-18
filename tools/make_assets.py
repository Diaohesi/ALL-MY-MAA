# -*- coding: utf-8 -*-
"""生成程序自身的图标资源（窗口图标、快捷方式图标、自定义卡片占位图标）。

用法（仓库根目录）: python tools/make_assets.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from PIL import Image, ImageDraw  # noqa: E402

from gamehub import render, theme  # noqa: E402

ASSETS = os.path.join(ROOT, "assets")


def make_custom_placeholder():
    """自定义游戏没有图标时的占位图：深色圆角方块 + 彩色小点。"""
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([24, 24, 232, 232], 48, fill=(24, 31, 44, 255),
                        outline=(52, 66, 88, 255), width=4)
    for i, (dx, dy) in enumerate([(96, 104), (160, 104), (96, 168), (160, 168)]):
        color = render.hex2rgb(theme.ACCENT_PRESETS[i][1])
        d.ellipse([dx - 16, dy - 16, dx + 16, dy + 16], fill=(*color, 255))
    img.save(os.path.join(ASSETS, "custom.png"))
    print("custom.png 已生成")


def main():
    os.makedirs(ASSETS, exist_ok=True)
    hub = render.render_hub_icon()
    hub.save(os.path.join(ASSETS, "hub.png"))
    hub.save(os.path.join(ASSETS, "hub.ico"),
             sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("hub.png / hub.ico 已生成")
    make_custom_placeholder()


if __name__ == "__main__":
    main()
