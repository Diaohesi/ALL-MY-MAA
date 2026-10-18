# -*- coding: utf-8 -*-
"""截图预览工具：把鼠标移到指定卡片上并截取 Hub 窗口。

用法: python preview.py <输出png> [卡片序号]
"""
import ctypes
import sys
import time
from ctypes import wintypes

from PIL import ImageGrab

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

TITLE = "游戏脚本中心"


class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


def find_window(title=TITLE):
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _l):
        cls = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, cls, 64)
        if cls.value == "TkTopLevel":
            text = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, text, 256)
            if text.value == title:
                found.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "preview.png"
    # 可选参数：客户区坐标 dx dy；也兼容传卡片序号（0/1/2）
    dx = dy = None
    if len(sys.argv) > 3:
        dx, dy = int(sys.argv[2]), int(sys.argv[3])
    elif len(sys.argv) > 2:
        card = int(sys.argv[2])
        dx = [48, 352, 656][card] + 138
        dy = 126 + 190
    hwnd = find_window()
    if not hwnd:
        print("窗口未找到（Hub 是否在运行？）")
        return 1
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    user32.SwitchToThisWindow(hwnd, True)
    time.sleep(0.35)

    rect = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    client = POINT()
    user32.ClientToScreen(hwnd, ctypes.byref(client))

    if dx is not None:
        user32.SetCursorPos(client.x + dx, client.y + dy)
        time.sleep(0.5)

    img = ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom))
    img.save(out)
    print(f"saved {out} rect={rect.left},{rect.top} client={client.x},{client.y} size={img.size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
