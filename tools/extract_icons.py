# -*- coding: utf-8 -*-
"""从本地已安装的脚本软件中提取图标，生成 GameHub 使用的 assets/*.png。

用法（在仓库根目录）:  python tools/extract_icons.py
脚本会自动在 GameHub 同级的上级目录里寻找 MAA.exe / MaaNTE.exe / ok-ww.exe / MaaEnd.exe
（或 MaaEnd 自带的 logo.png），然后输出 256x256 的透明背景图标。
"""
import ctypes
import glob
import os
from ctypes import wintypes

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
SCRIPTS_DIR = os.path.dirname(ROOT)      # 脚本软件所在目录
os.makedirs(ASSETS, exist_ok=True)

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

# 显式声明句柄类型，避免 64 位句柄在默认 c_int 参数下溢出
gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
gdi32.DeleteObject.restype = wintypes.BOOL
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.DeleteDC.restype = wintypes.BOOL
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
gdi32.SelectObject.restype = wintypes.HANDLE
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateDIBSection.restype = wintypes.HBITMAP
gdi32.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT,
                                   ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE,
                                   wintypes.DWORD]
user32.GetDC.restype = wintypes.HDC
user32.GetDC.argtypes = [wintypes.HWND]
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.DestroyIcon.argtypes = [wintypes.HICON]
user32.DrawIconEx.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.HICON,
                              ctypes.c_int, ctypes.c_int, wintypes.UINT, wintypes.HANDLE,
                              wintypes.UINT]

DI_NORMAL = 0x0003
DIB_RGB_COLORS = 0


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", wintypes.HBITMAP),
        ("hbmColor", wintypes.HBITMAP),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


def _hicon_to_image(hicon, size=256):
    info = ICONINFO()
    if not user32.GetIconInfo(hicon, ctypes.byref(info)):
        raise OSError("GetIconInfo failed")
    hdc = user32.GetDC(None)
    try:
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = size
        bmi.bmiHeader.biHeight = -size
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0

        bits = ctypes.c_void_p()
        hbmp = gdi32.CreateDIBSection(hdc, ctypes.byref(bmi), DIB_RGB_COLORS,
                                      ctypes.byref(bits), None, 0)
        if not hbmp:
            raise OSError("CreateDIBSection failed")
        memdc = gdi32.CreateCompatibleDC(hdc)
        old = gdi32.SelectObject(memdc, hbmp)
        try:
            if not user32.DrawIconEx(memdc, 0, 0, hicon, size, size, 0, None, DI_NORMAL):
                raise OSError("DrawIconEx failed")
            buf = ctypes.string_at(bits, size * size * 4)
        finally:
            gdi32.SelectObject(memdc, old)
            gdi32.DeleteDC(memdc)
            gdi32.DeleteObject(hbmp)
    finally:
        user32.ReleaseDC(None, hdc)
        if info.hbmColor:
            gdi32.DeleteObject(info.hbmColor)
        if info.hbmMask:
            gdi32.DeleteObject(info.hbmMask)
        user32.DestroyIcon(hicon)

    return Image.frombuffer("RGBA", (size, size), buf, "raw", "BGRA", 0, 1).copy()


def extract_icon(exe_path, size=256):
    hicons = (wintypes.HICON * 1)()
    if hasattr(user32, "PrivateExtractIconsW"):
        n = user32.PrivateExtractIconsW(
            ctypes.c_wchar_p(exe_path), 0, size, size, hicons, None, 1, 0)
        if n and n > 0 and hicons[0]:
            return _hicon_to_image(hicons[0], size)
    large = wintypes.HICON()
    small = wintypes.HICON()
    if user32.ExtractIconExW(ctypes.c_wchar_p(exe_path), 0,
                             ctypes.byref(large), ctypes.byref(small), 1) > 0:
        handle = large if large else small
        if handle:
            return _hicon_to_image(handle, size)
    return None


def fit_square(img, out_size, pad_ratio=0.02):
    """缩放到正方形，保持比例并居中；透明背景。"""
    img = img.convert("RGBA")
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    inner = int(out_size * (1 - pad_ratio * 2))
    w, h = img.size
    scale = min(inner / w, inner / h)
    new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
    img = img.resize(new_size, Image.LANCZOS)
    canvas = Image.new("RGBA", (out_size, out_size), (0, 0, 0, 0))
    canvas.paste(img, ((out_size - new_size[0]) // 2,
                       (out_size - new_size[1]) // 2), img)
    return canvas


def find_file(names, extra_globs=(), max_depth=4):
    """在脚本目录里找指定文件（跳过重目录）。"""
    skip = {"cache", "data", "resource", "python", "lib", "site-packages",
            "ebwebview", "repo", "debug", "agent", "thirdparty", "maafw",
            "__pycache__", "logs", "locales", "tasks", ".git", "dist", "build"}
    for pattern in extra_globs:
        hits = glob.glob(os.path.join(SCRIPTS_DIR, pattern), recursive=True)
        if hits:
            return sorted(hits)[0]
    names = {n.lower() for n in names}
    for dirpath, dirnames, filenames in os.walk(SCRIPTS_DIR):
        depth = dirpath[len(SCRIPTS_DIR):].count(os.sep)
        if depth >= max_depth:
            dirnames[:] = []
        else:
            dirnames[:] = [d for d in dirnames
                           if d.lower() not in skip and not d.startswith(".")]
        for name in filenames:
            if name.lower() in names:
                return os.path.join(dirpath, name)
    return None


TARGETS = [
    ("maa", ["MAA.exe"]),
    ("nte", ["MaaNTE.exe"]),
    ("wuwa", ["ok-ww.exe"]),
    ("maaend", ["MaaEnd.exe"]),
]


def main():
    for key, names in TARGETS:
        source = find_file(names)
        if key == "maaend":
            # MaaEnd 自带官方 logo PNG，优先使用（比从 exe 提取更清晰）
            logo = find_file([], extra_globs=[os.path.join("MaaEnd*", "locales",
                                                          "MaaEnd-Tiny.png")])
            if logo:
                source = logo
        if not source:
            print(f"[跳过] 没有找到 {names}")
            continue
        try:
            if source.lower().endswith(".png"):
                icon = Image.open(source).convert("RGBA")
            else:
                icon = extract_icon(source, 256)
            if icon is None:
                print(f"[失败] 无法提取图标: {source}")
                continue
            out = os.path.join(ASSETS, f"{key}.png")
            fit_square(icon, 256).save(out)
            print(f"[完成] {key}: {out}")
        except Exception as exc:
            print(f"[失败] {key}: {exc}")
    print("[完成] 图标更新完毕，窗口图标由 build_assets.py 生成")


if __name__ == "__main__":
    main()
