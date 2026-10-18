# -*- coding: utf-8 -*-
"""游戏脚本中心 · GameHub Lite v0.4.0 —— 程序入口。

双击「启动游戏中心.bat」运行；也可以直接 python hub.pyw。
依赖：Python 3.10+、tkinter、Pillow（pip install pillow）。
"""
import ctypes
import os
import sys

# 保证源码运行 / PyInstaller 打包运行都能找到 gamehub 包
APP_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False)
                                          else __file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

try:
    import PIL  # noqa: F401
except Exception:
    ctypes.windll.user32.MessageBoxW(
        0,
        "缺少 Pillow 依赖，界面无法绘制。\n\n"
        "请先打开命令行运行：\n"
        "    python -m pip install pillow\n\n"
        "或使用打包好的 GameHub.exe。",
        "游戏脚本中心", 0x10)
    raise SystemExit(1)

from gamehub.ui import run  # noqa: E402


if __name__ == "__main__":
    run()
