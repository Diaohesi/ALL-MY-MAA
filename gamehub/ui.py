# -*- coding: utf-8 -*-
"""主界面与对话框：卡片、工具栏、添加/编辑游戏、启动/下载等交互。"""
import ctypes
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import urllib.request
import webbrowser
import zipfile
from ctypes import wintypes
from tkinter import filedialog, messagebox

from PIL import Image, ImageDraw, ImageTk

from . import VERSION, daily, detector, feedback, render, runtime_log, store, tray, window_state
from . import theme as T

TITLE = "All-My-Maa · 游戏脚本中心"

# v0.10 字体缩放（0.9 小 / 1.0 标准 / 1.12 大 / 1.25 特大）
_FONT_SCALE = 1.0


def _scaled_font(size, family=None):
    """对话框/旧控件用的缩放字体元组（size 为负的像素字号）。"""
    try:
        base = abs(int(size))
    except (TypeError, ValueError):
        base = 11
    return (family or T.UI_FONT, -max(2, int(round(base * _FONT_SCALE))))


def titlebar_buttons(maximized):
    """自定义标题栏按钮状态（纯逻辑，供测试）。"""
    return {
        "maximized": bool(maximized),
        "minimize": "—",
        "maximize": "❐" if maximized else "□",
        "close": "✕",
    }


def window_scale_value(value, default=1.0):
    """font_scale 非法值回退默认。"""
    try:
        scale = float(value)
    except (TypeError, ValueError):
        return default
    return scale if scale in [float(item) for item in store.FONT_SCALES] \
        else default

# 软件更新（只检查/展示，不自动下载安装）
GITHUB_REPO = "Diaohesi/All-My-Maa"
PROJECT_PAGES = "https://diaohesi.github.io/All-My-Maa/"
PROJECT_GITHUB = "https://github.com/Diaohesi/All-My-Maa"
RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASE_PAGE = f"https://github.com/{GITHUB_REPO}/releases/latest"

# v0.9.1 UI 图标资源（assets/ 或 PyInstaller _MEIPASS/assets，见 store.ASSETS）
BRAND_ICON_FILE = "LinYuxia.png"
PAGE_ICON_FILES = {
    "home": "page_home.png",
    "daily": "page_daily.png",
    "settings": "page_settings.png",
    "about": "page_about.png",
}
ICON_SIZES = {
    "window": 64,       # 主窗口/任务栏大图
    "window_small": 32,  # 主窗口/任务栏小图
    "brand": 46,        # 侧边栏品牌 44-48
    "nav": 21,          # 导航按钮 20-22
    "page": 30,         # 页面标题 28-32
    "about": 64,        # 关于对话框
}
# 缺失时的优雅回退（按顺序查找）
ICON_FALLBACKS = {
    "brand": ("hub.png",),
    "about": ("LinYuxia.png", "hub.png"),
}


def icon_asset_file(name):
    """图标逻辑名 -> 文件名；未知名称返回空串。"""
    if name == "brand":
        return BRAND_ICON_FILE
    return PAGE_ICON_FILES.get(name, "")


def icon_path(name):
    """图标文件的绝对路径；文件不存在返回空串。"""
    filename = icon_asset_file(name)
    if not filename:
        return ""
    path = os.path.join(store.ASSETS, filename)
    return path if os.path.isfile(path) else ""


def resolve_icon_path(name):
    """带回退的图标路径：缺品牌/关于图标时回退到旧 hub.png / LinYuxia。"""
    path = icon_path(name)
    if path:
        return path
    for fallback in ICON_FALLBACKS.get(name, ()):
        candidate = os.path.join(store.ASSETS, fallback)
        if os.path.isfile(candidate):
            return candidate
    return ""


def _parent_bg(master):
    try:
        return master.cget("bg")
    except Exception:
        return T.UI_BG


def _round_rect(canvas, x1, y1, x2, y2, radius, fill, outline="",
                width=1, tags=None):
    """在 Canvas 上画平滑圆角矩形（用平滑多边形近似，避免逐像素图片）。"""
    radius = max(0, min(int(radius), int((x2 - x1) // 2), int((y2 - y1) // 2)))
    if radius <= 0:
        return canvas.create_rectangle(x1, y1, x2, y2, fill=fill,
                                       outline=outline, width=width,
                                       tags=tags)
    points = [
        x1 + radius, y1, x2 - radius, y1,
        x2, y1, x2, y1 + radius,
        x2, y2 - radius, x2, y2,
        x2 - radius, y2, x1 + radius, y2,
        x1, y2, x1, y2 - radius,
        x1, y1 + radius, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=24,
                                 fill=fill, outline=outline, width=width,
                                 tags=tags)


class RoundButton(tk.Canvas):
    """v0.9 自绘圆角按钮：默认/悬停/按下/禁用/主按钮 5 态。"""

    def __init__(self, master, text="", command=None, kind="normal",
                 width=None, font=None, state="normal", height=36,
                 accent=None, radius=None, bg=None, anchor="center",
                 photo=None, **kwargs):
        self._parent_bg = bg or _parent_bg(master)
        super().__init__(master, bg=self._parent_bg, highlightthickness=0,
                         bd=0, height=height, cursor="hand2",
                         takefocus=True)
        self._text = str(text or "")
        self._command = command
        self._kind = kind
        self._anchor = anchor
        self._state = state
        self._photo = photo
        self._hover = False
        self._pressed = False
        self._focused = False
        self._selected = False
        self._fg_override = None
        self._bg_override = None
        self._accent = accent or T.UI_ACCENT
        self._radius = radius or T.RADIUS_BUTTON
        self._font = font or tkfont.Font(family=T.UI_FONT, size=-11,
                                         weight="bold")
        self._height = height
        self._base_height = height
        self._explicit_width = width
        if width:
            self._width = int(width) * 9 + 26
        else:
            extra = (photo.width() + 12) if photo is not None else 0
            self._width = max(78, self._font.measure(self._text) + 30 + extra)
        super().configure(width=self._width)
        self.bind("<Configure>", lambda e: self._redraw(), add="+")
        self.bind("<Enter>", self._on_enter, add="+")
        self.bind("<Leave>", self._on_leave, add="+")
        self.bind("<ButtonPress-1>", self._on_press, add="+")
        self.bind("<ButtonRelease-1>", self._on_release, add="+")
        self.bind("<FocusIn>", self._on_focus, add="+")
        self.bind("<FocusOut>", self._on_blur, add="+")
        self._redraw()

    # 兼容旧 tk.Button 用法
    def configure(self, **kwargs):
        redraw = False
        for key, value in kwargs.items():
            if key == "text":
                self._text = str(value or "")
                redraw = True
            elif key == "state":
                self._state = str(value)
                self.configure(cursor="arrow" if value == "disabled"
                               else "hand2")
                redraw = True
            elif key == "command":
                self._command = value
            elif key == "photo":
                self._photo = value
                redraw = True
            elif key == "font":
                self._font = value
                redraw = True
            elif key == "fg":
                self._fg_override = value
                redraw = True
            elif key == "bg":
                self._bg_override = value
                redraw = True
            elif key in ("activebackground", "activeforeground"):
                continue
            elif key == "width":
                self._width = int(value) * 9 + 26
                super().configure(width=self._width)
                redraw = True
            else:
                try:
                    super().configure(**{key: value})
                except Exception:
                    pass
        if redraw:
            self._redraw()
        return self

    def cget(self, key):
        if key == "text":
            return self._text
        if key == "state":
            return self._state
        if key == "fg":
            return getattr(self, "_fg_override", None) or T.UI_TEXT
        if key == "bg":
            return getattr(self, "_bg_override", None) or self._parent_bg
        return super().cget(key)

    def set_accent(self, accent):
        self._accent = accent or T.UI_ACCENT
        self._redraw()

    def set_selected(self, selected):
        self._selected = bool(selected)
        self._redraw()

    def set_text(self, text):
        self._text = str(text or "")
        self._redraw()

    def apply_scale(self, scale):
        """v0.10 字体缩放：同步按钮高度/宽度。"""
        try:
            scale = float(scale)
        except (TypeError, ValueError):
            scale = 1.0
        self._height = max(24, int(round(self._base_height * scale)))
        super().configure(height=self._height)
        if self._explicit_width:
            self._width = max(64, int(round(
                (int(self._explicit_width) * 9 + 26) * scale)))
        else:
            photo_w = self._photo.width() if self._photo is not None else 0
            self._width = max(64, int(round(
                (self._font.measure(self._text) + 30 + photo_w) * scale)))
        super().configure(width=self._width)
        self._redraw()

    # 状态事件
    def _on_enter(self, _event=None):
        if self._state != "disabled":
            self._hover = True
            self._redraw()

    def _on_leave(self, _event=None):
        self._hover = False
        self._pressed = False
        self._redraw()

    def _on_press(self, _event=None):
        if self._state == "disabled":
            return
        self._pressed = True
        self.focus_set()
        self._redraw()

    def _on_release(self, event=None):
        if self._state == "disabled":
            return
        was = self._pressed
        self._pressed = False
        self._redraw()
        if was and event is not None:
            inside = 0 <= event.x <= self.winfo_width() and \
                0 <= event.y <= self.winfo_height()
            if inside and self._command:
                try:
                    self._command()
                except Exception:
                    pass

    def _on_focus(self, _event=None):
        self._focused = True
        self._redraw()

    def _on_blur(self, _event=None):
        self._focused = False
        self._redraw()

    def _colors(self):
        accent = getattr(self, "_accent", T.UI_ACCENT)
        selected = getattr(self, "_selected", False)
        if self._state == "disabled":
            return T.UI_PANEL, T.UI_TEXT_3, T.UI_BORDER_SOFT
        if self._kind == "primary":
            fill, fg, border = accent, "#071018", accent
        elif self._kind == "danger":
            fill, fg, border = T.UI_DANGER_SOFT, T.UI_DANGER, "#4a2c3a"
        elif self._kind == "ghost":
            if selected:
                fill, fg, border = T.UI_ACCENT_SOFT, accent, accent
            else:
                fill, fg, border = T.UI_PANEL, T.UI_TEXT_2, T.UI_BORDER_SOFT
        else:
            fill, fg, border = T.UI_PANEL_2, T.UI_TEXT, T.UI_BORDER
        if self._kind == "primary" and self._hover:
            fill = _mix(accent, "#ffffff", 0.14)
        elif self._kind == "primary" and self._pressed:
            fill = _mix(accent, "#000000", 0.12)
        elif self._kind != "ghost" and self._hover:
            fill = T.UI_PANEL_3
        elif self._kind == "ghost" and self._hover:
            fill = T.UI_PANEL_2 if not selected else T.UI_ACCENT_SOFT
        if self._focused:
            border = accent
        if self._kind == "ghost" and not selected:
            fill = self._bg_override or fill
        return fill, fg, border

    def _redraw(self):
        self.delete("all")
        width = max(4, self.winfo_width())
        height = max(4, self.winfo_height())
        fill, fg, border = self._colors()
        if self._kind == "primary" and self._state != "disabled":
            top = _mix(self._accent, "#ffffff", 0.20)
            bottom = _mix(self._accent, "#000000", 0.10)
            if self._pressed:
                top = _mix(top, "#000000", 0.10)
                bottom = _mix(bottom, "#000000", 0.10)
            elif self._hover:
                top = _mix(top, "#ffffff", 0.08)
            photo = _rounded_gradient_photo(
                self, width, height, top, bottom, self._radius)
            if photo is not None:
                self.create_image(0, 0, image=photo, anchor="nw")
                _round_rect(self, 0.5, 0.5, width - 1, height - 1,
                            self._radius, "", self._accent, 1)
                fill = None
        if fill is not None:
            _round_rect(self, 0.5, 0.5, width - 1, height - 1, self._radius,
                        fill, border, 1)
        if self._photo is not None:
            photo_w = self._photo.width()
            if self._anchor == "w":
                self.create_image(16, height / 2, image=self._photo,
                                  anchor="w")
                text_x = 16 + photo_w + 10
            else:
                text_w = self._font.measure(self._text)
                total = photo_w + 10 + text_w
                start = max(8, (width - total) / 2)
                self.create_image(start, height / 2, image=self._photo,
                                  anchor="w")
                text_x = start + photo_w + 10
            self.create_text(text_x, height / 2, text=self._text, fill=fg,
                             font=self._font, anchor="w")
            return
        if self._anchor == "w":
            text_x = 16
            anchor = "w"
        else:
            text_x = width / 2
            anchor = "center"
        self.create_text(text_x, height / 2, text=self._text, fill=fg,
                         font=self._font, anchor=anchor)


def _mix(color, other, ratio):
    """把两个 #rrggbb 颜色按比例混合（用于 hover/pressed/渐变）。"""
    try:
        a = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
        b = [int(other[i:i + 2], 16) for i in (1, 3, 5)]
        return "#" + "".join(f"{int(x + (y - x) * ratio):02x}"
                             for x, y in zip(a, b))
    except Exception:
        return color


_GRADIENT_PHOTO_CACHE = {}


def _rounded_gradient_photo(master, width, height, top, bottom, radius):
    """v0.10 主按钮渐变（Pillow + 圆角遮罩 + ImageTk）。"""
    try:
        width, height, radius = int(width), int(height), int(radius)
        if width < 2 or height < 2:
            return None
        key = (master, width, height, top, bottom, radius)
        if key in _GRADIENT_PHOTO_CACHE:
            return _GRADIENT_PHOTO_CACHE[key]
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        a = [int(top[i:i + 2], 16) for i in (1, 3, 5)]
        b = [int(bottom[i:i + 2], 16) for i in (1, 3, 5)]
        for row in range(height):
            ratio = row / max(1, height - 1)
            color = tuple(int(x + (y - x) * ratio) for x, y in zip(a, b))
            draw.line([(0, row), (width, row)], fill=color + (255,))
        mask = Image.new("L", (width, height), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, width - 1, height - 1), radius=radius, fill=255)
        image.putalpha(mask)
        photo = ImageTk.PhotoImage(image, master=master)
        _GRADIENT_PHOTO_CACHE[key] = photo
        return photo
    except Exception:
        return None


class RoundPanel(tk.Canvas):
    """v0.9 圆角卡片/面板容器；内容放进 .inner Frame。"""

    def __init__(self, master, fill=None, border=None, radius=None,
                 pad=None, bg=None, **kwargs):
        self._parent_bg = bg or _parent_bg(master)
        super().__init__(master, bg=self._parent_bg, highlightthickness=0,
                         bd=0, **kwargs)
        self._fill = fill or T.UI_PANEL
        self._border = border or T.UI_BORDER
        self._radius = radius or T.RADIUS_PANEL
        self._pad = pad if pad is not None else T.SPACE_UI_MD
        self.inner = tk.Frame(self, bg=self._fill)
        self._win = self.create_window(self._pad, self._pad,
                                       window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner, add="+")
        self.bind("<Configure>", self._on_canvas, add="+")

    def _on_inner(self, event=None):
        height = event.height if event is not None else self.inner.winfo_reqheight()
        self.configure(height=height + self._pad * 2)

    def _on_canvas(self, event=None):
        width = self.winfo_width()
        self.itemconfigure(self._win, width=max(10, width - self._pad * 2))
        self.delete("panel-bg")
        _round_rect(self, 0.5, 0.5, width - 1,
                    max(10, self.winfo_height()) - 1, self._radius,
                    self._fill, self._border, 1, tags="panel-bg")
        self.tag_lower("panel-bg")

    def set_border(self, color):
        self._border = color
        self._on_canvas()


class RoundEntry(tk.Frame):
    """v0.9 圆角输入框（保留 get/insert/delete 接口以兼容现有代码）。"""

    def __init__(self, master, value="", width=18, font=None,
                 textvariable=None, bg=None):
        self._parent_bg = bg or _parent_bg(master)
        super().__init__(master, bg=self._parent_bg)
        self._font = font or tkfont.Font(family=T.UI_FONT,
                                         size=-T.UI_FONT_SIZES["body"])
        self._canvas = tk.Canvas(self, bg=self._parent_bg,
                                 highlightthickness=0, bd=0, height=34,
                                 width=max(90, int(width) * 8 + 24))
        self._canvas.pack(fill="both", expand=True)
        self.var = textvariable or tk.StringVar(value=str(value or ""))
        self.entry = tk.Entry(self._canvas, textvariable=self.var,
                              bg=T.UI_PANEL_2, fg=T.UI_TEXT,
                              insertbackground=T.UI_TEXT, relief="flat",
                              bd=0, highlightthickness=0, font=self._font,
                              width=max(4, int(width)))
        self._win = self._canvas.create_window(12, 17, window=self.entry,
                                               anchor="w")
        self._focused = False
        self.entry.bind("<FocusIn>", self._focus, add="+")
        self.entry.bind("<FocusOut>", self._blur, add="+")
        self._canvas.bind("<Configure>", lambda e: self._draw(), add="+")
        self._draw()

    def _focus(self, _event=None):
        self._focused = True
        self._draw()

    def _blur(self, _event=None):
        self._focused = False
        self._draw()

    def _draw(self):
        canvas = self._canvas
        width = max(10, canvas.winfo_width())
        canvas.delete("all")
        accent = T.UI_ACCENT
        _round_rect(canvas, 0.5, 0.5, width - 1, 33.5, T.RADIUS_INPUT,
                    T.UI_PANEL_2, accent if self._focused else T.UI_BORDER, 1)
        self._win = canvas.create_window(12, 17, window=self.entry,
                                         anchor="w")
        canvas.itemconfigure(self._win, width=max(20, width - 24))

    def get(self):
        return self.var.get()

    def insert(self, index, text):
        self.entry.insert(index, text)

    def delete(self, first, last=None):
        self.entry.delete(first, last)

    def focus_set(self):
        self.entry.focus_set()


def _dark_titlebar(root):
    try:
        user32 = ctypes.windll.user32
        dwm = ctypes.WinDLL("dwmapi")
        hwnd = user32.GetAncestor(root.winfo_id(), 2)
        caption = 0x00140E0B
        for attr, value in ((20, 1), (34, caption), (35, caption), (36, 0x00F9F5F2)):
            v = ctypes.c_int(value)
            dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))
    except Exception:
        pass


def _flat_button(parent, text, command, accent=False):
    """深色扁平按钮（添加/编辑等对话框共用）。"""
    bg = T.UI_ACCENT if accent else T.UI_PANEL_2
    active = _mix(T.UI_ACCENT, "#000000", 0.12) if accent else T.UI_PANEL_3
    fg = "#071018" if accent else T.UI_TEXT
    return tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                     activebackground=active, activeforeground=fg,
                     relief="flat", bd=0, padx=14, pady=5,
                     font=_scaled_font(-11), cursor="hand2")


class AppDialog(tk.Toplevel):
    """添加 / 编辑一个游戏脚本卡片。"""

    FIELDS = [
        ("game", "游戏名称 *", "例如：明日方舟"),
        ("script", "脚本名称 *", "例如：MAA"),
        ("script_exe", "脚本启动程序 *", ""),
        ("script_procs", "脚本进程名", "可选，多个用逗号分隔"),
        ("game_exe", "游戏启动程序", "可选，用于「启动游戏」"),
        ("game_procs", "游戏进程名", "可选，用于显示游戏运行状态"),
        ("site", "脚本官网", "可选"),
        ("github", "GitHub 地址", "可选"),
        ("release", "更新检查地址", "可选，GitHub releases/latest"),
        ("download", "游戏下载页", "可选，点「下载游戏」时打开"),
        ("icon", "自定义图标", "可选，png / ico"),
    ]

    # 检测规则（用于判断「游戏运行中」；留空则用脚本自动规则）
    DETECT_FIELDS = [
        ("win_class", "检测：窗口类", "正则，如 ^UnrealWindow$"),
        ("win_title", "检测：窗口标题", "正则，如 异环"),
        ("detect_procs", "检测：进程名", "多个用逗号分隔"),
        ("adb_pkg", "检测：ADB 包名", "可选，多个用逗号分隔"),
    ]

    def __init__(self, master, app=None, on_save=None, on_delete=None):
        super().__init__(master)
        self.title("编辑游戏卡片" if app else "添加游戏")
        self.configure(bg=T.UI_BG)
        self.resizable(False, False)
        self.transient(master)
        self.on_save = on_save
        self.on_delete = on_delete
        self.editing = app is not None
        self.app = app or {}
        self.values = {}
        self.accent = self.app.get("accent") or T.ACCENT_PRESETS[0][1]
        self._chip_refs = []
        try:
            self.detect_initial = detector.rules_to_fields(
                detector.read_game_rules(self.app))
        except Exception:
            self.detect_initial = {}
        self._build()
        self.minsize(640, 0)
        self.grab_set()
        self._center()

    # ---------------------------------------------------------- 界面
    def _entry(self, parent, value=""):
        entry = tk.Entry(parent, bg=T.UI_PANEL, fg=T.UI_TEXT, insertbackground=T.UI_TEXT,
                         relief="flat", highlightthickness=1,
                         highlightbackground="#2a3547", highlightcolor="#4fc3ff",
                         font=_scaled_font(-11), width=34)
        entry.insert(0, value or "")
        return entry

    def _button(self, parent, text, command, accent=False):
        return _flat_button(parent, text, command, accent=accent)

    def _build(self):
        pad = 18
        body = tk.Frame(self, bg=T.UI_BG)
        body.pack(fill="both", expand=True, padx=pad, pady=(pad, 6))
        body.columnconfigure(1, weight=1)

        tk.Label(body, text="填写后保存即可，路径会自动记录成相对路径",
                 bg=T.UI_BG, fg=T.UI_TEXT_3,
                 font=_scaled_font(-10)).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        row = 1
        for field, label, hint in self.FIELDS:
            tk.Label(body, text=label, bg=T.UI_BG, fg=T.UI_TEXT_2,
                     font=_scaled_font(-11), anchor="e", width=14).grid(
                row=row, column=0, sticky="e", pady=4)
            entry = self._entry(body, self.app.get(field, ""))
            entry.grid(row=row, column=1, sticky="we", pady=4)
            self.values[field] = entry
            if field == "game_exe":
                box = tk.Frame(body, bg=T.UI_BG)
                box.grid(row=row, column=2, sticky="w", padx=(8, 0), pady=4)
                self._button(box, "浏览", lambda: self._browse("game_exe")).pack(
                    side="left")
                self._button(box, "自动检测", self._auto_detect_game).pack(
                    side="left", padx=(6, 0))
            elif field in ("script_exe", "icon"):
                self._button(body, "浏览", lambda f=field: self._browse(f)).grid(
                    row=row, column=2, padx=(8, 0), pady=4)
            elif hint:
                tk.Label(body, text=hint, bg=T.UI_BG, fg=T.UI_TEXT_3,
                         font=_scaled_font(-10), anchor="w").grid(
                    row=row, column=2, sticky="w", padx=(8, 0))
            row += 1

        # 检测规则（可选）
        tk.Frame(body, bg=T.UI_BORDER, height=1).grid(
            row=row, column=0, columnspan=3, sticky="we", pady=(10, 2))
        row += 1
        tk.Label(body, text="检测规则（可选，用于准确判断「游戏运行中」）",
                 bg=T.UI_BG, fg=T.UI_TEXT_3,
                 font=_scaled_font(-10)).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(2, 4))
        row += 1
        for field, label, hint in self.DETECT_FIELDS:
            tk.Label(body, text=label, bg=T.UI_BG, fg=T.UI_TEXT_2,
                     font=_scaled_font(-11), anchor="e", width=14).grid(
                row=row, column=0, sticky="e", pady=4)
            entry = self._entry(body, self.detect_initial.get(field, ""))
            entry.grid(row=row, column=1, sticky="we", pady=4)
            self.values[field] = entry
            if hint:
                tk.Label(body, text=hint, bg=T.UI_BG, fg=T.UI_TEXT_3,
                         font=_scaled_font(-10), anchor="w").grid(
                    row=row, column=2, sticky="w", padx=(8, 0))
            row += 1

        # 主题色
        tk.Label(body, text="主题色", bg=T.UI_BG, fg=T.UI_TEXT_2,
                 font=_scaled_font(-11), anchor="e", width=14).grid(
            row=row, column=0, sticky="e", pady=6)
        colors = tk.Frame(body, bg=T.UI_BG)
        colors.grid(row=row, column=1, columnspan=2, sticky="w", pady=6)
        for name, color in T.ACCENT_PRESETS:
            chip = tk.Frame(colors, bg=color, width=26, height=26,
                            highlightthickness=3,
                            highlightbackground=T.UI_BG, cursor="hand2")
            chip.pack(side="left", padx=2)
            chip.bind("<Button-1>", lambda e, c=color, f=chip: self._pick_accent(c, f))
            self._chip_refs.append((color, chip))
        self._refresh_chips()

        # 底部按钮
        footer = tk.Frame(self, bg=T.UI_BG)
        footer.pack(fill="x", padx=pad, pady=(4, 14))
        self._button(footer, "保存", self._save, accent=True).pack(side="right")
        self._button(footer, "取消", self.destroy).pack(side="right", padx=(0, 8))
        if self.editing and self.on_delete and not self.app.get("builtin"):
            self._button(footer, "删除此卡片", self._delete).pack(side="left")

    def _refresh_chips(self):
        for color, chip in self._chip_refs:
            chip.configure(highlightbackground=T.UI_TEXT if color == self.accent
                           else T.UI_BG)

    def _pick_accent(self, color, chip):
        self.accent = color
        self._refresh_chips()

    def _browse(self, field):
        if field == "icon":
            path = filedialog.askopenfilename(
                parent=self, title="选择图标",
                filetypes=[("图片", "*.png;*.ico;*.jpg;*.jpeg"), ("所有文件", "*.*")])
        else:
            path = filedialog.askopenfilename(
                parent=self, title="选择可执行程序",
                filetypes=[("可执行程序", "*.exe"), ("所有文件", "*.*")])
        if path:
            self.values[field].delete(0, "end")
            self.values[field].insert(0, os.path.normpath(path))

    def _detect_target(self):
        """自动检测用的 app 信息：优先编辑中的游戏，其次看用户刚输入的名称。"""
        game = ""
        if "game" in self.values:
            game = self.values["game"].get().strip()
        return {"key": self.app.get("key", ""), "game": game or self.app.get("game", "")}

    def _auto_detect_game(self):
        info = self._detect_target()
        self.config(cursor="watch")
        try:
            self.update_idletasks()
            candidates = store.find_game_candidates(info)
        except Exception:
            candidates = []
        finally:
            self.config(cursor="")
        if not candidates:
            messagebox.showinfo(
                "未检测到游戏启动程序",
                f"没有自动找到「{info['game'] or '该游戏'}」的启动程序。\n"
                "可以点「浏览」手动选择。",
                parent=self)
            return
        dialog = GameCandidateDialog(self, candidates)
        self.wait_window(dialog)
        try:
            self.grab_set()       # 候选框关掉后恢复编辑框的模态
        except Exception:
            pass
        if dialog.result:
            path = os.path.normpath(dialog.result)
            entry = self.values["game_exe"]
            entry.delete(0, "end")
            entry.insert(0, path)
            self._fill_detect_suggestion(path)

    def _fill_detect_suggestion(self, exe_path):
        """自动检测选中启动程序后，把脚本自带的检测规则填进空着的输入框。"""
        script_entry = self.values.get("script_exe")
        script_exe = script_entry.get().strip() if script_entry is not None else ""
        try:
            rules = detector.read_auto_rules({
                "key": self.app.get("key", ""),
                "game": self.app.get("game", ""),
                "script_exe": script_exe,
            })
            suggestion = detector.rules_to_fields(rules)
        except Exception:
            suggestion = {}
        if not suggestion.get("detect_procs"):
            suggestion["detect_procs"] = os.path.basename(exe_path)
        for field in ("win_class", "win_title", "detect_procs", "adb_pkg"):
            entry = self.values.get(field)
            if entry is None or entry.get().strip():
                continue
            value = suggestion.get(field, "")
            if value:
                entry.insert(0, value)

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        master = self.master
        x = master.winfo_rootx() + (master.winfo_width() - w) // 2
        y = master.winfo_rooty() + (master.winfo_height() - h) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    # ---------------------------------------------------------- 动作
    def _collect(self):
        data = {}
        for field in self.values:
            data[field] = self.values[field].get().strip()
        data["accent"] = self.accent
        if not data["game"] or not data["script"]:
            messagebox.showwarning("请填写完整", "游戏名称和脚本名称不能为空。", parent=self)
            return None
        if not data["script_exe"] or not os.path.isfile(data["script_exe"]):
            messagebox.showwarning("路径无效", "请选择正确的脚本启动程序（.exe）。", parent=self)
            return None
        if data["game_exe"] and not os.path.isfile(data["game_exe"]):
            messagebox.showwarning("路径无效", "游戏启动程序路径不存在。", parent=self)
            return None
        return data

    def _save(self):
        data = self._collect()
        if data and self.on_save:
            self.on_save(data)
        self.destroy()

    def _delete(self):
        if self.on_delete and messagebox.askyesno(
                "删除卡片", "确定要删除这个游戏卡片吗？\n（只删除 Hub 里的卡片，不会删除文件）",
                parent=self):
            self.on_delete()
            self.destroy()


class GameCandidateDialog(tk.Toplevel):
    """游戏启动程序候选选择框（深色）：双击候选或选中后点「确定」返回路径。"""

    def __init__(self, master, candidates, title="选择游戏启动程序"):
        super().__init__(master)
        self.title(title)
        self.configure(bg=T.UI_BG)
        self.resizable(False, False)
        self.transient(master)
        self.result = None
        self.candidates = list(candidates or [])
        self._path_var = tk.StringVar(value="")
        self._build()
        self.grab_set()
        self._center(master)

    def _build(self):
        pad = 16
        tk.Label(self, text=f"找到 {len(self.candidates)} 个候选，双击或选中后点「确定」",
                 bg=T.UI_BG, fg=T.UI_TEXT_2,
                 font=_scaled_font(-11)).pack(anchor="w", padx=pad, pady=(14, 8))
        body = tk.Frame(self, bg=T.UI_PANEL, highlightthickness=1,
                        highlightbackground="#2a3547")
        body.pack(fill="both", expand=True, padx=pad)
        self.listbox = tk.Listbox(
            body, bg=T.UI_PANEL, fg=T.UI_TEXT, selectbackground=T.UI_ACCENT_SOFT,
            selectforeground="#ffffff", relief="flat", bd=0, highlightthickness=0,
            activestyle="none", font=_scaled_font(-11),
            width=96, height=min(9, max(3, len(self.candidates))))
        scroll = tk.Scrollbar(body, command=self.listbox.yview, width=10,
                              bg=T.UI_PANEL_2, troughcolor=T.UI_BG,
                              activebackground=T.UI_PANEL_3, relief="flat", bd=0,
                              highlightthickness=0)
        self.listbox.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.listbox.pack(side="left", fill="both", expand=True)
        for candidate in self.candidates:
            name = candidate.get("name") or os.path.basename(candidate.get("path", ""))
            source = candidate.get("source") or ""
            path = self._short_path(candidate.get("path", ""))
            self.listbox.insert("end", f"{name}    〔{source}〕  {path}")
        if self.candidates:
            self.listbox.selection_set(0)
            self.listbox.activate(0)
            self._show_path(0)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)
        self.listbox.bind("<Double-Button-1>", lambda event: self._confirm())
        tk.Label(self, textvariable=self._path_var, bg=T.UI_BG, fg=T.UI_TEXT_3,
                 font=_scaled_font(-10), anchor="w", justify="left",
                 wraplength=720).pack(fill="x", padx=pad, pady=(8, 0))
        footer = tk.Frame(self, bg=T.UI_BG)
        footer.pack(fill="x", padx=pad, pady=(12, 14))
        _flat_button(footer, "确定", self._confirm, accent=True).pack(side="right")
        _flat_button(footer, "取消", self._cancel).pack(side="right", padx=(0, 8))
        _flat_button(footer, "浏览…", self._browse).pack(side="left")
        self.bind("<Return>", lambda event: self._confirm())
        self.bind("<Escape>", lambda event: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    @staticmethod
    def _short_path(path, limit=44):
        """列表里用中间省略的路径，完整路径在下方单独显示。"""
        path = str(path or "")
        if len(path) <= limit:
            return path
        head = limit // 2 - 2
        tail = limit - head - 3
        return f"{path[:head]}…{path[-tail:]}"

    def _on_select(self, _event=None):
        selection = self.listbox.curselection()
        if selection:
            self._show_path(selection[0])

    def _show_path(self, index):
        if 0 <= index < len(self.candidates):
            self._path_var.set(self.candidates[index]["path"])

    def _confirm(self):
        selection = self.listbox.curselection()
        if not selection:
            if not self.candidates:
                return
            selection = (0,)
        self.result = self.candidates[selection[0]]["path"]
        self.destroy()

    def _browse(self):
        path = filedialog.askopenfilename(
            parent=self, title="手动选择游戏启动程序",
            filetypes=[("可执行程序", "*.exe"), ("所有文件", "*.*")])
        if path:
            self.result = os.path.normpath(path)
            self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()

    def _center(self, master):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        try:
            x = master.winfo_rootx() + (master.winfo_width() - w) // 2
            y = master.winfo_rooty() + (master.winfo_height() - h) // 2
        except Exception:
            x = y = 100
        x = min(max(0, x), max(0, self.winfo_screenwidth() - w))
        y = min(max(0, y), max(0, self.winfo_screenheight() - h))
        self.geometry(f"+{x}+{y}")


class TitleBar(tk.Canvas):
    """v0.10 自绘渐变标题栏：图标 + 标题 + 最小化/最大化/关闭，可拖动/双击。"""

    def __init__(self, master, hub, height=None):
        self.hub = hub
        self._height = int(height or T.TITLEBAR_H)
        super().__init__(master, bg=T.UI_GRADIENT_TOP,
                         highlightthickness=0, bd=0,
                         height=self._height)
        self._drag = None
        self._buttons = {}
        self._photo = hub._ui_icon_photo("brand", 22)
        specs = (
            ("minimize", "—", hub.minimize_window, "ghost"),
            ("maximize", "□", hub.toggle_maximize, "ghost"),
            ("close", "✕", hub._on_close, "danger"),
        )
        for name, glyph, command, kind in specs:
            button = RoundButton(self, text=glyph, command=command,
                                 kind=kind, width=3, height=26,
                                 radius=9, font=hub.f_small,
                                 bg=T.UI_GRADIENT_TOP)
            button._titlebar_name = name
            self._buttons[name] = button
        self.bind("<Configure>", lambda event: self._redraw(), add="+")
        self.bind("<ButtonPress-1>", self._on_press, add="+")
        self.bind("<B1-Motion>", self._on_motion, add="+")
        self.bind("<ButtonRelease-1>", self._on_release, add="+")
        self.bind("<Double-Button-1>", self._on_double, add="+")
        self._redraw()

    def apply_scale(self, scale=None):
        try:
            self._height = int(round(T.TITLEBAR_H * float(scale or 1.0)))
        except (TypeError, ValueError):
            self._height = T.TITLEBAR_H
        super().configure(height=self._height)
        self._redraw()

    def refresh_buttons(self):
        state = titlebar_buttons(getattr(self.hub, "_maximized", False))
        for name, button in self._buttons.items():
            button.configure(text=state[name])
        self._redraw()

    def _redraw(self):
        width = max(100, self.winfo_width())
        height = max(20, self.winfo_height())
        self.delete("all")
        for row in range(height):
            ratio = row / max(1, height - 1)
            color = _mix(T.UI_GRADIENT_TOP, T.UI_BG, ratio)
            self.create_rectangle(0, row, width, row + 1, fill=color,
                                  outline="", tags="bg")
        self.create_line(0, height - 1, width, height - 1,
                         fill=T.UI_BORDER, tags="bg")
        if self._photo is not None:
            self.create_image(14, height / 2, image=self._photo,
                              anchor="w", tags="fg")
        self.create_text(46, height / 2, text=TITLE,
                         fill=T.UI_TEXT, font=self.hub.f_small,
                         anchor="w", tags="fg")
        x = width - 8
        for name in ("close", "maximize", "minimize"):
            button = self._buttons[name]
            self.create_window(x, height / 2, window=button, anchor="e",
                               tags="fg")
            x -= (button._width + 4)
        self.tag_raise("fg")
        self.tag_lower("bg")

    def _on_press(self, event):
        self._drag = (event.x_root, event.y_root,
                      self.hub.root.winfo_x(), self.hub.root.winfo_y())

    def _on_motion(self, event):
        if not self._drag or getattr(self.hub, "_maximized", False):
            return
        start_x, start_y, win_x, win_y = self._drag
        dx, dy = event.x_root - start_x, event.y_root - start_y
        self.hub.root.geometry(f"+{win_x + dx}+{win_y + dy}")

    def _on_release(self, _event=None):
        self._drag = None

    def _on_double(self, _event=None):
        self.hub.toggle_maximize()


class PageHeader(tk.Canvas):
    """v0.10 页面顶部渐变标题区（图标 + 标题/副标题 + 右侧操作）。"""

    def __init__(self, master, hub, icon_name, title, subtitle,
                 actions=()):
        self.hub = hub
        self._icon_name = icon_name
        self._title = title
        self._subtitle = subtitle
        self._scale = hub._font_scale
        self._height = int(round(104 * self._scale))
        super().__init__(master, height=self._height, bg=T.UI_BG,
                         highlightthickness=0, bd=0)
        self._photo = hub._ui_icon_photo(
            icon_name, int(round(ICON_SIZES["page"] * self._scale)))
        self._buttons = []
        for text, command, kind in actions:
            self._buttons.append(hub._button(self, text, command,
                                             kind=kind))
        self.bind("<Configure>", lambda event: self._redraw(), add="+")
        self._redraw()

    def apply_scale(self, scale):
        self._scale = scale
        self._height = int(round(104 * scale))
        super().configure(height=self._height)
        self._photo = self.hub._ui_icon_photo(
            self._icon_name, int(round(ICON_SIZES["page"] * scale)))
        for button in self._buttons:
            try:
                button.apply_scale(scale)
            except Exception:
                pass
        self._redraw()

    def _redraw(self):
        width = max(100, self.winfo_width())
        height = max(40, self.winfo_height())
        self.delete("all")
        top = _mix(T.UI_GRADIENT_TOP, self.hub.settings.get("accent")
                   or T.UI_ACCENT, 0.10)
        for row in range(height):
            ratio = row / max(1, height - 1)
            color = _mix(top, T.UI_BG, ratio)
            self.create_rectangle(0, row, width, row + 1, fill=color,
                                  outline="")
        icon_w = self._photo.width() if self._photo is not None else 0
        if self._photo is not None:
            self.create_image(26, height / 2, image=self._photo, anchor="w")
        text_x = 26 + (icon_w + 12 if icon_w else 0)
        self.create_text(text_x, height / 2 - 9, text=self._title,
                         fill=T.UI_TEXT, font=self.hub.f_title, anchor="sw")
        self.create_text(text_x, height / 2 + 9, text=self._subtitle,
                         fill=T.UI_TEXT_3, font=self.hub.f_small,
                         anchor="nw")
        x = width - 26
        for button in reversed(self._buttons):
            self.create_window(x, height / 2, window=button, anchor="e")
            x -= (button._width + 8)


class GameHub:
    """v0.8 主界面：左侧导航 + 主页 / 清日常 / 设置三页（真实 Tk 控件）。"""

    def __init__(self, root):
        global _FONT_SCALE
        self.root = root
        self.root.report_callback_exception = self._report_callback_exception
        runtime_log.log_event("ui.initialize", version=VERSION)
        self.apps, self.clash_exe, self.search_root, meta = store.load_state_full()
        self.settings = store._clean_settings(meta.get("settings"))
        runtime_log.log_event("config.loaded", app_count=len(self.apps),
                              app_keys=[app.get("key") for app in self.apps],
                              admin=store.hub_is_elevated())
        # v0.10：没有显式 accent 时使用淡紫新默认；旧用户选择保留
        if not meta.get("settings_explicit_accent"):
            self.settings["accent"] = store.NEW_DEFAULT_ACCENT
        self._font_scale = window_scale_value(
            self.settings.get("font_scale"), 1.0)
        _FONT_SCALE = self._font_scale
        self._maximized = False
        self._restore_geometry = ""
        self.daily_order = list(meta.get("daily_order") or store.DEFAULT_DAILY_ORDER)
        # 设置页的「默认超时/完成后关闭脚本」作用于尚未单独保存过 daily 的卡片
        for app in self.apps:
            if app.get("daily_explicit"):
                continue
            key = app.get("key", "")
            current = app.get("daily") or store._clean_daily(None, key)
            current["timeout_min"] = int(
                self.settings.get("daily_default_timeout") or 120)
            current["close_after"] = bool(
                self.settings.get("daily_close_after", True))
            app["daily"] = current
        self.page = "home"
        self.versions = {}
        self.latest = {}
        self.starting = {}
        self.running = {}
        self.game_states = {}
        self.adb_enabled = bool(self.settings.get("adb_enabled"))
        self.daily_manager = daily.DailyManager(self.apps,
                                                on_event=self._daily_manager_event)
        self.daily_events = queue.Queue()
        self.daily_log = []
        self.daily_selected = None
        self._photos = {}
        self._home_rows = {}
        self._daily_rows = {}
        self._daily_vars = {}
        self._daily_status = {}
        self._daily_start_btn = {}
        self._daily_stop_btn = {}
        self._daily_hint = {}
        self._daily_settings = {}
        self._daily_summary = {}
        self._nav_buttons = {}
        self._accent_buttons = []
        self._page_headers = {}
        self.checking = False
        self.manual_check = False
        self.update_queue = queue.Queue()
        self.software_checking = False
        self.software_check_manual = False
        self.software_queue = queue.Queue()
        self.update_download_queue = queue.Queue()
        self._update_progress_dialog = None
        self._update_progress_var = None
        self._update_progress_bar = None
        self.game_launching = {}
        self.game_launch_queue = queue.Queue()
        self._toast_after = None
        self._poll_after = None
        self._closing = False
        self.config_saved = store.save_state(
            self.apps, self.clash_exe, self.search_root,
            self.daily_order, self.settings)
        self._setup_fonts()
        self._build_ui()
        try:
            detector.set_adb_enabled(self.adb_enabled)
        except Exception:
            pass
        self._update_versions()
        self._apply_accent_theme()
        self._rebuild_home()
        self._rebuild_daily()
        self.show_page("home")
        self._refresh()
        self._schedule_poll()
        if self.settings.get("check_update_on_start", True):
            self._startup_check_after = self.root.after(
                900, self._start_update_check)
            self._startup_software_after = self.root.after(
                1800, lambda: self.check_software_update(manual=False))
        else:
            self._startup_check_after = None
            self._startup_software_after = None
        if not self.config_saved:
            self.root.after(300, self._warn_save_failed)
        self._toast("就绪")

    # ---------------------------------------------------------- 初始化
    def _save_config(self):
        saved = store.save_state(self.apps, self.clash_exe, self.search_root,
                                 self.daily_order, self.settings)
        runtime_log.log_event("config.saved", ok=saved, app_count=len(self.apps))
        if not saved:
            self._toast("配置文件无法写入，本次修改无法保存")
        return saved

    def _warn_save_failed(self):
        messagebox.showwarning(
            "配置文件无法写入",
            "配置文件 config.json 无法写入，之后的修改将无法保存。\n"
            "请检查 Hub 所在目录是否有写入权限，或 config.json 是否被占用、设为只读。",
            parent=self.root)

    def _setup_fonts(self):
        """v0.10：按 font_scale 创建/更新字体；已有 Font 对象原地更新。"""
        scale = getattr(self, "_font_scale", 1.0) or 1.0
        sizes = T.UI_FONT_SIZES

        def ensure(attr, base, weight="normal"):
            font = getattr(self, attr, None)
            size = -max(2, int(round(base * scale)))
            if font is None:
                font = tkfont.Font(family=T.UI_FONT, size=size,
                                   weight=weight)
            else:
                font.configure(family=T.UI_FONT, size=size, weight=weight)
            setattr(self, attr, font)

        ensure("f_title", sizes["title"], "bold")
        ensure("f_page", sizes["page"], "bold")
        ensure("f_name", sizes["name"], "bold")
        ensure("f_body", sizes["body"])
        ensure("f_small", sizes["body"])
        ensure("f_tiny", sizes["aux"])
        self.f_aux = self.f_tiny
        ensure("f_btn", sizes["body"], "bold")

    def _app_by_key(self, key):
        for app in self.apps:
            if app.get("key") == key:
                return app
        return None

    def _key_index(self, key):
        for index, app in enumerate(self.apps):
            if app.get("key") == key:
                return index
        return -1

    def _icon_photo(self, path, size):
        key = (path, size)
        if key in self._photos:
            return self._photos[key]
        try:
            img = render.load_icon(path, 256)
            width, height = img.size
            scale = min(size / width, size / height)
            img = img.resize((max(1, int(width * scale)),
                              max(1, int(height * scale))), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img, master=self.root)
        except Exception:
            photo = None
        self._photos[key] = photo
        return photo

    def _ui_icon_photo(self, name, size):
        """v0.9.1 图标：PIL RGBA + LANCZOS + ImageTk，并缓存引用防 GC。"""
        path = resolve_icon_path(name)
        if not path:
            return None
        key = ("ui", path, int(size))
        if key in self._photos:
            return self._photos[key]
        try:
            img = Image.open(path).convert("RGBA")
            bbox = img.getbbox()
            if bbox:
                img = img.crop(bbox)
            side = max(img.size)
            square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
            square.paste(img, ((side - img.size[0]) // 2,
                               (side - img.size[1]) // 2), img)
            img = square.resize((max(1, int(size)), max(1, int(size))),
                                Image.LANCZOS)
            photo = ImageTk.PhotoImage(img, master=self.root)
        except Exception:
            photo = None
        self._photos[key] = photo
        return photo

    # ---------------------------------------------------------- 控件
    def _button(self, parent, text, command, kind="normal", width=None,
                font=None, state=None, anchor="center", photo=None):
        """v0.9：统一自绘圆角按钮（正常/悬停/按下/禁用/主按钮）。"""
        accent = self.settings.get("accent") or T.UI_ACCENT
        button = RoundButton(parent, text=text, command=command, kind=kind,
                             width=width, font=font or self.f_btn,
                             state=state or "normal", accent=accent,
                             anchor=anchor, photo=photo)
        if kind == "primary":
            self._accent_buttons.append(button)
        return button

    def _entry(self, parent, value="", width=18):
        return RoundEntry(parent, value=value, width=width, font=self.f_body)

    def _label(self, parent, text="", color=T.UI_TEXT_2, font=None, **kwargs):
        return tk.Label(parent, text=text, bg=kwargs.pop("bg", T.UI_BG),
                        fg=color, font=font or self.f_body, **kwargs)

    def _scroll_area(self, parent):
        outer = tk.Frame(parent, bg=T.UI_BG)
        canvas = tk.Canvas(outer, bg=T.UI_BG, highlightthickness=0)
        scroll = tk.Scrollbar(outer, orient="vertical", command=canvas.yview,
                              width=11, bg=T.UI_PANEL_2,
                              troughcolor=T.UI_BG,
                              activebackground=T.UI_PANEL_3, relief="flat",
                              bd=0, highlightthickness=0)
        inner = tk.Frame(canvas, bg=T.UI_BG)
        window = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda event: canvas.configure(
                       scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda event: canvas.itemconfigure(window,
                                                      width=event.width))
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        def _wheel(event):
            try:
                canvas.yview_scroll(int(-event.delta / 120), "units")
            except Exception:
                pass

        inner.bind_all("<MouseWheel>", _wheel, add="+")
        return outer, inner

    # ---------------------------------------------------------- 主布局
    def _build_ui(self):
        self.root.title(TITLE)
        self.root.configure(bg=T.UI_BG)
        self.root.resizable(True, True)
        self.root.minsize(T.MIN_W, T.MIN_H)
        width, height = T.WIN_W, T.WIN_H
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(
            f"{width}x{height}+{max(0, (sw - width) // 2)}"
            f"+{max(0, (sh - height) // 2 - 20)}")
        self._window_icons = []
        for icon_size in (ICON_SIZES["window"], ICON_SIZES["window_small"]):
            photo = self._ui_icon_photo("brand", icon_size)
            if photo is not None:
                self._window_icons.append(photo)
        try:
            if self._window_icons:
                self.root.iconphoto(True, *self._window_icons)
            else:
                fallback = tk.PhotoImage(
                    file=os.path.join(store.ASSETS, "hub.png"))
                self.root.iconphoto(True, fallback)
                self._window_icons.append(fallback)
        except Exception:
            pass
        _dark_titlebar(self.root)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.overrideredirect(True)
        self.root.bind("<Map>", lambda event: window_state.restore_from_taskbar(self.root, event), add="+")
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(1, weight=1)
        self._build_titlebar()
        self._build_sidebar()
        self.content = tk.Frame(self.root, bg=T.UI_BG)
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)
        self.pages = {}
        for name in ("home", "daily", "settings"):
            frame = tk.Frame(self.content, bg=T.UI_BG)
            frame.grid(row=0, column=0, sticky="nsew")
            self.pages[name] = frame
        self._build_home_page()
        self._build_daily_page()
        self._build_settings_page()
        self._apply_accent_theme()
        self.toast_var = tk.StringVar(value="")
        self.toast_label = tk.Label(self.content, textvariable=self.toast_var,
                                    bg=T.UI_SIDEBAR, fg=T.UI_TEXT_2,
                                    anchor="w", font=self.f_small,
                                    padx=18, pady=7)
        self.toast_label.grid(row=1, column=0, sticky="we")
        self._build_resize_grips()
        self._setup_borderless()
        self.root.after_idle(self._setup_borderless)
        self.root.after(300, self._setup_borderless)
        self.tray = None
        self._tray_hidden = False
        try:
            self.tray = tray.TrayManager(
                self.root, on_show=self._show_from_tray,
                on_exit=self._tray_exit,
                icon_path=os.path.join(store.ASSETS, "hub.ico"),
                tooltip=f"All-My-Maa v{VERSION}")
            if self.settings.get("minimize_to_tray", True):
                self.tray.start()
        except Exception:
            self.tray = None

    # ---------------------------------------------------------- 无边框窗口/标题栏
    def _build_titlebar(self):
        self.titlebar = TitleBar(
            self.root, self,
            height=int(round(T.TITLEBAR_H * self._font_scale)))
        self.titlebar.grid(row=0, column=0, columnspan=2, sticky="we")

    def _setup_borderless(self):
        """隐藏原生标题栏后，恢复任务栏/Alt+Tab 行为并启用圆角。"""
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetAncestor(self.root.winfo_id(), 2)
            try:
                self.root.attributes("-toolwindow", 0)
            except Exception:
                pass
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = (style | WS_EX_APPWINDOW) & ~WS_EX_TOOLWINDOW
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                                0x0020 | 0x0004 | 0x0001)  # framed/noz/no size
            try:
                dwm = ctypes.WinDLL("dwmapi")
                pref = ctypes.c_int(2)
                dwm.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref),
                                          ctypes.sizeof(pref))
            except Exception:
                pass
        except Exception:
            pass

    def _build_resize_grips(self):
        self._resize_dir = None
        self._resize_data = None
        specs = (
            ("n", {"relx": 0.5, "rely": 0, "anchor": "n", "relwidth": 1,
                   "height": 6, "cursor": "sb_v_double_arrow"}),
            ("s", {"relx": 0.5, "rely": 1, "anchor": "s", "relwidth": 1,
                   "height": 6, "cursor": "sb_v_double_arrow"}),
            ("w", {"relx": 0, "rely": 0.5, "anchor": "w", "width": 6,
                   "relheight": 1, "cursor": "sb_h_double_arrow"}),
            ("e", {"relx": 1, "rely": 0.5, "anchor": "e", "width": 6,
                   "relheight": 1, "cursor": "sb_h_double_arrow"}),
            ("nw", {"relx": 0, "rely": 0, "anchor": "nw", "width": 10,
                    "height": 10, "cursor": "size_nw_se"}),
            ("ne", {"relx": 1, "rely": 0, "anchor": "ne", "width": 10,
                    "height": 10, "cursor": "size_ne_sw"}),
            ("sw", {"relx": 0, "rely": 1, "anchor": "sw", "width": 10,
                    "height": 10, "cursor": "size_nw_se"}),
            ("se", {"relx": 1, "rely": 1, "anchor": "se", "width": 10,
                    "height": 10, "cursor": "size_ne_sw"}),
        )
        self._grips = []
        for direction, options in specs:
            grip = tk.Frame(self.root, bg=T.UI_BG, cursor=options.pop("cursor"))
            grip.place(**options)
            grip.bind("<ButtonPress-1>",
                      lambda event, d=direction: self._resize_start(d, event))
            grip.bind("<B1-Motion>", self._resize_motion)
            grip.bind("<ButtonRelease-1>", self._resize_end)
            grip.lift()
            self._grips.append(grip)

    def _resize_start(self, direction, event):
        if self._maximized:
            return
        self._resize_dir = direction
        self._resize_data = (self.root.winfo_x(), self.root.winfo_y(),
                             self.root.winfo_width(),
                             self.root.winfo_height(),
                             event.x_root, event.y_root)

    def _resize_motion(self, event):
        if not self._resize_dir or not self._resize_data:
            return
        x, y, width, height, sx, sy = self._resize_data
        dx, dy = event.x_root - sx, event.y_root - sy
        min_w, min_h = T.MIN_W, T.MIN_H
        if "e" in self._resize_dir:
            width = max(min_w, width + dx)
        if "s" in self._resize_dir:
            height = max(min_h, height + dy)
        if "w" in self._resize_dir:
            new_w = max(min_w, width - dx)
            x += width - new_w
            width = new_w
        if "n" in self._resize_dir:
            new_h = max(min_h, height - dy)
            y += height - new_h
            height = new_h
        self.root.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")

    def _resize_end(self, _event=None):
        self._resize_dir = None
        self._resize_data = None

    def _work_area(self):
        try:
            rect = wintypes.RECT()
            ctypes.windll.user32.SystemParametersInfoW(
                0x0030, 0, ctypes.byref(rect), 0)
            return (rect.left, rect.top,
                    rect.right - rect.left, rect.bottom - rect.top)
        except Exception:
            return (0, 0, self.root.winfo_screenwidth(),
                    self.root.winfo_screenheight())

    def minimize_window(self):
        runtime_log.log_event("window.minimize_requested", target="tray" if self._tray_enabled() else "taskbar")
        if self._hide_to_tray():
            return
        self._minimize_to_taskbar()

    def _minimize_to_taskbar(self):
        ok = window_state.minimize_to_taskbar(self.root)
        runtime_log.log_event("window.taskbar_minimize", ok=ok,
                              error=getattr(self.root, "_gamehub_window_state_error", ""))
        if not ok:
            self._toast("最小化失败，窗口保持打开；可重试或查看 Hub 日志")
        return ok

    def _report_callback_exception(self, exc_type, exc_value, exc_tb):
        runtime_log.get_logger("ui").error(
            "tk_callback_exception", exc_info=(exc_type, exc_value, exc_tb))
        try:
            self._toast("界面操作出现异常，已记录到 Hub 日志；请通过问题反馈导出诊断包")
        except Exception:
            pass

    def _tray_enabled(self):
        return bool(self.settings.get("minimize_to_tray", True))

    def _hide_to_tray(self, force=False):
        if not (self.tray and (force or bool(
                self.settings.get("minimize_to_tray", True)))):
            return False
        try:
            if not self.tray.start():
                return False
            self.root.withdraw()
            self._tray_hidden = True
            runtime_log.log_event("window.hidden_to_tray")
            return True
        except Exception:
            return False

    def _show_from_tray(self):
        runtime_log.log_event("window.restore_from_tray")
        self._tray_hidden = False
        try:
            self.root.deiconify()
            window_state.apply_taskbar_style(self.root)
            self.root.lift()
            self.root.focus_force()
        except Exception:
            pass

    def _tray_exit(self):
        self._on_close(force=True)

    def _sync_tray(self):
        if self.tray is None:
            return
        try:
            if self._tray_enabled():
                self.tray.start()
            else:
                if self._tray_hidden:
                    self._show_from_tray()
                self.tray.stop()
                self._tray_hidden = False
        except Exception:
            pass

    def toggle_maximize(self):
        if self._maximized:
            geometry = self._restore_geometry or \
                f"{T.WIN_W}x{T.WIN_H}+80+60"
            self.root.geometry(geometry)
            self._maximized = False
        else:
            self._restore_geometry = self.root.geometry()
            x, y, width, height = self._work_area()
            self.root.geometry(f"{width}x{height}+{x}+{y}")
            self._maximized = True
        try:
            self.titlebar.refresh_buttons()
        except Exception:
            pass

    def _sidebar_section(self, title):
        tk.Label(self.sidebar, text=title, bg=T.UI_SIDEBAR,
                 fg=T.UI_TEXT_3, font=self.f_tiny, anchor="w").pack(
            fill="x", padx=24, pady=(11, 2))

    def _build_sidebar(self):
        sidebar = tk.Frame(self.root, bg=T.UI_SIDEBAR, width=T.SIDEBAR_W)
        sidebar.grid(row=1, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        sidebar.pack_propagate(False)
        self.sidebar = sidebar

        head = tk.Canvas(sidebar, height=86, bg=T.UI_GRADIENT_SIDEBAR_TOP,
                         highlightthickness=0, bd=0)
        head.pack(fill="x")
        logo = self._ui_icon_photo("brand", ICON_SIZES["brand"])
        if logo is not None:
            self._logo_photo = logo

        def paint_head(_event=None):
            width = max(120, head.winfo_width())
            height = 86
            head.delete("all")
            for row in range(height):
                ratio = row / max(1, height - 1)
                head.create_rectangle(
                    0, row, width, row + 1,
                    fill=_mix(T.UI_GRADIENT_SIDEBAR_TOP,
                              T.UI_SIDEBAR, ratio), outline="")
            if logo is not None:
                head.create_image(20, height / 2, image=logo, anchor="w")
            head.create_text(76, height / 2 - 8, text="All-My-Maa",
                             fill=T.UI_TEXT, font=self.f_page, anchor="w")
            head.create_text(76, height / 2 + 12, text="游戏脚本中心",
                             fill=T.UI_TEXT_3, font=self.f_aux, anchor="w")

        head.bind("<Configure>", paint_head, add="+")
        head.after_idle(paint_head)

        self._sidebar_section("导航")
        nav = tk.Frame(sidebar, bg=T.UI_SIDEBAR)
        nav.pack(fill="x", padx=12)
        items = (("home", "主页"), ("daily", "清日常"), ("settings", "设置"))
        for name, label in items:
            icon = self._ui_icon_photo(name, ICON_SIZES["nav"])
            button = RoundButton(nav, text=label,
                                 command=lambda page=name: self.show_page(page),
                                 kind="ghost", height=37, anchor="w",
                                 font=self.f_small, bg=T.UI_SIDEBAR,
                                 photo=icon)
            button.pack(fill="x", pady=1)
            button._selected = (name == "home")
            self._nav_buttons[name] = button

        self._sidebar_section("小工具")
        tools = tk.Frame(sidebar, bg=T.UI_SIDEBAR)
        tools.pack(fill="x", padx=12)
        tool_items = (
            ("打开 Clash Verge", self.open_clash),
            ("打开脚本目录", self.open_script_dir),
            ("打开日志目录", self.open_log_dir),
            ("检查脚本更新", self._on_refresh),
        )
        for label, command in tool_items:
            button = RoundButton(tools, text=label, command=command,
                                 kind="ghost", height=33, anchor="w",
                                 font=self.f_small, bg=T.UI_SIDEBAR)
            button.pack(fill="x", pady=1)
        self.clash_button = tools.winfo_children()[0]

        spacer = tk.Frame(sidebar, bg=T.UI_SIDEBAR)
        spacer.pack(fill="both", expand=True)

        bottom = tk.Frame(sidebar, bg=T.UI_SIDEBAR)
        bottom.pack(side="bottom", fill="x", padx=16, pady=(0, 12))
        tk.Label(bottom, text="关于与更新", bg=T.UI_SIDEBAR,
                 fg=T.UI_TEXT_3, font=self.f_tiny, anchor="w").pack(
            fill="x", padx=8, pady=(0, 3))
        about_buttons = tk.Frame(bottom, bg=T.UI_SIDEBAR)
        about_buttons.pack(fill="x")
        about_icon = self._ui_icon_photo("about", 20)
        self._button(about_buttons, "关于软件", self.open_about,
                     kind="ghost", anchor="w",
                     photo=about_icon).pack(fill="x", pady=1)
        self._button(about_buttons, "问题反馈 / Bug", self.open_feedback,
                     kind="ghost", anchor="w").pack(fill="x", pady=1)
        self._button(about_buttons, "检查软件更新", self.check_software_update,
                     kind="ghost", anchor="w").pack(fill="x", pady=1)

        status = RoundPanel(bottom, fill=T.UI_PANEL,
                            border=T.UI_BORDER_SOFT, pad=T.SPACE_UI_XS)
        status.pack(fill="x", pady=(4, 6))
        self.sidebar_hub_var = tk.StringVar(value="就绪")
        self.sidebar_count_var = tk.StringVar(value="")
        self._label(status.inner, "Hub 状态", color=T.UI_TEXT_3,
                    font=self.f_aux, bg=T.UI_PANEL).pack(anchor="w")
        tk.Label(status.inner, textvariable=self.sidebar_hub_var,
                 bg=T.UI_PANEL, fg=T.UI_SUCCESS, font=self.f_small,
                 anchor="w").pack(anchor="w", pady=(1, 1))
        tk.Label(status.inner, textvariable=self.sidebar_count_var,
                 bg=T.UI_PANEL, fg=T.UI_TEXT_3, font=self.f_aux,
                 anchor="w").pack(anchor="w")
        self._label(bottom, f"All-My-Maa v{VERSION} · 单实例",
                    color=T.UI_TEXT_3, font=self.f_aux,
                    bg=T.UI_SIDEBAR).pack(anchor="w")

    def _apply_accent_theme(self):
        """把 settings.accent 应用到导航高亮与主按钮（强调色）。"""
        accent = self.settings.get("accent") or T.UI_ACCENT
        for button in self._accent_buttons:
            try:
                button.set_accent(accent)
            except Exception:
                pass
        for page_name, button in self._nav_buttons.items():
            try:
                button.set_accent(accent)
                button.set_selected(page_name == self.page)
            except Exception:
                pass

    def show_page(self, name):
        if name not in self.pages:
            return
        self.page = name
        for page_name, frame in self.pages.items():
            if page_name == name:
                frame.tkraise()
            else:
                frame.lower()
        for page_name, button in self._nav_buttons.items():
            try:
                button.set_selected(page_name == name)
            except Exception:
                pass
        if name == "home":
            self._refresh_home_states()
        elif name == "daily":
            self._refresh_daily_states()
        elif name == "settings":
            self._refresh_settings_view()

    # ---------------------------------------------------------- 页面标题
    def _page_title_box(self, parent, icon_name, title, subtitle):
        box = tk.Frame(parent, bg=T.UI_BG)
        photo = self._ui_icon_photo(icon_name, ICON_SIZES["page"])
        if photo is not None:
            tk.Label(box, image=photo, bg=T.UI_BG).pack(side="left",
                                                       padx=(0, 10))
        text = tk.Frame(box, bg=T.UI_BG)
        text.pack(side="left")
        self._label(text, title, color=T.UI_TEXT, font=self.f_title,
                    bg=T.UI_BG).pack(anchor="w")
        self._label(text, subtitle, color=T.UI_TEXT_3, font=self.f_small,
                    bg=T.UI_BG).pack(anchor="w", pady=(3, 0))
        return box

    # ---------------------------------------------------------- 主页
    def _build_home_page(self):
        page = self.pages["home"]
        page.columnconfigure(0, weight=1)
        page.rowconfigure(1, weight=1)
        header = PageHeader(
            page, self, "home", "主页",
            "选择游戏行或「打开脚本」：未运行则启动，运行中则唤到前台",
            actions=(("添加游戏", self.add_app, "primary"),
                     ("检查更新", self._on_refresh, "normal"),
                     ("重新识别路径", self.rescan_paths, "normal")))
        header.grid(row=0, column=0, sticky="we",
                    padx=T.SPACE_UI_XL, pady=(T.SPACE_UI_SM, 2))
        self._page_headers["home"] = header
        area, self.home_inner = self._scroll_area(page)
        area.grid(row=1, column=0, sticky="nsew", padx=T.SPACE_UI_XL,
                  pady=(0, T.SPACE_UI_MD))

    def _rebuild_home(self):
        if not hasattr(self, "home_inner"):
            return
        for child in self.home_inner.winfo_children():
            child.destroy()
        self._home_rows = {}
        for index, app in enumerate(self.apps):
            self._build_home_row(index, app)
        if not self.apps:
            self._label(self.home_inner, "还没有游戏，点右上角「添加游戏」开始。",
                        color=T.UI_TEXT_3).pack(padx=10, pady=24)
        self._refresh_home_states()

    def _build_home_row(self, index, app):
        key = app["key"]
        card = RoundPanel(self.home_inner, fill=T.UI_PANEL,
                          border=T.UI_BORDER, pad=T.SPACE_UI_LG)
        card.pack(fill="x", pady=(3, 9))
        row = card.inner
        row.columnconfigure(2, weight=1)
        icon = self._icon_photo(app.get("icon_path"), 64)
        icon_label = tk.Label(row, image=icon, bg=T.UI_PANEL)
        if icon is not None:
            icon_label.image = icon
        icon_label.grid(row=0, column=0, rowspan=2, padx=(0, T.SPACE_UI_MD),
                        pady=2)

        name = tk.Label(row, text=app.get("game", ""), bg=T.UI_PANEL,
                        fg=T.UI_TEXT, font=self.f_page, anchor="w")
        name.grid(row=0, column=1, sticky="sw", columnspan=2)
        version = tk.Label(row, text="", bg=T.UI_PANEL, fg=T.UI_TEXT_3,
                           font=self.f_small, anchor="w")
        version.grid(row=1, column=1, sticky="nw", pady=(3, 0))

        status_box = tk.Frame(row, bg=T.UI_PANEL)
        status_box.grid(row=2, column=0, columnspan=2, sticky="w",
                        pady=(T.SPACE_UI_XS, 0))
        script_status = tk.StringVar(value="脚本 未启动")
        game_status = tk.StringVar(value="游戏 未运行")
        script_status_label = tk.Label(status_box, textvariable=script_status,
                                       bg=T.UI_PANEL, fg=T.UI_TEXT_2,
                                       font=self.f_small)
        script_status_label.pack(side="left", padx=(0, T.SPACE_UI_MD))
        game_status_label = tk.Label(status_box, textvariable=game_status,
                                     bg=T.UI_PANEL, fg=T.UI_TEXT_3,
                                     font=self.f_small)
        game_status_label.pack(side="left")

        buttons = tk.Frame(row, bg=T.UI_PANEL)
        buttons.grid(row=0, column=3, rowspan=3, sticky="e",
                     padx=(T.SPACE_UI_MD, 0))
        main_btn = self._button(buttons, "打开脚本",
                                lambda k=key: self.open_script(k),
                                kind="primary", width=11)
        main_btn.pack(side="left", padx=(0, T.SPACE_UI_XS))
        game_btn = self._button(buttons, "启动游戏",
                                lambda k=key: self.launch_game(k),
                                width=9)
        game_btn.pack(side="left", padx=(0, T.SPACE_UI_XS))
        daily_btn = self._button(buttons, "清日常",
                                 lambda k=key: self.run_daily_single(k),
                                 width=8)
        daily_btn.pack(side="left", padx=(0, T.SPACE_UI_XS))
        more_btn = self._button(buttons, "更多 ▾", lambda: None, width=7)
        more_btn.configure(command=lambda k=key, w=more_btn: self._show_more(k, w))
        more_btn.pack(side="left")

        for widget in (card, row, icon_label, name, version):
            widget.bind("<Button-1>",
                        lambda event, k=key: self.open_script(k))

        self._home_rows[key] = {
            "row": row, "card": card, "name": name, "version": version,
            "script_status": script_status, "game_status": game_status,
            "script_status_label": script_status_label,
            "game_status_label": game_status_label,
            "main_btn": main_btn, "game_btn": game_btn,
            "daily_btn": daily_btn,
        }

    def _refresh_home_states(self):
        accent = self.settings.get("accent") or T.UI_ACCENT
        by_key = {app["key"]: app for app in self.apps}
        daily_snapshot = self.daily_manager.snapshot()
        daily_busy = daily_snapshot.get("busy")
        daily_active = daily_snapshot.get("active")
        for key, row in self._home_rows.items():
            app = by_key.get(key)
            if app is None:
                continue
            version = self.versions.get(key) or ""
            text = app.get("script", "")
            if version:
                text += " · " + version
            if self._has_update(app):
                text += "  →  " + str(self.latest.get(key))
                row["version"].configure(fg=accent)
            else:
                row["version"].configure(fg=T.UI_TEXT_3)
            row["version"].configure(text=text)

            script_state = self._app_state(app)
            script_labels = {"on": ("● 脚本运行中", T.UI_SUCCESS),
                             "starting": ("● 脚本启动中…", T.UI_WARNING),
                             "missing": ("● 脚本路径缺失", T.UI_DANGER),
                             "off": ("○ 脚本未启动", T.UI_TEXT_2)}
            label, color = script_labels.get(script_state,
                                            script_labels["off"])
            row["script_status"].set(label)
            row["script_status_label"].configure(fg=color)
            game_state = self._game_state(app)
            if not game_state.get("configured"):
                game_text, game_color = "○ 游戏未配置", T.UI_TEXT_3
            elif game_state.get("running"):
                game_text = "● 游戏" + (game_state.get("label") or "运行中")
                game_color = T.UI_SUCCESS
            elif game_state.get("reason") == "launcher":
                game_text, game_color = "● 游戏启动器已开", T.UI_WARNING
            elif game_state.get("reason") == "cloud":
                game_text, game_color = "● 游戏云游戏运行中", T.UI_SUCCESS
            else:
                game_text, game_color = "○ 游戏未运行", T.UI_TEXT_3
            row["game_status"].set(game_text)
            row["game_status_label"].configure(fg=game_color)

            running = bool(self.running.get(key, {}).get("script"))
            row["main_btn"].configure(
                text="唤到前台" if running else "打开脚本",
                state="normal")
            if daily_active == key:
                row["daily_btn"].configure(text="清日常中", state="disabled")
            elif daily_busy:
                row["daily_btn"].configure(text="清日常", state="disabled")
            else:
                row["daily_btn"].configure(text="清日常", state="normal")
        self._refresh_sidebar()

    def _refresh_sidebar(self):
        running = sum(1 for app in self.apps
                      if self.running.get(app["key"], {}).get("script"))
        self.sidebar_hub_var.set("运行中" if running else "就绪")
        self.sidebar_count_var.set(f"{running} 个脚本运行中 · 共 {len(self.apps)} 个卡片")

    def _show_more(self, key, widget):
        app = self._app_by_key(key)
        if app is None:
            return
        menu = tk.Menu(self.root, tearoff=0, bg=T.UI_PANEL_2,
                       fg=T.UI_TEXT, activebackground=T.UI_PANEL_3,
                       activeforeground=T.UI_TEXT, bd=0, font=self.f_small)
        menu.add_command(label="编辑卡片",
                         command=lambda: self.edit_app(self._key_index(key)))
        menu.add_command(label="检查更新",
                         command=lambda: self.update_app(key))
        menu.add_separator()
        menu.add_command(label="脚本官网",
                         command=lambda: self._open_url(app.get("site"),
                                                        "脚本官网"))
        menu.add_command(label="GitHub",
                         command=lambda: self._open_url(app.get("github"),
                                                        "GitHub"))
        menu.add_command(label="游戏下载页",
                         command=lambda: self.download_game(key))
        menu.add_separator()
        menu.add_command(label="打开脚本文件夹",
                         command=lambda: self.open_folder(key))
        menu.add_command(label="更新启动器",
                         command=lambda: self._launch_updater(app))
        if not app.get("builtin"):
            menu.add_separator()
            menu.add_command(label="删除此卡片",
                             command=lambda: self.delete_app(
                                 self._key_index(key)))
        try:
            x = widget.winfo_rootx()
            y = widget.winfo_rooty() + widget.winfo_height()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    # ---------------------------------------------------------- 清日常页
    def _build_daily_page(self):
        page = self.pages["daily"]
        page.columnconfigure(0, weight=1)
        page.rowconfigure(3, weight=1)
        header = PageHeader(
            page, self, "daily", "清日常",
            "使用脚本自身已配置的任务；勾选决定队列，顺序可调；同一时刻只运行一项")
        header.grid(row=0, column=0, sticky="we",
                    padx=T.SPACE_UI_XL, pady=(T.SPACE_UI_SM, 2))
        self._page_headers["daily"] = header
        toolbar = tk.Frame(page, bg=T.UI_BG)
        toolbar.grid(row=1, column=0, sticky="we", padx=T.SPACE_UI_XL,
                     pady=(4, 8))
        buttons = (
            ("全选", lambda: self._daily_check_all(True), "normal", 6),
            ("取消全选", lambda: self._daily_check_all(False), "normal", 8),
            ("↑ 上移", lambda: self._daily_move(-1), "normal", 7),
            ("↓ 下移", lambda: self._daily_move(1), "normal", 7),
            ("开始选中项", self._daily_start_checked, "primary", 11),
            ("停止", self._daily_stop_all, "danger", 6),
            ("查看命令(dry-run)", self._daily_preview, "normal", 16),
        )
        for index, (text, command, kind, width) in enumerate(buttons):
            button = self._button(toolbar, text, command, kind=kind,
                                  width=width)
            button.pack(side="left", padx=(0, T.SPACE_UI_XS if index < 4
                                          else T.SPACE_UI_SM))
        self._label(page, "⚠ 自动化可能违反游戏条款、存在账号风险；执行期间脚本会抢占鼠标键盘，请确认后使用。",
                    color=T.UI_WARNING, font=self.f_aux,
                    bg=T.UI_BG).grid(row=2, column=0, sticky="w",
                                     padx=T.SPACE_UI_XL)
        self._daily_area, self.daily_inner = self._scroll_area(page)
        self._daily_area.grid(row=3, column=0, sticky="nsew",
                              padx=T.SPACE_UI_XL,
                              pady=(4, T.SPACE_UI_XS))
        log_panel = RoundPanel(page, fill=T.UI_PANEL,
                               border=T.UI_BORDER_SOFT, pad=T.SPACE_UI_SM)
        log_panel.grid(row=4, column=0, sticky="we", padx=T.SPACE_UI_XL,
                       pady=(0, T.SPACE_UI_MD))
        self.daily_log_text = tk.Text(
            log_panel.inner, height=6, bg=T.UI_PANEL, fg=T.UI_TEXT_2,
            insertbackground=T.UI_TEXT, relief="flat", bd=0,
            highlightthickness=0, font=self.f_aux, wrap="word")
        self.daily_log_text.pack(side="left", fill="both", expand=True)
        self.daily_log_text.configure(state="disabled")

    def _daily_settings_for(self, app):
        key = app.get("key", "")
        settings = store._clean_daily(app.get("daily"), key)
        if not app.get("daily_explicit"):
            settings["timeout_min"] = int(
                self.settings.get("daily_default_timeout")
                or settings.get("timeout_min") or 120)
            settings["close_after"] = bool(
                self.settings.get("daily_close_after"))
        # MXU 实例为空时展示自动推断的实例名，方便用户确认/保存
        if key in ("nte", "maaend") and not settings.get("instance"):
            try:
                settings = daily.effective_settings(app)
            except Exception:
                pass
        return settings

    def _rebuild_daily(self):
        if not hasattr(self, "daily_inner"):
            return
        for child in self.daily_inner.winfo_children():
            child.destroy()
        self._daily_rows = {}
        self._daily_vars = {}
        self._daily_status = {}
        self._daily_start_btn = {}
        self._daily_stop_btn = {}
        self._daily_hint = {}
        self._daily_settings = {}
        by_key = {app["key"]: app for app in self.apps}
        order = [key for key in self.daily_order if key in by_key]
        for index, key in enumerate(order):
            self._build_daily_row(index, by_key[key])
        if not self.daily_selected and order:
            self._daily_select(order[0])
        self._render_daily_log()
        self._refresh_daily_states()

    def _build_daily_row(self, index, app):
        key = app["key"]
        settings = self._daily_settings_for(app)
        card = RoundPanel(self.daily_inner, fill=T.UI_PANEL,
                          border=T.UI_BORDER, pad=T.SPACE_UI_MD)
        card.pack(fill="x", pady=(3, 8))
        row = card.inner
        line1 = tk.Frame(row, bg=T.UI_PANEL)
        line1.pack(fill="x")
        line1.columnconfigure(2, weight=1)
        var = tk.BooleanVar(value=bool(settings.get("enabled", True)))
        check = tk.Checkbutton(
            line1, variable=var, bg=T.UI_PANEL, activebackground=T.UI_PANEL,
            selectcolor=T.UI_ACCENT_SOFT, fg=T.UI_TEXT, bd=0,
            highlightthickness=0,
            command=lambda k=key: self._daily_on_check(k))
        check.grid(row=0, column=0, padx=(0, T.SPACE_UI_XS))
        self._daily_vars[key] = var
        icon = self._icon_photo(app.get("icon_path"), 34)
        icon_label = tk.Label(line1, image=icon, bg=T.UI_PANEL)
        if icon is not None:
            icon_label.image = icon
        icon_label.grid(row=0, column=1, padx=(0, 10))
        display_name = app.get("game", "")
        if app.get("key") in ("nte", "oknte"):
            display_name = f"{display_name} · {app.get('script', '')}"
        name = tk.Label(line1, text=display_name, bg=T.UI_PANEL,
                        fg=T.UI_TEXT, font=self.f_name, anchor="w")
        name.grid(row=0, column=2, sticky="w")
        status = tk.StringVar(value="空闲")
        tk.Label(line1, textvariable=status, bg=T.UI_PANEL, fg=T.UI_TEXT_2,
                 font=self.f_small, width=18,
                 anchor="e").grid(row=0, column=3, padx=(T.SPACE_UI_SM, 10))
        self._daily_status[key] = status
        start_btn = self._button(line1, "开始清日常",
                                 lambda k=key: self._daily_start_row(k),
                                 kind="primary", width=10)
        start_btn.grid(row=0, column=4, padx=(0, T.SPACE_UI_XS))
        stop_btn = self._button(line1, "停止",
                                lambda k=key: self._daily_stop_row(k),
                                kind="danger", width=6, state="disabled")
        stop_btn.grid(row=0, column=5)
        self._daily_start_btn[key] = start_btn
        self._daily_stop_btn[key] = stop_btn

        line2 = tk.Frame(row, bg=T.UI_PANEL)
        line2.pack(fill="x", pady=(T.SPACE_UI_SM, 0))
        fields = [("instance", "实例", 6), ("task", "任务", 6),
                  ("config", "MAA 配置", 6), ("timeout_min", "超时", 4),
                  ("extra_args", "额外参数", 6)]
        entries = {}
        for column, (field, label, width) in enumerate(fields):
            name_label = tk.Label(line2, text=label, bg=T.UI_PANEL,
                                  fg=T.UI_TEXT_3, font=self.f_aux)
            name_label.grid(row=0, column=column * 2, padx=(0, 4),
                            sticky="e")
            entry = self._entry(line2, self._daily_field_value(settings, field),
                                width=width)
            entry.grid(row=0, column=column * 2 + 1, padx=(0, 8),
                       sticky="ew")
            line2.columnconfigure(column * 2 + 1, weight=1)
            entries[field] = entry
        save_btn = self._button(line2, "保存设置",
                                lambda k=key: self._daily_save_row(k),
                                width=6)
        save_btn.grid(row=0, column=len(fields) * 2, padx=(4, 0))
        hint = self._label(line2, "", color=T.UI_WARNING, font=self.f_aux,
                           bg=T.UI_PANEL, anchor="w", justify="left")
        hint.grid(row=1, column=0, columnspan=len(fields) * 2 + 1,
                  sticky="w", pady=(4, 0))
        self._daily_hint[key] = hint
        self._daily_settings[key] = entries

        for widget in (card, row, name, icon_label, check):
            widget.bind("<Button-1>", lambda event, k=key: self._daily_select(k))
        self._daily_rows[key] = card

    @staticmethod
    def _daily_field_value(settings, field):
        if field == "extra_args":
            return " ".join(str(item) for item in
                            (settings.get("extra_args") or []))
        return settings.get(field) or ""

    def _daily_select(self, key):
        self.daily_selected = key
        accent = self.settings.get("accent") or T.UI_ACCENT
        for row_key, card in self._daily_rows.items():
            try:
                card.set_border(accent if row_key == key else T.UI_BORDER)
            except Exception:
                pass

    def _daily_on_check(self, key):
        app = self._app_by_key(key)
        var = self._daily_vars.get(key)
        if app is None or var is None:
            return
        settings = store._clean_daily(app.get("daily"), key)
        settings["enabled"] = bool(var.get())
        app["daily"] = settings
        app["daily_explicit"] = True
        self._save_config()
        self._refresh_daily_states()

    def _daily_check_all(self, enabled):
        for key, var in self._daily_vars.items():
            var.set(bool(enabled))
            app = self._app_by_key(key)
            if app is None:
                continue
            settings = store._clean_daily(app.get("daily"), key)
            settings["enabled"] = bool(enabled)
            app["daily"] = settings
            app["daily_explicit"] = True
        self._save_config()
        self._refresh_daily_states()

    def _daily_move(self, delta):
        key = self.daily_selected
        if not key:
            self._toast("请先点选一行，再调整顺序")
            return
        if self.move_daily(key, delta):
            self._rebuild_daily()
            self._daily_select(key)
            self._toast("已调整清日常顺序")

    def _daily_save_row(self, key):
        app = self._app_by_key(key)
        entries = self._daily_settings.get(key) or {}
        if app is None:
            return
        try:
            timeout = max(1, min(600, int(
                entries["timeout_min"].get().strip() or "120")))
        except ValueError:
            self._toast("超时必须是 1–600 的整数分钟")
            return
        import shlex
        raw_extra = entries["extra_args"].get().strip()
        try:
            extra = shlex.split(raw_extra, posix=True) if raw_extra else []
        except Exception:
            extra = raw_extra.split()
        settings = store._clean_daily(app.get("daily"), key)
        settings.update({
            "instance": entries["instance"].get().strip(),
            "task": entries["task"].get().strip(),
            "config": entries["config"].get().strip(),
            "timeout_min": timeout,
            "extra_args": extra,
            "enabled": bool(self._daily_vars[key].get()),
        })
        app["daily"] = settings
        app["daily_explicit"] = True
        if self._save_config():
            self._toast(f"已保存「{app.get('game')}」的清日常设置")
        self._refresh_daily_states()

    def _daily_start_row(self, key):
        app = self._app_by_key(key)
        if app is None:
            return
        ok, reason = self.daily_manager.start_single(key)
        if not ok:
            self._toast(reason or "无法开始清日常")
            return
        self._append_daily_log(f"▶ 开始：{app.get('game')}")
        self._refresh_daily_states()
        self._refresh_home_states()

    def _daily_stop_row(self, key):
        app = self._app_by_key(key)
        if app is None:
            return
        if self.daily_manager.state_of(key).get("state") not in (
                daily.STARTING, daily.RUNNING):
            return
        if not messagebox.askyesno(
                "停止清日常",
                f"停止「{app.get('game')}」的清日常吗？\n"
                "会结束由 Hub 启动的脚本进程（不会动你自己打开的程序）。",
                parent=self.root):
            return
        self.daily_manager.stop_single(key)
        self._append_daily_log("用户请求停止…")
        self._refresh_daily_states()

    def _daily_start_checked(self):
        keys = daily.enabled_daily_keys(self.apps, self.daily_order)
        if not keys:
            self._toast("请先勾选要执行清日常的游戏")
            return
        plans = [daily.plan_for(self._app_by_key(key)) for key in keys]
        errors = [error for plan in plans for error in plan.get("errors") or []]
        if errors or self.settings.get("daily_show_preview", True):
            if not self._confirm_preview("清日常命令预览（dry-run）", plans):
                return
        elif not messagebox.askyesno(
                "开始一键清日常",
                "将按勾选顺序自动执行清日常。\n"
                "⚠ 自动化存在账号风险；执行期间脚本可能抢占鼠标键盘。\n\n"
                "确定开始吗？", parent=self.root):
            return
        ok, reason = self.daily_manager.start_queue(keys)
        if not ok:
            self._toast(reason)
            return
        self._append_daily_log("准备执行：" + "、".join(
            str(self._app_by_key(key).get("game")) for key in keys))
        self._refresh_daily_states()
        self._refresh_home_states()

    def _daily_stop_all(self):
        if not self.daily_manager.busy:
            self._toast("当前没有正在运行的清日常")
            return
        if not messagebox.askyesno(
                "停止清日常",
                "确定停止当前清日常/队列吗？\n"
                "会结束由 Hub 启动的脚本进程（不会动你自己打开的程序）。",
                parent=self.root):
            return
        self.daily_manager.stop_all()
        self._append_daily_log("用户请求停止…")
        self._refresh_daily_states()

    def _confirm_preview(self, title, plans, confirm=True):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.configure(bg=T.UI_BG)
        dialog.transient(self.root)
        dialog.geometry("760x460")
        result = {"ok": False}
        text = tk.Text(dialog, bg=T.UI_PANEL, fg=T.UI_TEXT_2, relief="flat",
                       wrap="word", font=self.f_small)
        text.pack(fill="both", expand=True, padx=14, pady=(14, 8))
        text.insert("1.0", "\n\n".join(daily.describe_plan(plan)
                                       for plan in plans))
        text.configure(state="disabled")
        footer = tk.Frame(dialog, bg=T.UI_BG)
        footer.pack(fill="x", padx=14, pady=(0, 12))

        def start():
            result["ok"] = True
            dialog.destroy()

        if confirm:
            self._button(footer, "开始执行", start,
                         kind="primary").pack(side="right")
        self._button(footer, "取消" if confirm else "关闭",
                     dialog.destroy).pack(side="right",
                                          padx=(0, 8) if confirm else (0, 0))
        dialog.grab_set()
        self.root.wait_window(dialog)
        return result["ok"]

    def _daily_preview(self):
        keys = daily.enabled_daily_keys(self.apps, self.daily_order)
        if not keys:
            keys = [key for key in self.daily_order if self._app_by_key(key)]
        plans = [daily.plan_for(self._app_by_key(key)) for key in keys]
        if not plans:
            self._toast("没有可预览的清日常项")
            return
        self._confirm_preview("清日常命令预览（dry-run，不启动）", plans,
                              confirm=False)

    def _daily_manager_event(self, event):
        self.daily_events.put(event)
        if event.get("type") not in ("log", "queue"):
            result = event.get("result") or {}
            state = event.get("state")
            if isinstance(state, dict):
                state = state.get("state")
            if not isinstance(state, str):
                state = result.get("state") if isinstance(result.get("state"), str) else None
            runtime_log.log_event("daily.ui_event", event_type=event.get("type"),
                                  key=event.get("key") or result.get("key"),
                                  state=state, pid=result.get("pid"),
                                  duration=result.get("duration"))

    def _append_daily_log(self, line):
        self.daily_log.append(time.strftime("%H:%M:%S ") + line)
        self.daily_log = self.daily_log[-300:]
        self._render_daily_log()

    def _render_daily_log(self):
        if not hasattr(self, "daily_log_text"):
            return
        text = "\n".join(self.daily_log[-200:]) or "（尚未开始）"
        self.daily_log_text.configure(state="normal")
        self.daily_log_text.delete("1.0", "end")
        self.daily_log_text.insert("1.0", text)
        self.daily_log_text.see("end")
        self.daily_log_text.configure(state="disabled")

    def _drain_daily_events(self):
        changed = False
        while True:
            try:
                event = self.daily_events.get_nowait()
            except queue.Empty:
                break
            kind = event.get("type")
            if kind == "item_start":
                self._append_daily_log(f"▶ 开始：{event.get('game')}")
                changed = True
            elif kind == "item":
                result = event.get("result") or {}
                self._append_daily_log(
                    f"■ {result.get('game') or event.get('key')}："
                    f"{result.get('state_label') or result.get('state')}"
                    + (f"（{result.get('reason')}）"
                       if result.get("reason") else ""))
                changed = True
            elif kind == "done":
                result = event.get("result") or {}
                self._append_daily_log(
                    f"■ {result.get('game') or event.get('key')}："
                    f"{result.get('state_label') or result.get('state')}")
                summary = self._daily_summary_text()
                self._append_daily_log("── " + summary)
                self._toast(summary)
                changed = True
            elif kind == "queue":
                if event.get("state") in (daily.FINISHED, daily.STOPPED,
                                          daily.FAILED):
                    summary = self._daily_summary_text()
                    self._append_daily_log("── " + summary)
                    self._toast(summary)
                    changed = True
            elif kind == "manual":
                text = str(event.get("text") or "需要手动操作")
                self._append_daily_log("⚠ " + text)
                self._toast(text)
                changed = True
            elif kind == "log":
                text = str(event.get("text") or "")
                if text:
                    self._append_daily_log(text)
                    changed = True
        if changed:
            self._refresh_daily_states()
            self._refresh_home_states()
            self._render_daily_log()

    def _daily_summary_text(self):
        snapshot = self.daily_manager.snapshot()
        results = snapshot.get("queue", {}).get("results") or []
        if not results:
            return "清日常结束"
        finished = [item for item in results
                    if item.get("state") == daily.FINISHED]
        failed = [item for item in results
                  if item.get("state") in (daily.FAILED, daily.TIMEOUT)]
        skipped = [item for item in results
                   if item.get("state") in (daily.STOPPED, daily.SKIPPED)]
        parts = [f"完成 {len(finished)}/{len(results)}"]
        if failed:
            parts.append("失败：" + "、".join(str(item.get("game"))
                                            for item in failed))
        if skipped:
            parts.append("停止/跳过：" + "、".join(str(item.get("game"))
                                              for item in skipped))
        return "清日常结束（" + "，".join(parts) + "）"

    def _refresh_daily_states(self):
        if not self._daily_rows:
            return
        snapshot = self.daily_manager.snapshot()
        apps = snapshot.get("apps") or {}
        busy = snapshot.get("busy")
        active = snapshot.get("active")
        for key, status in self._daily_status.items():
            state = apps.get(key) or {}
            label = state.get("state_label") or "空闲"
            status.set(label)
            start_btn = self._daily_start_btn.get(key)
            stop_btn = self._daily_stop_btn.get(key)
            hint = self._daily_hint.get(key)
            reason = self.daily_manager.busy_reason(key)
            if start_btn is not None:
                can_start = not busy or active == key
                start_btn.configure(state="normal" if can_start else "disabled")
                start_btn.configure(text="开始清日常"
                                    if not (active == key) else "执行中…")
            if stop_btn is not None:
                stop_btn.configure(state="normal" if active == key
                                   else "disabled")
            if hint is not None:
                if reason:
                    hint.configure(text=reason, fg="#ffce6b")
                elif key == "nte":
                    hint.configure(text=daily.MXU_UI_NOTE, fg=T.UI_TEXT_3)
                elif key == "oknte":
                    hint.configure(
                        text="ok-nte：DailyRoutineTask；建议与 MaaNTE 二选一勾选，避免重复执行异环日常",
                        fg=T.UI_TEXT_3)
                else:
                    hint.configure(text="", fg=T.UI_TEXT_3)

    # ---------------------------------------------------------- 设置页
    def _build_settings_page(self):
        page = self.pages["settings"]
        page.columnconfigure(0, weight=1)
        page.rowconfigure(1, weight=1)
        header = PageHeader(
            page, self, "settings", "设置",
            "配置会立即持久化到 config.json（保存失败会提示）",
            actions=(("保存设置", self._apply_settings, "primary"),))
        header.grid(row=0, column=0, sticky="we",
                    padx=T.SPACE_UI_XL, pady=(T.SPACE_UI_SM, 2))
        self._page_headers["settings"] = header
        area, body = self._scroll_area(page)
        area.grid(row=1, column=0, sticky="nsew", padx=T.SPACE_UI_XL,
                  pady=(0, T.SPACE_UI_MD))
        self.settings_body = body
        columns = tk.Frame(body, bg=T.UI_BG)
        columns.pack(fill="both", expand=True)
        left_col = tk.Frame(columns, bg=T.UI_BG)
        left_col.pack(side="left", fill="both", expand=True,
                      padx=(0, T.SPACE_UI_SM))
        right_col = tk.Frame(columns, bg=T.UI_BG)
        right_col.pack(side="left", fill="both", expand=True,
                       padx=(T.SPACE_UI_SM, 0))

        def section(title, parent):
            panel = RoundPanel(parent, fill=T.UI_PANEL,
                               border=T.UI_BORDER, pad=T.SPACE_UI_MD)
            panel.pack(fill="x", pady=(3, 9))
            self._label(panel.inner, title, color=T.UI_TEXT,
                        font=self.f_name, bg=T.UI_PANEL).pack(
                anchor="w", pady=(0, T.SPACE_UI_XS))
            return panel.inner

        # 外观
        appearance = section("外观", left_col)
        self._label(appearance, "强调色", color=T.UI_TEXT_2,
                    font=self.f_small, bg=T.UI_PANEL).pack(side="left",
                                                          padx=(0, 10))
        self._accent_var = self.settings.get("accent") or T.UI_ACCENT
        self._accent_chips = {}
        for color in store.ACCENT_PRESETS:
            chip = tk.Button(appearance, bg=color, width=2, relief="flat",
                             bd=0, cursor="hand2",
                             command=lambda c=color: self._pick_accent(c))
            chip.pack(side="left", padx=3, pady=2)
            self._accent_chips[color] = chip
        self._refresh_accent_chips()
        font_row = tk.Frame(appearance, bg=T.UI_PANEL)
        font_row.pack(anchor="w", pady=(10, 0))
        self._label(font_row, "字体大小", color=T.UI_TEXT_2,
                    font=self.f_small, bg=T.UI_PANEL).pack(side="left",
                                                          padx=(0, 10))
        self._font_scale_map = {
            "小 0.9": 0.9, "标准 1.0": 1.0,
            "大 1.12": 1.12, "特大 1.25": 1.25,
        }
        current_scale = self._font_scale
        current_label = next(
            (label for label, scale in self._font_scale_map.items()
             if abs(scale - current_scale) < 1e-6), "标准 1.0")
        self.font_scale_var = tk.StringVar(value=current_label)
        scale_menu = tk.OptionMenu(font_row, self.font_scale_var,
                                   *self._font_scale_map.keys())
        scale_menu.configure(bg=T.UI_PANEL_2, fg=T.UI_TEXT,
                             activebackground=T.UI_PANEL_3, relief="flat",
                             bd=0, highlightthickness=0,
                             font=self.f_small)
        scale_menu.pack(side="left")

        # 启动器
        launcher = section("启动器", left_col)
        self.check_update_var = tk.BooleanVar(
            value=bool(self.settings.get("check_update_on_start", True)))
        tk.Checkbutton(launcher, text="启动时检查更新", variable=self.check_update_var,
                       bg=T.UI_PANEL, fg=T.UI_TEXT_2, selectcolor=T.UI_PANEL,
                       activebackground=T.UI_PANEL,
                       activeforeground=T.UI_TEXT,
                       font=self.f_small).pack(anchor="w", pady=2)
        self.auto_download_var = tk.BooleanVar(
            value=bool(self.settings.get("auto_download_update", False)))
        tk.Checkbutton(launcher, text="发现新版本时自动下载（安装前仍确认）",
                       variable=self.auto_download_var,
                       bg=T.UI_PANEL, fg=T.UI_TEXT_2, selectcolor=T.UI_PANEL,
                       activebackground=T.UI_PANEL,
                       activeforeground=T.UI_TEXT,
                       font=self.f_small).pack(anchor="w", pady=2)
        self._label(
            launcher,
            "提示：以管理员身份运行 Hub 才能在 MaaNTE 已运行时发送「开始任务」热键；"
            "普通权限下异环清日常会改用 --autostart 自动开始。",
            color=T.UI_TEXT_3, font=self.f_aux, bg=T.UI_PANEL,
            wraplength=440, justify="left").pack(anchor="w", pady=(2, 0))
        row = tk.Frame(launcher, bg=T.UI_PANEL)
        row.pack(anchor="w", pady=2)
        self._label(row, "状态刷新间隔：", color=T.UI_TEXT_2,
                    font=self.f_small, bg=T.UI_PANEL).pack(side="left")
        self.refresh_var = tk.StringVar(
            value=str(self.settings.get("refresh_interval", 1.5)))
        refresh_menu = tk.OptionMenu(row, self.refresh_var, "1.0", "1.5", "2.0")
        refresh_menu.configure(bg=T.UI_PANEL_2, fg=T.UI_TEXT,
                               activebackground=T.UI_PANEL_3, relief="flat",
                               bd=0, highlightthickness=0, font=self.f_small)
        refresh_menu.pack(side="left")
        self._label(row, " 秒", color=T.UI_TEXT_3, font=self.f_aux,
                    bg=T.UI_PANEL).pack(side="left")
        row2 = tk.Frame(launcher, bg=T.UI_PANEL)
        row2.pack(anchor="w", pady=2)
        self._label(row2, "旧版关闭偏好（现会弹出确认）：", color=T.UI_TEXT_2, font=self.f_small,
                    bg=T.UI_PANEL).pack(side="left")
        self.close_action_var = tk.StringVar(
            value=self.settings.get("close_action", "exit"))
        for value, label in (("exit", "退出程序"),
                             ("minimize", "最小化（按托盘设置）")):
            tk.Radiobutton(row2, text=label, value=value,
                           variable=self.close_action_var, bg=T.UI_PANEL,
                           fg=T.UI_TEXT_2, selectcolor=T.UI_PANEL,
                           activebackground=T.UI_PANEL,
                           activeforeground=T.UI_TEXT,
                           font=self.f_small).pack(side="left", padx=(0, 12))
        self.minimize_to_tray_var = tk.BooleanVar(
            value=bool(self.settings.get("minimize_to_tray", True)))
        tk.Checkbutton(launcher, text="标题栏最小化按钮隐藏到托盘（关闭则最小化到任务栏）",
                       variable=self.minimize_to_tray_var,
                       bg=T.UI_PANEL, fg=T.UI_TEXT_2, selectcolor=T.UI_PANEL,
                       activebackground=T.UI_PANEL,
                       activeforeground=T.UI_TEXT,
                       font=self.f_small).pack(anchor="w", pady=2)
        self._label(launcher,
                    "点击 × 总会询问：任务栏、托盘、退出或取消；任务运行时退出会先停止任务。",
                    color=T.UI_TEXT_3, font=self.f_aux, bg=T.UI_PANEL,
                    wraplength=440, justify="left").pack(anchor="w")

        # 路径
        paths = section("路径", left_col)
        row = tk.Frame(paths, bg=T.UI_PANEL)
        row.pack(fill="x", pady=2)
        self._label(row, "脚本根目录：", color=T.UI_TEXT_2,
                    font=self.f_small, bg=T.UI_PANEL).pack(side="left")
        self.settings_root_var = tk.StringVar(value=self.search_root)
        tk.Label(row, textvariable=self.settings_root_var, bg=T.UI_PANEL,
                 fg=T.UI_TEXT_3, font=self.f_aux,
                 anchor="w").pack(side="left", fill="x", expand=True)
        self._button(row, "重新识别", self.rescan_paths, width=8).pack(
            side="right")
        row = tk.Frame(paths, bg=T.UI_PANEL)
        row.pack(fill="x", pady=(T.SPACE_UI_XS, 2))
        self._label(row, "Clash Verge：", color=T.UI_TEXT_2,
                    font=self.f_small, bg=T.UI_PANEL).pack(side="left")
        self.clash_var = tk.StringVar(value=self.clash_exe or "")
        clash_entry = RoundEntry(row, textvariable=self.clash_var, width=16,
                                 font=self.f_aux)
        clash_entry.pack(side="left", fill="x", expand=True,
                         padx=(0, 6), pady=2)
        clash_actions = tk.Frame(paths, bg=T.UI_PANEL)
        clash_actions.pack(fill="x", pady=(0, 2))
        self._button(clash_actions, "自动查找", self._auto_find_clash,
                     width=8).pack(side="right")
        self._button(clash_actions, "浏览", self._browse_clash,
                     width=6).pack(side="right", padx=(0, 6))

        # 清日常
        daily_frame = section("清日常", right_col)
        row = tk.Frame(daily_frame, bg=T.UI_PANEL)
        row.pack(fill="x", pady=2)
        self._label(row, "默认超时（分钟）：", color=T.UI_TEXT_2,
                    font=self.f_small, bg=T.UI_PANEL).pack(side="left")
        self.daily_timeout_var = tk.StringVar(
            value=str(self.settings.get("daily_default_timeout", 120)))
        RoundEntry(row, textvariable=self.daily_timeout_var, width=4,
                   font=self.f_small).pack(side="left", padx=(0, 16), pady=2)
        self._label(row, "（未单独设置时使用）", color=T.UI_TEXT_3,
                    font=self.f_aux, bg=T.UI_PANEL).pack(side="left")
        self.preview_var = tk.BooleanVar(
            value=bool(self.settings.get("daily_show_preview", True)))
        self.adb_var = tk.BooleanVar(
            value=bool(self.settings.get("adb_enabled", False)))
        self.daily_close_var = tk.BooleanVar(
            value=bool(self.settings.get("daily_close_after", True)))
        for var, text in ((self.preview_var, "执行前显示命令预览"),
                          (self.adb_var, "启用 ADB 检测（模拟器内游戏）"),
                          (self.daily_close_var, "完成后结束脚本（默认值）")):
            tk.Checkbutton(daily_frame, text=text, variable=var,
                           bg=T.UI_PANEL, fg=T.UI_TEXT_2,
                           selectcolor=T.UI_PANEL,
                           activebackground=T.UI_PANEL,
                           activeforeground=T.UI_TEXT,
                           font=self.f_small).pack(anchor="w", pady=1)

        # 关于与更新
        about = section("关于与更新", right_col)
        self._label(about, f"All-My-Maa v{VERSION}", color=T.UI_TEXT,
                    font=self.f_small, bg=T.UI_PANEL).pack(anchor="w", pady=1)
        self._label(about, "游戏脚本中心 · 一体化启动器",
                    color=T.UI_TEXT_3, font=self.f_aux,
                    bg=T.UI_PANEL).pack(anchor="w", pady=(0, 2))
        current_priv = "管理员" if store.hub_is_elevated() else "普通用户"
        self._label(about, f"当前权限：{current_priv} · 默认以管理员身份启动",
                    color=T.UI_TEXT_2, font=self.f_aux,
                    bg=T.UI_PANEL).pack(anchor="w", pady=(0, 6))
        links = tk.Frame(about, bg=T.UI_PANEL)
        links.pack(anchor="w")
        about_links = (
            ("关于软件", self.open_about, "primary"),
            ("检查软件更新", self.check_software_update, "normal"),
            ("问题反馈 / Bug", self.open_feedback, "normal"),
            ("更新日志", self._open_changelog, "ghost"),
            ("GitHub", lambda: self._open_url(PROJECT_GITHUB, "GitHub"),
             "ghost"),
            ("项目主页", lambda: self._open_url(PROJECT_PAGES, "项目主页"),
             "ghost"),
        )
        for index, (label, command, kind) in enumerate(about_links):
            self._button(links, label, command, kind=kind,
                         width=9, font=self.f_small).grid(
                row=index // 2, column=index % 2, padx=(0, 6), pady=2,
                sticky="w")

    # ---------------------------------------------------------- 关于 / 软件更新 / 小工具
    def open_script_dir(self):
        folder = _script_directory(self.search_root)
        if store.open_path(folder):
            self._toast("已打开脚本根目录")
        else:
            self._toast(f"脚本目录不存在：{folder}")

    def open_log_dir(self):
        log_path = runtime_log.current_log_path()
        folder = os.path.dirname(log_path) if log_path else _log_directory(store.APP_DIR)
        if store.open_path(folder):
            self._toast("已打开日志目录")
        else:
            self._toast(f"日志目录不存在：{folder}")

    def open_feedback(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("问题反馈 / Bug 报告 · All-My-Maa")
        dialog.configure(bg=T.UI_BG)
        dialog.transient(self.root)
        self._place_dialog(dialog, 760, 730)
        dialog.minsize(620, 560)
        dialog.rowconfigure(1, weight=1)
        dialog.columnconfigure(0, weight=1)
        self._label(dialog, "问题反馈 / Bug 报告", font=self.f_title,
                    bg=T.UI_BG).grid(row=0, column=0, sticky="w", padx=20, pady=(14, 8))
        area, body = self._scroll_area(dialog)
        area.grid(row=1, column=0, sticky="nsew", padx=20)
        self._label(body,
                    "报告会提交至公开的 GitHub Issues，需要登录 GitHub 并由你确认提交。\n"
                    "不会自动上传日志或配置；请勿填写密码、令牌、账号及个人路径。",
                    font=self.f_aux, color=T.UI_WARNING, bg=T.UI_BG,
                    justify="left", wraplength=660).pack(anchor="w", pady=(0, 10))
        kind = tk.StringVar(value="Bug")
        line = tk.Frame(body, bg=T.UI_BG)
        line.pack(fill="x")
        self._label(line, "反馈类型", bg=T.UI_BG).pack(side="left")
        tk.OptionMenu(line, kind, "Bug", "问题反馈", "功能建议").pack(side="left", padx=8)
        self._label(body, "标题（必填）", bg=T.UI_BG).pack(anchor="w", pady=(8, 2))
        title = self._entry(body, "")
        title.pack(fill="x")
        self._label(body, "相关功能 / 脚本（例如：托盘、ok-nte 清日常）",
                    bg=T.UI_BG).pack(anchor="w", pady=(8, 2))
        component = self._entry(body, "Hub")
        component.pack(fill="x")
        fields = {}
        for field, label in (("description", "问题描述（必填）"),
                             ("steps", "复现步骤"), ("expected", "预期结果"),
                             ("actual", "实际结果 / 错误提示")):
            self._label(body, label, bg=T.UI_BG).pack(anchor="w", pady=(8, 2))
            widget = tk.Text(body, height=3, wrap="word", bg=T.UI_PANEL_2,
                             fg=T.UI_TEXT, insertbackground=T.UI_TEXT,
                             font=self.f_small, relief="flat", highlightthickness=1,
                             highlightbackground=T.UI_BORDER)
            widget.pack(fill="x")
            fields[field] = widget
        include_env = tk.BooleanVar(value=True)
        tk.Checkbutton(body, text="附带 Hub / 系统 / Python 版本（不含个人路径）",
                       variable=include_env, bg=T.UI_BG, fg=T.UI_TEXT_2,
                       activebackground=T.UI_BG, activeforeground=T.UI_TEXT,
                       selectcolor=T.UI_PANEL_2).pack(anchor="w", pady=10)
        status = tk.StringVar(value="可先预览或复制报告，再打开 GitHub 提交。")
        footer = tk.Frame(dialog, bg=T.UI_BG)
        footer.grid(row=2, column=0, sticky="ew", padx=20, pady=12)
        self._label(footer, textvariable=status, font=self.f_aux,
                    bg=T.UI_BG, wraplength=660, justify="left").pack(anchor="w", pady=(0, 8))
        actions = tk.Frame(footer, bg=T.UI_BG)
        actions.pack(fill="x")

        def report():
            try:
                return feedback.build_report(
                    kind=kind.get(), title=title.get(), component=component.get(),
                    include_environment=include_env.get(),
                    **{name: widget.get("1.0", "end-1c") for name, widget in fields.items()})
            except ValueError as exc:
                messagebox.showwarning("请填写反馈", str(exc), parent=dialog)
                return None

        def copy_report(text):
            try:
                dialog.clipboard_clear()
                dialog.clipboard_append(text)
                dialog.update_idletasks()
                status.set("完整报告已复制。请确认内容中没有敏感信息。")
                return True
            except tk.TclError:
                status.set("复制失败，请使用预览窗口手动复制。")
                return False

        def preview():
            text = report()
            if text is not None:
                self._show_text_window("反馈报告预览", text)

        def copy():
            text = report()
            if text is not None:
                copy_report(text)

        def submit():
            text = report()
            if text is None:
                return
            if not messagebox.askyesno(
                    "公开反馈提醒", "将打开 GitHub 新建 Issue 页面，报告内容公开可见。\n"
                    "请确认未包含敏感信息；浏览器中仍需你点击提交。是否继续？", parent=dialog):
                return
            url, included = feedback.issue_url(title.get(), text)
            if not included:
                if not copy_report(text):
                    return
                messagebox.showinfo("报告较长", "完整报告已复制，请在 GitHub 正文中粘贴后提交。", parent=dialog)
            try:
                opened = webbrowser.open(url)
            except Exception:
                opened = False
            status.set("已打开 GitHub，请核对内容后提交。" if opened else
                       "浏览器未能打开。可复制报告后访问 github.com/Diaohesi/All-My-Maa/issues")

        def export_logs():
            destination = filedialog.asksaveasfilename(
                parent=dialog, title="导出脱敏 Hub 诊断包", defaultextension=".zip",
                initialfile="All-My-Maa-diagnostics-" + time.strftime("%Y%m%d-%H%M%S") + ".zip",
                filetypes=[("ZIP 诊断包", "*.zip")])
            if not destination:
                return
            try:
                runtime_log.export_diagnostics(destination)
                runtime_log.log_event("feedback.diagnostics_exported")
                status.set("诊断包已保存。请检查内容后手动附加到 GitHub Issue；不会自动上传。")
            except Exception:
                runtime_log.get_logger("ui").exception("feedback.diagnostics_export_failed")
                messagebox.showerror("导出失败", "无法导出诊断包，请检查目标目录权限后重试。", parent=dialog)

        self._button(footer, "导出脱敏诊断包（手动附加到 Issue）", export_logs,
                     kind="normal").pack(anchor="w", pady=(0, 8), before=actions)
        for label, command, style in (("预览报告", preview, "normal"),
                                      ("复制报告", copy, "normal"),
                                      ("去 GitHub 提交", submit, "primary")):
            self._button(actions, label, command, kind=style).pack(side="left", padx=(0, 8))
        self._button(actions, "关闭", dialog.destroy, kind="ghost").pack(side="right")
        title.focus_set()

    def open_about(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("关于软件 · All-My-Maa")
        dialog.configure(bg=T.UI_BG)
        dialog.transient(self.root)
        self._place_dialog(dialog, 620, 540)
        panel = RoundPanel(dialog, fill=T.UI_PANEL, border=T.UI_BORDER,
                           pad=T.SPACE_UI_XL)
        panel.pack(fill="both", expand=True, padx=T.SPACE_UI_MD,
                   pady=T.SPACE_UI_MD)
        body = panel.inner
        logo = self._ui_icon_photo("about", ICON_SIZES["about"])
        if logo is not None:
            tk.Label(body, image=logo, bg=T.UI_PANEL).pack(pady=(0, 6))
        self._label(body, "All-My-Maa", color=T.UI_TEXT, font=self.f_title,
                    bg=T.UI_PANEL).pack()
        self._label(body, "游戏脚本中心 · 一体化启动器", color=T.UI_TEXT_3,
                    font=self.f_small, bg=T.UI_PANEL).pack(pady=(2, 2))
        self._label(body, f"版本 v{VERSION}", color=T.UI_TEXT_2,
                    font=self.f_small, bg=T.UI_PANEL).pack()
        current_priv = "管理员" if store.hub_is_elevated() else "普通用户"
        self._label(body, f"当前权限：{current_priv}",
                    color=T.UI_TEXT, font=self.f_small,
                    bg=T.UI_PANEL).pack(pady=(2, 0))
        self._label(body, "默认以管理员身份启动（UAC）；取消 UAC 会以普通权限运行，"
                          "异环清日常热键/部分脚本功能可能受限",
                    color=T.UI_TEXT_3, font=self.f_aux,
                    bg=T.UI_PANEL, wraplength=520,
                    justify="center").pack(pady=(0, 4))
        self._label(body, _license_label(),
                    color=T.UI_TEXT_3, font=self.f_aux,
                    bg=T.UI_PANEL).pack(pady=(4, 10))

        links = tk.Frame(body, bg=T.UI_PANEL)
        links.pack(pady=(0, T.SPACE_UI_SM))
        entries = (
            ("GitHub", lambda: self._open_url(PROJECT_GITHUB, "GitHub")),
            ("项目主页", lambda: self._open_url(PROJECT_PAGES, "项目主页")),
            ("License", self._open_license),
            ("更新日志", self._open_changelog),
        )
        for label, command in entries:
            self._button(links, label, command, kind="ghost",
                         width=8, font=self.f_small).pack(side="left",
                                                         padx=3)
        self._label(body, "最近更新", color=T.UI_TEXT, font=self.f_small,
                    bg=T.UI_PANEL).pack(anchor="w", pady=(0, 4))
        text = tk.Text(body, height=9, bg=T.UI_PANEL_2, fg=T.UI_TEXT_2,
                       relief="flat", bd=0, highlightthickness=0,
                       wrap="word", font=self.f_aux)
        text.pack(fill="both", expand=True)
        text.insert("1.0", _changelog_preview_text(8))
        text.configure(state="disabled")
        footer = tk.Frame(body, bg=T.UI_PANEL)
        footer.pack(fill="x", pady=(T.SPACE_UI_SM, 0))
        self._button(footer, "检查软件更新", self.check_software_update,
                     kind="primary").pack(side="left")
        self._button(footer, "问题反馈 / Bug",
                     lambda: (dialog.destroy(), self.open_feedback()),
                     kind="normal").pack(side="left", padx=8)
        self._button(footer, "关闭", dialog.destroy).pack(side="right")
        dialog.grab_set()
        self.root.wait_window(dialog)

    def _open_license(self):
        path = _find_license()
        if path:
            self._open_file(path, "License")
        else:
            self._toast("未找到 LICENSE 文件（打包版需随 exe 附带）")

    def _open_file(self, path, label):
        try:
            os.startfile(path)
            self._toast(f"已打开 {label}")
        except Exception as exc:
            self._toast(f"打开 {label} 失败：{exc}")

    def _place_dialog(self, dialog, width, height):
        """把对话框居中放在主窗口内，并保证不超过主窗口可用区域。"""
        self.root.update_idletasks()
        max_w = max(480, self.root.winfo_width() - 80)
        max_h = max(360, self.root.winfo_height() - 100)
        width = min(int(width), max_w)
        height = min(int(height), max_h)
        x = self.root.winfo_rootx() + max(0, (self.root.winfo_width() - width) // 2)
        y = self.root.winfo_rooty() + max(0, (self.root.winfo_height() - height) // 2)
        dialog.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")

    def check_software_update(self, manual=True):
        if self.software_checking:
            if manual:
                self._toast("正在检查软件更新，请稍候…")
            return
        self.software_checking = True
        self.software_check_manual = bool(manual)
        if manual:
            self._toast("正在检查软件更新…")
        threading.Thread(target=self._software_update_worker,
                         daemon=True).start()

    def _software_update_worker(self):
        try:
            payload = store.http_get(RELEASE_API, timeout=12)
            info = parse_release_payload(payload, VERSION)
        except Exception as exc:
            info = {"error": f"{exc}"}
        self.software_queue.put(info)

    def _drain_software_update(self):
        try:
            info = self.software_queue.get_nowait()
        except queue.Empty:
            return
        self.software_checking = False
        manual = self.software_check_manual
        self.software_check_manual = False
        if info.get("error"):
            self._toast(f"检查软件更新失败：{info['error']}（请检查网络或代理）")
            return
        if not info.get("newer"):
            if manual:
                self._show_software_update(info)
            return
        if self.settings.get("auto_download_update") and info.get("newer"):
            self._toast(f"发现新版本 v{info.get('version')}，开始自动下载…")
            self._start_update_download(info)
            return
        self._show_software_update(info)

    def _show_software_update(self, info):
        dialog = tk.Toplevel(self.root)
        dialog.title("软件更新 · All-My-Maa")
        dialog.configure(bg=T.UI_BG)
        dialog.transient(self.root)
        self._place_dialog(dialog, 680, 540)
        panel = RoundPanel(dialog, fill=T.UI_PANEL, border=T.UI_BORDER,
                           pad=T.SPACE_UI_XL)
        panel.pack(fill="both", expand=True, padx=T.SPACE_UI_MD,
                   pady=T.SPACE_UI_MD)
        body = panel.inner
        self._label(body, "All-My-Maa 软件更新", color=T.UI_TEXT,
                    font=self.f_page, bg=T.UI_PANEL).pack(anchor="w")
        self._label(body, f"当前版本：v{info.get('current', VERSION)}",
                    color=T.UI_TEXT_2, font=self.f_small,
                    bg=T.UI_PANEL).pack(anchor="w", pady=(6, 2))
        version = info.get("version") or "未知"
        if info.get("newer"):
            headline = f"发现新版本：v{version}"
            color = T.UI_SUCCESS
        else:
            headline = f"已是最新版本（GitHub 最新：v{version}）"
            color = T.UI_TEXT_2
        self._label(body, headline, color=color, font=self.f_name,
                    bg=T.UI_PANEL).pack(anchor="w", pady=(0, 8))
        self._label(body, "更新内容", color=T.UI_TEXT, font=self.f_small,
                    bg=T.UI_PANEL).pack(anchor="w")
        text = tk.Text(body, height=12, bg=T.UI_PANEL_2, fg=T.UI_TEXT_2,
                       relief="flat", bd=0, highlightthickness=0,
                       wrap="word", font=self.f_small)
        text.pack(fill="both", expand=True, pady=(4, T.SPACE_UI_SM))
        changelog = format_changelog_text(info.get("changelog") or "")
        text.insert("1.0", changelog or "（该版本没有附带更新说明）")
        text.configure(state="disabled")
        footer = tk.Frame(body, bg=T.UI_PANEL)
        footer.pack(fill="x")
        if info.get("newer"):
            self._button(footer, "下载并更新",
                         lambda: (dialog.destroy(),
                                  self._start_update_download(info)),
                         kind="primary").pack(side="left")
            self._button(footer, "打开发布页",
                         lambda: self._open_url(info.get("url") or RELEASE_PAGE,
                                                "发布页")).pack(side="left",
                                                              padx=(8, 0))
        self._button(footer, "关闭", dialog.destroy).pack(side="right")
        self._label(body, "下载仅在确认后执行，程序不会静默重启。",
                    color=T.UI_TEXT_3, font=self.f_aux,
                    bg=T.UI_PANEL).pack(anchor="w", pady=(6, 0))
        dialog.grab_set()
        self.root.wait_window(dialog)

        dialog.grab_set()
        self.root.wait_window(dialog)

    # ---------------------------------------------------------- 自动更新
    def _git_state(self, root=None):
        root = root or store.APP_DIR
        is_git = os.path.isdir(os.path.join(root, ".git"))
        clean = False
        if is_git:
            try:
                proc = subprocess.run(
                    ["git", "-C", root, "status", "--porcelain"],
                    capture_output=True, text=True, timeout=10,
                    creationflags=0x08000000)
                clean = proc.returncode == 0 and not proc.stdout.strip()
            except Exception:
                clean = False
        return is_git, clean

    def _start_update_download(self, info):
        if not getattr(sys, "frozen", False):
            self._start_source_update(info)
            return
        asset = select_update_asset(info)
        if not asset:
            self._toast("该版本没有可下载的 exe/zip，已打开发布页")
            self._open_url(info.get("url") or RELEASE_PAGE, "发布页")
            return
        target = sys.executable or ""
        writable = False
        try:
            folder = os.path.dirname(target)
            probe = os.path.join(folder, ".allmymaa_write_test")
            with open(probe, "wb"):
                pass
            os.remove(probe)
            writable = True
        except Exception:
            writable = False
        if not can_auto_update(True, writable):
            messagebox.showwarning(
                "无法自动更新",
                "程序所在目录不可写（可能需要管理员权限）。\n"
                "请打开发布页手动下载更新。", parent=self.root)
            self._open_url(info.get("url") or RELEASE_PAGE, "发布页")
            return
        self._show_download_progress(info, asset)
        threading.Thread(target=self._download_worker,
                         args=(info, asset), daemon=True).start()

    def _show_download_progress(self, info, asset):
        try:
            self._close_update_progress()
        except Exception:
            pass
        dialog = tk.Toplevel(self.root)
        dialog.title("下载更新 · All-My-Maa")
        dialog.configure(bg=T.UI_BG)
        dialog.transient(self.root)
        self._place_dialog(dialog, 520, 220)
        panel = RoundPanel(dialog, fill=T.UI_PANEL, border=T.UI_BORDER,
                           pad=T.SPACE_UI_LG)
        panel.pack(fill="both", expand=True, padx=T.SPACE_UI_MD,
                   pady=T.SPACE_UI_MD)
        body = panel.inner
        self._label(body, f"正在下载 All-My-Maa v{info.get('version')}",
                    color=T.UI_TEXT, font=self.f_name,
                    bg=T.UI_PANEL).pack(anchor="w")
        var = tk.StringVar(value="准备下载…")
        tk.Label(body, textvariable=var, bg=T.UI_PANEL, fg=T.UI_TEXT_2,
                 font=self.f_small, anchor="w").pack(fill="x", pady=(8, 6))
        bar = tk.Canvas(body, height=10, bg=T.UI_PANEL_2,
                        highlightthickness=0, bd=0)
        bar.pack(fill="x")
        self._update_progress_dialog = dialog
        self._update_progress_var = var
        self._update_progress_bar = bar

    def _set_update_progress(self, percent, text=None):
        if self._update_progress_var is None:
            return
        percent = max(0, min(100, int(percent)))
        if text is not None:
            self._update_progress_var.set(text)
        else:
            self._update_progress_var.set(f"正在下载更新… {percent}%")
        bar = self._update_progress_bar
        if bar is not None:
            width = max(10, bar.winfo_width())
            bar.delete("all")
            _round_rect(bar, 0, 0, width - 1, 9, 5, T.UI_PANEL_2,
                        T.UI_BORDER_SOFT, 1)
            fill_w = int((width - 2) * percent / 100)
            if fill_w > 2:
                _round_rect(bar, 1, 1, 1 + fill_w, 8, 4,
                            T.UI_ACCENT, "", 0)

    def _close_update_progress(self):
        dialog = self._update_progress_dialog
        self._update_progress_dialog = None
        self._update_progress_var = None
        self._update_progress_bar = None
        if dialog is not None:
            try:
                dialog.destroy()
            except Exception:
                pass

    def _download_worker(self, info, asset):
        try:
            folder = tempfile.mkdtemp(prefix="allmymaa_update_")
            dest = os.path.join(folder, asset["name"])
            request = urllib.request.Request(
                asset["url"], headers={"User-Agent": "AllMyMaa-Update"})
            with urllib.request.urlopen(request, timeout=30) as response, \
                    open(dest, "wb") as fh:
                total = int(asset.get("size") or 0)
                try:
                    total = total or int(response.headers.get("Content-Length")
                                         or 0)
                except (TypeError, ValueError):
                    pass
                got = 0
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    fh.write(chunk)
                    got += len(chunk)
                    if total:
                        self.update_download_queue.put(
                            ("progress", min(99, int(got * 100 / total))))
            if total and os.path.getsize(dest) != total:
                raise OSError("下载大小校验失败")
            exe_path = dest
            if asset.get("kind") == "zip":
                exe_path = self._extract_update_zip(dest)
            self.update_download_queue.put(
                ("done", {"info": info, "asset": asset, "exe": exe_path,
                          "folder": folder}))
        except Exception as exc:
            self.update_download_queue.put(("error", str(exc)))

    @staticmethod
    def _extract_update_zip(path):
        folder = tempfile.mkdtemp(prefix="allmymaa_unzip_")
        with zipfile.ZipFile(path) as archive:
            archive.extractall(folder)
        candidates = []
        for root, _dirs, files in os.walk(folder):
            for name in files:
                if name.lower().endswith(".exe"):
                    full = os.path.join(root, name)
                    try:
                        candidates.append((os.path.getsize(full), full))
                    except OSError:
                        pass
        if not candidates:
            raise OSError("更新包中没有找到 exe")
        candidates.sort(reverse=True)
        return candidates[0][1]

    def _drain_update_download(self):
        while True:
            try:
                kind, payload = self.update_download_queue.get_nowait()
            except queue.Empty:
                return
            if kind == "progress":
                self._set_update_progress(payload)
            elif kind == "error":
                self._close_update_progress()
                self._toast(f"下载更新失败：{payload}")
            elif kind == "done":
                self._close_update_progress()
                self._show_install_confirm(payload)
            elif kind == "source_done":
                self._toast("源码更新完成")
                if messagebox.askyesno(
                        "更新完成", "代码已更新。是否立即重启 Hub？",
                        parent=self.root):
                    self._restart_from_source()
            elif kind == "source_error":
                self._toast(f"源码更新失败：{payload}")

    def _start_source_update(self, info):
        is_git, clean = self._git_state()
        if not should_source_update(is_git, clean):
            messagebox.showinfo(
                "无法自动更新",
                "当前以源码方式运行，且目录不是干净的 git 仓库。\n"
                "请打开发布页手动更新（不会覆盖你的本地修改）。",
                parent=self.root)
            self._open_url(info.get("url") or RELEASE_PAGE, "发布页")
            return
        if not messagebox.askyesno(
                "源码模式更新",
                "将执行 git pull --ff-only 更新代码，完成后可选择重启 Hub。\n"
                "确定继续吗？", parent=self.root):
            return
        self._toast("正在更新源码…")

        def worker():
            try:
                proc = subprocess.run(
                    ["git", "-C", store.APP_DIR, "pull", "--ff-only"],
                    capture_output=True, text=True, timeout=120,
                    creationflags=0x08000000)
                if proc.returncode != 0:
                    self.update_download_queue.put(
                        ("source_error", (proc.stderr or proc.stdout or
                                          "git pull 失败").strip()[:200]))
                else:
                    self.update_download_queue.put(("source_done", ""))
            except Exception as exc:
                self.update_download_queue.put(("source_error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _restart_from_source(self):
        hub = os.path.join(store.APP_DIR, "hub.pyw")
        if not os.path.isfile(hub):
            self._toast("未找到 hub.pyw，无法自动重启")
            return
        try:
            subprocess.Popen([sys.executable, hub], cwd=store.APP_DIR,
                             creationflags=0x00000008 | 0x00000200)
            self._on_close(force=True)
        except Exception as exc:
            self._toast(f"重启失败：{exc}")

    def _show_install_confirm(self, data):
        info = data.get("info") or {}
        exe = data.get("exe") or ""
        dialog = tk.Toplevel(self.root)
        dialog.title("安装更新 · All-My-Maa")
        dialog.configure(bg=T.UI_BG)
        dialog.transient(self.root)
        self._place_dialog(dialog, 560, 330)
        panel = RoundPanel(dialog, fill=T.UI_PANEL, border=T.UI_BORDER,
                           pad=T.SPACE_UI_XL)
        panel.pack(fill="both", expand=True, padx=T.SPACE_UI_MD,
                   pady=T.SPACE_UI_MD)
        body = panel.inner
        self._label(body, f"已下载 All-My-Maa v{info.get('version')}",
                    color=T.UI_TEXT, font=self.f_page,
                    bg=T.UI_PANEL).pack(anchor="w")
        self._label(body, "确认后将退出当前程序，由更新脚本备份并替换 exe，"
                          "然后启动新版本。",
                    color=T.UI_TEXT_2, font=self.f_small,
                    bg=T.UI_PANEL).pack(anchor="w", pady=(8, 6))
        self._label(body, f"更新文件：{os.path.basename(exe)}",
                    color=T.UI_TEXT_3, font=self.f_aux,
                    bg=T.UI_PANEL).pack(anchor="w")
        footer = tk.Frame(body, bg=T.UI_PANEL)
        footer.pack(fill="x", pady=(T.SPACE_UI_LG, 0))
        self._button(footer, "安装并重启",
                     lambda: (dialog.destroy(),
                              self._install_frozen_update(exe)),
                     kind="primary").pack(side="left")
        self._button(footer, "打开发布页",
                     lambda: self._open_url(info.get("url") or RELEASE_PAGE,
                                            "发布页")).pack(side="left",
                                                          padx=(8, 0))
        self._button(footer, "取消", dialog.destroy).pack(side="right")
        dialog.grab_set()
        self.root.wait_window(dialog)

    def _install_frozen_update(self, new_exe):
        target = sys.executable or ""
        if not can_auto_update(getattr(sys, "frozen", False), True):
            self._toast("当前不是打包模式或程序目录不可写，无法自动安装")
            return
        try:
            folder = tempfile.mkdtemp(prefix="allmymaa_updater_")
            ps1 = os.path.join(folder, "update_gamehub.ps1")
            with open(ps1, "w", encoding="utf-8-sig") as fh:
                fh.write(build_updater_script(os.getpid(), new_exe, target))
            cmd = os.path.join(folder, "update_gamehub.cmd")
            with open(cmd, "w", encoding="utf-8") as fh:
                fh.write("@echo off\r\n")
                fh.write("powershell -NoProfile -ExecutionPolicy Bypass "
                         f"-File \"{ps1}\"\r\n")
            subprocess.Popen(["cmd", "/c", cmd],
                             creationflags=0x00000008 | 0x00000010)
            self._toast("正在安装更新，程序即将退出…")
            self.root.after(500, self._on_close)
        except Exception as exc:
            self._toast(f"启动更新脚本失败：{exc}")

    # ---------------------------------------------------------- 更新日志
    def _open_changelog(self):
        path = _find_changelog()
        if not path:
            self._toast("未找到更新日志 CHANGELOG.md（打包版需随 exe 附带）")
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as fh:
                text = fh.read()
        except Exception as exc:
            self._toast(f"读取更新日志失败：{exc}")
            return
        content = format_changelog_text(text) or "（更新日志为空）"
        self._show_text_window("更新日志 · All-My-Maa", content)

    def _show_text_window(self, title, content):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.configure(bg=T.UI_BG)
        dialog.transient(self.root)
        self._place_dialog(dialog, 720, 560)
        text = tk.Text(dialog, bg=T.UI_PANEL, fg=T.UI_TEXT_2, relief="flat",
                       wrap="word", font=self.f_small)
        scroll = tk.Scrollbar(dialog, command=text.yview, width=10,
                              bg=T.UI_PANEL_2, troughcolor=T.UI_PANEL,
                              relief="flat", bd=0, highlightthickness=0)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(fill="both", expand=True, padx=(14, 0), pady=14)
        text.insert("1.0", content)
        text.configure(state="disabled")
        footer = tk.Frame(dialog, bg=T.UI_BG)
        footer.pack(fill="x", padx=14, pady=(0, 12))
        self._button(footer, "关闭", dialog.destroy).pack(side="right")
        dialog.grab_set()
        self.root.wait_window(dialog)

    def _open_doc(self, filename):
        path = os.path.join(store.APP_DIR, "docs", filename)
        if store.open_path(path):
            self._toast(f"已打开 {filename}")
        else:
            self._toast(f"文档不存在：{path}")

    def _pick_accent(self, color):
        self._accent_var = color
        self._refresh_accent_chips()

    def _refresh_accent_chips(self):
        for color, chip in getattr(self, "_accent_chips", {}).items():
            chip.configure(relief="sunken" if color == self._accent_var
                           else "flat", bd=2 if color == self._accent_var else 0)

    def _refresh_settings_view(self):
        if not hasattr(self, "settings_root_var"):
            return
        self.settings_root_var.set(self.search_root)
        self.clash_var.set(self.clash_exe or "")
        try:
            self.minimize_to_tray_var.set(
                bool(self.settings.get("minimize_to_tray", True)))
            self.close_action_var.set(
                self.settings.get("close_action", "exit"))
        except Exception:
            pass
        self._refresh_accent_chips()
        try:
            labels = getattr(self, "_font_scale_map", {})
            current = next(
                (label for label, scale in labels.items()
                 if abs(scale - self._font_scale) < 1e-6), "标准 1.0")
            self.font_scale_var.set(current)
        except Exception:
            pass

    def _browse_clash(self):
        path = filedialog.askopenfilename(
            parent=self.root, title="选择 Clash Verge 程序",
            filetypes=[("可执行程序", "*.exe"), ("所有文件", "*.*")])
        if path:
            self.clash_var.set(os.path.normpath(path))

    def _auto_find_clash(self):
        candidates = list(getattr(store, "CLASH_CANDIDATES", []))
        found = next((p for p in candidates if p and os.path.isfile(p)), "")
        if not found:
            for base in (os.environ.get("ProgramFiles", ""),
                         os.environ.get("ProgramFiles(x86)", ""),
                         os.path.join(os.environ.get("LOCALAPPDATA", ""),
                                      "Programs")):
                if not base or not os.path.isdir(base):
                    continue
                for name in ("Clash Verge", "clash-verge", "Clash Verge Rev"):
                    path = os.path.join(base, name, "clash-verge.exe")
                    if os.path.isfile(path):
                        found = path
                        break
                if found:
                    break
        if found:
            self.clash_var.set(found)
            self._toast("已找到 Clash Verge")
        else:
            self._toast("没有自动找到 Clash Verge，请手动浏览选择")

    def _apply_settings(self):
        try:
            timeout = max(1, min(600, int(
                self.daily_timeout_var.get().strip() or "120")))
        except ValueError:
            self._toast("默认超时必须是 1–600 的整数分钟")
            return
        values = dict(self.settings)
        new_scale = self._font_scale_map.get(
            self.font_scale_var.get(), self._font_scale)
        values.update({
            "accent": self._accent_var,
            "font_scale": new_scale,
            "auto_download_update": bool(self.auto_download_var.get()),
            "check_update_on_start": bool(self.check_update_var.get()),
            "refresh_interval": float(self.refresh_var.get() or 1.5),
            "close_action": self.close_action_var.get() or "exit",
            "minimize_to_tray": bool(self.minimize_to_tray_var.get()),
            "clash_exe": self.clash_var.get().strip(),
            "daily_default_timeout": timeout,
            "daily_show_preview": bool(self.preview_var.get()),
            "adb_enabled": bool(self.adb_var.get()),
            "daily_close_after": bool(self.daily_close_var.get()),
        })
        self.settings = store._clean_settings(values)
        self.clash_exe = self.settings.get("clash_exe") or self.clash_exe
        if self.clash_exe and not os.path.isfile(self.clash_exe):
            self.clash_exe = ""
            self.settings["clash_exe"] = ""
        self.adb_enabled = bool(self.settings.get("adb_enabled"))
        self._sync_tray()
        try:
            detector.set_adb_enabled(self.adb_enabled)
        except Exception:
            pass
        saved = self._save_config()
        self._accent_var = self.settings.get("accent") or self._accent_var
        scale_changed = abs(new_scale - self._font_scale) > 1e-6
        if scale_changed:
            self._apply_font_scale(new_scale)
        self._apply_accent_theme()
        self.show_page(self.page)
        self._schedule_poll()
        self._refresh_settings_view()
        self._refresh_home_states()
        self._refresh_daily_states()
        if saved:
            self._toast("设置已保存")

    def _apply_font_scale(self, scale):
        """v0.10：字体缩放立即生效（标题栏/按钮/行高/对话框后续创建同步）。"""
        global _FONT_SCALE
        try:
            scale = float(scale)
        except (TypeError, ValueError):
            scale = 1.0
        self._font_scale = scale
        _FONT_SCALE = scale
        self._setup_fonts()
        try:
            self.titlebar.apply_scale(scale)
            self.titlebar.refresh_buttons()
        except Exception:
            pass
        for header in getattr(self, "_page_headers", {}).values():
            try:
                header.apply_scale(scale)
            except Exception:
                pass

        def walk(widget):
            for child in widget.winfo_children():
                if isinstance(child, RoundButton):
                    try:
                        child.apply_scale(scale)
                    except Exception:
                        pass
                walk(child)

        walk(self.root)
        # 侧栏高度有限：字体仍按比例，按钮高度最多放大约 1.08 倍，避免底部版本溢出
        sidebar_scale = min(scale, 1.08)

        def walk_sidebar(widget):
            for child in widget.winfo_children():
                if isinstance(child, RoundButton):
                    try:
                        child.apply_scale(sidebar_scale)
                    except Exception:
                        pass
                walk_sidebar(child)

        try:
            walk_sidebar(self.sidebar)
        except Exception:
            pass
        self._rebuild_home()
        self._rebuild_daily()
        self._refresh_home_states()
        self._refresh_daily_states()
        if self.page == "settings":
            self._refresh_settings_view()

    def _schedule_poll(self):
        if self._poll_after:
            try:
                self.root.after_cancel(self._poll_after)
            except Exception:
                pass
        delay = _refresh_delay_ms(self.settings)
        self._poll_after = self.root.after(delay, self._poll)

    # ---------------------------------------------------------- 通用状态
    def _app_state(self, app):
        exe = app.get("script_exe", "")
        key = app.get("key", "")
        launch = app.get("launch") if isinstance(app.get("launch"), dict) else {}
        if not exe or not os.path.isfile(exe):
            if not launch.get("exe") or not os.path.isfile(launch.get("exe")):
                return "missing"
        if key in self.starting:
            if time.time() - self.starting[key] < 12:
                return "starting"
            self.starting.pop(key, None)
        return "on" if self.running.get(key, {}).get("script") else "off"

    def _game_state(self, app):
        state = self.game_states.get(app.get("key"))
        if state is None:
            try:
                state = detector.detect_game_state(
                    app, adb_enabled=self.adb_enabled)
            except Exception:
                state = {"running": False, "reason": "", "label": "未运行",
                         "hwnd": None, "configured": False, "source": "none",
                         "rules": {}}
            self.game_states[app["key"]] = state
        return state

    def _has_update(self, app):
        latest = self.latest.get(app["key"])
        current = self.versions.get(app["key"])
        return bool(latest and current and store.is_newer(latest, current))

    def _update_versions(self):
        for app in self.apps:
            self.versions[app["key"]] = store.read_version(app)

    def _refresh(self):
        names = store.snapshot_processes()
        windows = detector.snapshot_windows()
        for app in self.apps:
            key = app["key"]
            prev = self.running.get(key, {"script": False, "game": False})
            prev_game = self.game_states.get(key) or {}
            script_on = bool(app.get("script_procs")) and bool(
                names & set(app["script_procs"]))
            launch = app.get("launch")
            if isinstance(launch, dict) and launch.get("exe"):
                try:
                    script_on = store.launch_spec_running(app)
                except Exception:
                    script_on = False
            try:
                game_state = detector.detect_game_state(
                    app, windows=windows, processes=names,
                    adb_enabled=self.adb_enabled)
            except Exception:
                game_state = {"running": False, "reason": "", "label": "未运行",
                              "hwnd": None, "configured": False,
                              "source": "none", "rules": {}}
            self.game_states[key] = game_state
            game_on = bool(game_state.get("running"))
            self.running[key] = {"script": script_on, "game": game_on}
            if prev["script"] != script_on:
                if script_on and key in self.starting:
                    self.starting.pop(key, None)
                    self._toast(f"已启动 {app['game']} · {app['script']}")
                elif not script_on and prev["script"]:
                    self._toast(f"{app['game']} 的脚本已退出")
            if game_on and not prev_game.get("running"):
                self._toast(f"{app['game']} {game_state.get('label') or '已启动'}")
            elif prev_game.get("running") and not game_on:
                self._toast(f"{app['game']} 已退出")
        if self.page == "home":
            self._refresh_home_states()
        elif self.page == "daily":
            self._refresh_daily_states()
        self._refresh_sidebar()

    # ---------------------------------------------------------- 启动/更新
    def open_script(self, key):
        app = self._app_by_key(key)
        if app is None:
            return
        if self.running.get(key, {}).get("script"):
            focused = False
            if isinstance(app.get("launch"), dict):
                focused = store.focus_launch_spec(app)
            if not focused:
                focused = store.bring_to_front(app.get("script_procs") or [])
            self._toast(f"已切换到 {app.get('game')}" if focused
                        else f"{app.get('game')} 正在运行中（窗口未找到）")
            return
        self.launch_script(key)

    def launch_script(self, key):
        app = self._app_by_key(key)
        if app is None:
            return
        if self._app_state(app) == "missing":
            self._choose_script_path(key)
            return
        runtime_log.log_event("script.launch_requested", key=key, script=app.get("script"))
        try:
            ok, error, mode = store.launch_app(app)
        except Exception as exc:
            ok, error, mode = False, str(exc), "none"
        runtime_log.log_event("script.launch_result", key=key, ok=ok, mode=mode, error=error)
        if not ok:
            self._toast(f"启动 {app.get('game')} 失败：{error}")
            return
        if mode == "launcher":
            self._toast(f"未找到正式脚本，已回退启动 {app.get('script')} 启动器（可在启动器里更新）")
            return
        self.starting[key] = time.time()
        self._toast(f"正在启动 {app.get('game')} · {app.get('script')}")
        self._refresh_home_states()

    def _launch_updater(self, app):
        spec = app.get("launch") if isinstance(app.get("launch"), dict) else {}
        if not spec.get("launcher_exe"):
            return False
        ok, error = store.launch_updater(app)
        self._toast(f"正在打开 {app.get('script')} 更新器…" if ok
                    else f"打开更新器失败：{error}")
        return True

    def launch_game(self, key):
        runtime_log.log_event("game.launch_requested", key=key)
        app = self._app_by_key(key)
        if app is None:
            return
        try:
            state = detector.detect_game_state(app, adb_enabled=self.adb_enabled)
        except Exception:
            state = {"running": False, "reason": "", "label": "未运行",
                     "hwnd": None}
        self.game_states[key] = state
        if state.get("running"):
            hwnd = state.get("hwnd")
            if hwnd and detector.focus_window(hwnd):
                self._toast(f"已切换到 {app.get('game')}")
            elif store.bring_to_front(app.get("game_procs") or []):
                self._toast(f"已切换到 {app.get('game')}")
            else:
                self._toast(f"{app.get('game')} {state.get('label') or '运行中'}"
                            "（窗口未找到）")
            return
        exe = app.get("game_exe", "")
        saved = True
        try:
            spec = store.build_game_launch(app)
        except Exception:
            spec = {}
        if not spec.get("exe") and spec.get("strategy") != "maa_adb":
            self._toast(f"正在自动检测「{app.get('game')}」的启动程序…")
            try:
                candidates = store.find_game_candidates(app)
            except Exception:
                candidates = []
            if candidates:
                dialog = GameCandidateDialog(
                    self.root, candidates,
                    title=f"选择「{app.get('game')}」的游戏启动程序")
                self.root.wait_window(dialog)
                if not dialog.result:
                    self._toast("已取消启动游戏")
                    return
                exe = os.path.normpath(dialog.result)
            else:
                path = filedialog.askopenfilename(
                    parent=self.root,
                    title=f"选择「{app.get('game')}」的启动程序",
                    filetypes=[("可执行程序", "*.exe"), ("所有文件", "*.*")])
                if not path:
                    return
                exe = os.path.normpath(path)
            app["game_exe"] = exe
            app["game_procs"] = store.proc_names_for_exe(exe)
            saved = self._save_config()
            self._rebuild_home()
            spec = store.build_game_launch(app)
        if spec.get("exe") and spec.get("strategy") != "maa_adb" and \
                os.path.normpath(spec["exe"]) != \
                os.path.normpath(app.get("game_exe") or ""):
            app["game_exe"] = spec["exe"]
            app["game_procs"] = store.proc_names_for_exe(spec["exe"])
            saved = self._save_config()
            self._rebuild_home()
        if app.get("key") in ("nte", "oknte") and spec.get("exe"):
            if os.path.basename(spec["exe"]).lower() == "ntelauncher.exe":
                self._toast("正在打开异环启动器，请登录并点击开始游戏")
        if not spec.get("exe") and spec.get("strategy") != "maa_adb":
            self._toast(f"未找到 {app.get('game')} 的启动程序")
            return
        if spec.get("strategy") == "maa_adb":
            adb = spec.get("adb") or {}
            if not spec.get("exe") and not adb.get("path"):
                hint = (spec.get("fallback") or [{}])[0].get("hint") or \
                    "请从 MAA/模拟器手动启动游戏"
                self._toast(hint)
                return
        if app.get("key") in self.game_launching:
            self._toast("正在启动游戏，请稍候…")
            return
        self.game_launching[app["key"]] = True
        hint = spec.get("hint")
        self._toast(hint or f"正在启动 {app.get('game')}…")
        if hint:
            self._toast(hint)
        key_name = app["key"]

        def worker():
            try:
                result = store.launch_game_with_wait(app, spec)
            except Exception as exc:
                result = {"ok": False, "reason": f"启动异常：{exc}",
                          "spec": spec}
            self.game_launch_queue.put((key_name, result))

        threading.Thread(target=worker, daemon=True).start()

    def _drain_game_launch_events(self):
        while True:
            try:
                key, result = self.game_launch_queue.get_nowait()
            except queue.Empty:
                return
            self.game_launching.pop(key, None)
            runtime_log.log_event("game.launch_result", key=key, ok=result.get("ok"),
                                  reason=result.get("reason"))
            app = self._app_by_key(key)
            game = app.get("game") if app else key
            if result.get("ok"):
                self._toast(f"已启动 {game}")
                self._refresh_home_states()
                continue
            fallback = result.get("fallback") or {}
            hint = fallback.get("hint") if isinstance(fallback, dict) else ""
            if hint:
                self._toast(f"{game} 启动超时：{hint}")
            else:
                self._toast(f"启动 {game} 失败：{result.get('reason') or '未知错误'}")
            self._refresh_home_states()

    def download_game(self, key):
        app = self._app_by_key(key)
        if app is None:
            return
        url = app.get("download") or app.get("site")
        if not url:
            self._toast(f"{app.get('game')} 还没有配置下载页，可在「编辑此卡片」里填写")
            return
        self._open_url(url, f"{app.get('game')} 下载页")

    def update_app(self, key):
        app = self._app_by_key(key)
        if app is None:
            return
        if self._app_state(app) == "missing":
            self._choose_script_path(key)
            return
        if self.running.get(key, {}).get("script"):
            self._toast(f"{app.get('game')} 正在运行，请关闭后重新打开以检查更新")
            return
        if self.checking and key not in self.latest:
            self._toast("正在检查最新版本，请稍候再点一次")
            return
        if self._has_update(app):
            if not self._launch_updater(app):
                self.launch_script(key)
        elif key in self.latest and not self._has_update(app):
            self._toast(f"{app.get('script')} 已是最新版本 "
                        f"{self.versions.get(key, '')}")
        else:
            self._toast(f"无法获取最新版本，打开 {app.get('game')} 自行检查更新")
            if not self._launch_updater(app):
                self.launch_script(key)

    def open_folder(self, key):
        app = self._app_by_key(key)
        folder = os.path.dirname(app.get("script_exe", "")) if app else ""
        if store.open_path(folder):
            self._toast(f"已打开 {app.get('script')} 所在文件夹")
        else:
            self._toast("脚本目录不存在")

    def _open_url(self, url, label):
        if not url:
            self._toast(f"还没有配置 {label} 地址")
            return
        try:
            if not webbrowser.open(url):
                os.startfile(url)
            self._toast(f"已打开 {label}")
        except Exception:
            try:
                os.startfile(url)
                self._toast(f"已打开 {label}")
            except Exception:
                self._toast(f"打开失败：{url}")

    def _choose_script_path(self, key):
        app = self._app_by_key(key)
        if app is None:
            return
        path = filedialog.askopenfilename(
            parent=self.root, title=f"选择「{app.get('game')}」的脚本启动程序",
            initialdir=os.path.dirname(app.get("script_exe", ""))
            or self.search_root,
            filetypes=[("可执行程序", "*.exe"), ("所有文件", "*.*")])
        if not path:
            return
        app["script_exe"] = os.path.normpath(path)
        app["script_procs"] = store.proc_names_for_exe(path)
        store.refresh_launch_spec(app)
        saved = self._save_config()
        self._rebuild_home()
        if saved:
            self._toast(f"已更新 {app.get('script')} 的路径")

    def _store_icon(self, key, path):
        if not path or not os.path.isfile(path):
            return ""
        try:
            import shutil
            folder = os.path.join(store.APP_DIR, "user_icons")
            os.makedirs(folder, exist_ok=True)
            ext = os.path.splitext(path)[1].lower() or ".png"
            target = os.path.join(folder, key + ext)
            shutil.copyfile(path, target)
            return target
        except Exception:
            return path

    def _apply_detect_fields(self, app, data):
        fields = ("win_class", "win_title", "detect_procs", "adb_pkg")
        try:
            current = detector.read_game_rules(app)
            initial = detector.rules_to_fields(current)
        except Exception:
            current, initial = {}, {}
        values = {field: (data.get(field) or "").strip() for field in fields}
        if all(values[field] == (initial.get(field) or "").strip()
               for field in fields):
            return
        self.game_states.pop(app.get("key"), None)
        if not any(values.values()):
            app.pop("detect", None)
            app["detect_custom"] = False
            return
        try:
            app["detect"] = detector.rules_from_fields(
                win_class=values["win_class"], win_title=values["win_title"],
                detect_procs=values["detect_procs"],
                adb_pkg=values["adb_pkg"], base=current)
            app["detect_custom"] = True
        except Exception:
            pass

    # ---------------------------------------------------------- 添加/编辑/删除
    def add_app(self):
        def on_save(data):
            key = self._next_key()
            icon = self._store_icon(key, data["icon"]) if data["icon"] else ""
            app = dict(
                key=key, game=data["game"], script=data["script"], builtin=False,
                script_exe=data["script_exe"],
                script_procs=store._clean_procs(data["script_procs"],
                                                data["script_exe"]),
                game_exe=data["game_exe"],
                game_procs=store._clean_procs(data["game_procs"],
                                              data["game_exe"]),
                accent=data["accent"], fallback_version="",
                site=data["site"], github=data["github"],
                release=data["release"], download=data["download"],
                icon_path=icon or store.custom_icon_path(key),
                daily=store._clean_daily({"enabled": False}, key),
                daily_explicit=False,
            )
            self._apply_detect_fields(app, data)
            self.apps.append(app)
            if key not in self.daily_order:
                self.daily_order.append(key)
            saved = self._save_config()
            self._rebuild_all()
            if saved:
                self._toast(f"已添加 {app.get('game')} · {app.get('script')}")
            self._start_update_check()
        AppDialog(self.root, None, on_save=on_save)

    def edit_app(self, index):
        if index < 0 or index >= len(self.apps):
            return
        app = self.apps[index]

        def on_save(data):
            app["game"] = data["game"]
            app["script"] = data["script"]
            app["script_exe"] = data["script_exe"]
            app["script_procs"] = store._clean_procs(data["script_procs"],
                                                     data["script_exe"])
            app["game_exe"] = data["game_exe"]
            app["game_procs"] = store._clean_procs(data["game_procs"],
                                                   data["game_exe"])
            app["accent"] = data["accent"]
            app["site"] = data["site"]
            app["github"] = data["github"]
            app["release"] = data["release"]
            app["download"] = data["download"]
            if data["icon"] and os.path.isfile(data["icon"]):
                app["icon_path"] = self._store_icon(app["key"], data["icon"])
            self._apply_detect_fields(app, data)
            store.refresh_launch_spec(app)
            self.game_states.pop(app.get("key"), None)
            saved = self._save_config()
            self._rebuild_all()
            if saved:
                self._toast(f"已保存 {app.get('game')} 的配置")

        def on_delete():
            self.delete_app(index)

        AppDialog(self.root, app, on_save=on_save, on_delete=on_delete)

    def delete_app(self, index):
        if index < 0 or index >= len(self.apps):
            return
        app = self.apps[index]
        if app.get("builtin"):
            messagebox.showinfo("无法删除", "内置脚本卡片不能删除，可以修改或隐藏。",
                                parent=self.root)
            return
        if not messagebox.askyesno(
                "删除卡片",
                f"确定删除「{app.get('game')}」这张卡片吗？\n（不会删除任何文件）",
                parent=self.root):
            return
        key = app["key"]
        self.apps = [item for item in self.apps if item.get("key") != key]
        self.daily_order = [item for item in self.daily_order if item != key]
        self.game_states.pop(key, None)
        self.daily_manager = daily.DailyManager(
            self.apps, on_event=self._daily_manager_event)
        saved = self._save_config()
        self._rebuild_all()
        if saved:
            self._toast(f"已删除 {app.get('game')} 的卡片")

    def _next_key(self):
        index = 1
        existing = {app.get("key") for app in self.apps}
        while f"custom_{index}" in existing:
            index += 1
        return f"custom_{index}"

    def rescan_paths(self):
        found = 0
        for app in self.apps:
            exe_name = os.path.basename(app.get("script_exe", "")) or app.get(
                "script_exe_name", "")
            if not exe_name:
                continue
            hits = store.find_app_exe(self.search_root, exe_name)
            best = store.pick_best_exe(hits)
            if best and best != app.get("script_exe"):
                app["script_exe"] = best
                app["script_procs"] = store.proc_names_for_exe(best)
                store.refresh_launch_spec(app)
                found += 1
        saved = self._save_config()
        self._update_versions()
        self._rebuild_all()
        total = sum(1 for app in self.apps
                    if os.path.isfile(app.get("script_exe", "")))
        self._toast("路径识别完成：" + f"{total}/{len(self.apps)} 个脚本可用"
                    + (f"，更新了 {found} 个路径" if found else ""))

    def open_clash(self):
        path = self.clash_exe
        if path and os.path.exists(path):
            if store.snapshot_processes() & store.CLASH_PROCS:
                if store.bring_to_front(store.CLASH_PROCS):
                    self._toast("已切换到 Clash Verge")
                else:
                    self._toast("Clash Verge 已在运行（可能最小化在托盘）")
                return
            ok, error = store.launch_exe(path)
            self._toast("正在打开 Clash Verge" if ok
                        else f"打开 Clash Verge 失败：{error}")
            return
        path = filedialog.askopenfilename(
            parent=self.root, title="选择 Clash Verge 程序",
            filetypes=[("可执行程序", "*.exe")])
        if path:
            self.clash_exe = os.path.normpath(path)
            self.settings["clash_exe"] = self.clash_exe
            saved = self._save_config()
            if saved:
                self._toast("已记录 Clash Verge 路径，再点一次即可打开")
                self._refresh_settings_view()

    # ---------------------------------------------------------- 清日常（主页入口）
    def run_daily_single(self, key):
        app = self._app_by_key(key)
        if app is None:
            return
        state = self.daily_manager.state_of(key).get("state")
        if state in (daily.STARTING, daily.RUNNING):
            self._daily_stop_row(key)
            return
        if self.daily_manager.busy:
            self._toast(self.daily_manager.busy_reason(key)
                        or "已有清日常任务在运行")
            return
        plans = [daily.plan_for(app)]
        if self.settings.get("daily_show_preview", True):
            if not self._confirm_preview("清日常命令预览（dry-run）", plans):
                return
        ok, reason = self.daily_manager.start_single(key)
        if not ok:
            self._toast(reason)
            return
        self._append_daily_log(f"▶ 开始：{app.get('game')}")
        self._refresh_daily_states()
        self._refresh_home_states()

    def set_daily_enabled(self, key, enabled):
        app = self._app_by_key(key)
        if app is None:
            return
        settings = store._clean_daily(app.get("daily"), key)
        settings["enabled"] = bool(enabled)
        app["daily"] = settings
        app["daily_explicit"] = True
        self._save_config()

    def move_daily(self, key, delta):
        order = [item for item in self.daily_order if self._app_by_key(item)]
        if key not in order:
            order.append(key)
        index = order.index(key)
        target = index + delta
        if 0 <= target < len(order):
            order[index], order[target] = order[target], order[index]
            self.daily_order = order
            self._save_config()
            return True
        return False

    def daily_dry_run_text(self, keys=None):
        if keys is None:
            keys = daily.enabled_daily_keys(self.apps, self.daily_order)
            if not keys:
                keys = [key for key in self.daily_order if self._app_by_key(key)]
        plans = [daily.plan_for(self._app_by_key(key)) for key in keys]
        return "\n\n".join(daily.describe_plan(plan) for plan in plans)

    # ---------------------------------------------------------- 更新检查
    def _start_update_check(self, manual=False):
        if getattr(self, "checking", False):
            if manual:
                self._toast("正在检查更新中，请稍候…")
            return
        self.checking = True
        self.manual_check = manual
        if manual:
            self._toast("正在检查更新…")
        threading.Thread(target=self._update_worker, daemon=True).start()

    def _update_worker(self):
        for app in list(self.apps):
            try:
                latest = store.check_latest(app)
            except Exception:
                latest = None
            self.update_queue.put((app["key"], latest))
        self.update_queue.put(("done", None))

    def _drain_queue(self):
        changed = False
        while True:
            try:
                key, value = self.update_queue.get_nowait()
            except queue.Empty:
                break
            if key == "done":
                self.checking = False
                if self.manual_check:
                    self._toast(self._update_summary())
                self.manual_check = False
            else:
                self.latest[key] = value
                changed = True
        if changed:
            self._update_versions()
            self._refresh_home_states()

    def _update_summary(self):
        updates = [app for app in self.apps if self._has_update(app)]
        if updates:
            return "发现更新：" + "、".join(
                f"{app.get('game')} → {self.latest.get(app.get('key'))}"
                for app in updates)
        return "检查完成：没有发现新版本"

    def _on_refresh(self):
        self._start_update_check(manual=True)

    # ---------------------------------------------------------- 其他
    def _toast(self, text):
        runtime_log.log_event("ui.notice", text_length=len(str(text or "")))
        if not hasattr(self, "toast_var"):
            return
        self.toast_var.set(str(text or ""))
        if self._toast_after:
            try:
                self.root.after_cancel(self._toast_after)
            except Exception:
                pass
        self._toast_after = self.root.after(6000, lambda: self.toast_var.set(""))

    def _choose_close_action(self):
        if getattr(self, "_close_dialog_open", False):
            return "cancel"
        self._close_dialog_open = True
        dialog = tk.Toplevel(self.root)
        dialog.title("关闭窗口 · All-My-Maa")
        dialog.configure(bg=T.UI_BG)
        dialog.transient(self.root)
        self._place_dialog(dialog, 600, 300)
        result = {"action": "cancel"}
        panel = RoundPanel(dialog, fill=T.UI_PANEL, border=T.UI_BORDER, pad=20)
        panel.pack(fill="both", expand=True, padx=12, pady=12)
        self._label(panel.inner, "希望如何处理窗口？", font=self.f_title,
                    bg=T.UI_PANEL).pack(anchor="w", pady=(0, 10))
        manager = getattr(self, "daily_manager", None)
        busy = bool(manager and manager.snapshot().get("busy"))
        text = ("清日常正在执行：最小化后仍会继续运行；选择退出将先请求停止任务。" if busy else
                "最小化到任务栏或托盘不会退出 Hub；可以随时恢复窗口。")
        self._label(panel.inner, text, bg=T.UI_PANEL, wraplength=510,
                    justify="left").pack(anchor="w", pady=(0, 16))

        def choose(action):
            result["action"] = action
            dialog.destroy()

        actions = tk.Frame(panel.inner, bg=T.UI_PANEL)
        actions.pack(fill="x")
        for index, (label, action, kind) in enumerate((
                ("最小化到任务栏", "taskbar", "primary"),
                ("隐藏到托盘", "tray", "normal"),
                ("退出程序", "exit", "danger"),
                ("取消", "cancel", "ghost"))):
            self._button(actions, label, lambda value=action: choose(value),
                         kind=kind).grid(row=index // 2, column=index % 2,
                                         sticky="ew", padx=4, pady=4)
        dialog.protocol("WM_DELETE_WINDOW", lambda: choose("cancel"))
        dialog.bind("<Escape>", lambda _event: choose("cancel"))
        dialog.grab_set()
        try:
            self.root.wait_window(dialog)
        finally:
            self._close_dialog_open = False
        return result["action"]

    def _on_close(self, force=False):
        if not force:
            action = self._choose_close_action()
            runtime_log.log_event("window.close_choice", action=action)
            if action == "taskbar":
                self._minimize_to_taskbar()
                return
            if action == "tray":
                if not self._hide_to_tray(force=True):
                    self._toast("托盘暂不可用，已改为最小化到任务栏")
                    self._minimize_to_taskbar()
                return
            if action != "exit":
                return
        manager = getattr(self, "daily_manager", None)
        if manager and manager.snapshot().get("busy"):
            if not getattr(self, "_exit_waiting", False):
                self._exit_waiting = True
                self._exit_wait_started = time.monotonic()
                runtime_log.log_event("shutdown.wait_for_daily_stop")
                manager.stop_all()
            elapsed = time.monotonic() - getattr(self, "_exit_wait_started", time.monotonic())
            if elapsed >= 15:
                self._exit_waiting = False
                self._exit_wait_after = None
                runtime_log.log_event("shutdown.stop_wait_timeout", elapsed=elapsed)
                abandon = messagebox.askyesno(
                    "任务仍未停止", "停止请求已发出，但任务超过 15 秒仍未结束。\n\n"
                    "是否仅退出 Hub？外部脚本或游戏可能继续运行，需要手动检查。\n"
                    "选择「否」保留 Hub 窗口，稍后可重试退出。", parent=self.root)
                if not abandon:
                    self._toast("已取消退出；停止请求仍有效，请检查脚本状态")
                    return
            else:
                self._toast("正在停止本次清日常，结束后退出 Hub…")
                previous = getattr(self, "_exit_wait_after", None)
                if previous:
                    self.root.after_cancel(previous)
                self._exit_wait_after = self.root.after(200, lambda: self._on_close(force=True))
                return
        runtime_log.log_event("shutdown.ui_close")
        self._closing = True
        for attr in ("_poll_after", "_toast_after", "_startup_check_after",
                     "_startup_software_after", "_exit_wait_after"):
            after_id = getattr(self, attr, None)
            if after_id:
                try:
                    self.root.after_cancel(after_id)
                except Exception:
                    pass
                setattr(self, attr, None)
        if self.tray is not None:
            try:
                self.tray.stop()
            except Exception:
                pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def _poll(self):
        try:
            self._drain_queue()
            self._drain_daily_events()
            self._drain_software_update()
            self._drain_update_download()
            self._drain_game_launch_events()
            self._refresh()
        except Exception:
            pass
        if not self._closing:
            self._schedule_poll()

    def _rebuild_all(self):
        self._update_versions()
        self.daily_manager = daily.DailyManager(
            self.apps, on_event=self._daily_manager_event)
        self._rebuild_home()
        self._rebuild_daily()
        self._refresh()


def _find_license():
    """定位 LICENSE：源码运行用仓库根目录，打包版用 exe 同目录/_MEIPASS。"""
    import sys
    candidates = []
    bundle = getattr(sys, "_MEIPASS", "")
    if bundle:
        candidates.append(os.path.join(bundle, "LICENSE"))
        candidates.append(os.path.join(bundle, "LICENSE.md"))
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt"):
        candidates.append(os.path.join(store.APP_DIR, name))
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return ""


def _license_label():
    """从 LICENSE 文件识别许可证名称，输出一行「License：MIT License」。"""
    path = _find_license()
    if not path:
        return "License：随程序附带"
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
            head = fh.read(4096)
    except Exception:
        return "License：随程序附带"
    low = head.lower()
    known = (
        ("MIT License", "mit license"),
        ("Apache License 2.0", "apache license"),
        ("GNU GPL v3", "gnu general public license"),
        ("GNU LGPL", "gnu lesser general public license"),
        ("BSD 3-Clause", "bsd 3-clause"),
        ("BSD 2-Clause", "bsd 2-clause"),
        ("Mozilla Public License 2.0", "mozilla public license"),
    )
    for label, needle in known:
        if needle in low:
            return f"License：{label}"
    match = re.search(r"SPDX-License-Identifier:\s*([^\s]+)", head)
    if match:
        return f"License：{match.group(1)}"
    return "License：见随程序附带的 LICENSE 文件"


def _markdown_to_plain(text):
    """把一行 Markdown 变成纯文本：去 #/列表/引用/粗体/斜体/代码/链接语法。"""
    line = str(text or "").strip()
    line = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", line)
    line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)
    line = re.sub(r"<https?://[^>]+>", "", line)
    line = line.replace("**", "").replace("__", "").replace("`", "")
    line = re.sub(r"~~(.*?)~~", r"\1", line)
    line = re.sub(r"(?<!\w)[*_]([^*_]+)[*_](?!\w)", r"\1", line)
    line = re.sub(r"^#{1,6}\s*", "", line)
    line = re.sub(r"^>\s*", "", line)
    line = re.sub(r"^[-*+]\s+", "", line)
    line = re.sub(r"^\d+[.)]\s+", "", line)
    if re.fullmatch(r"[-*_]{3,}", line):
        return ""
    return line.strip()


def _markdown_body_to_plain(body):
    lines = []
    for raw in str(body or "").splitlines():
        line = _markdown_to_plain(raw)
        if line == "" and (not lines or lines[-1] == ""):
            continue
        lines.append(line)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def format_changelog_text(text, limit_entries=None):
    """把 CHANGELOG / GitHub release Markdown 转成适合 Text 显示的纯文本。

    - `## vX.Y.Z (日期)` -> `vX.Y.Z · 日期` 单独一行（版本从新到旧）
    - 去掉行首 #/列表/引用符号，去掉 **、反引号、[]() 链接语法（保留文字）
    - 条目保留换行；limit_entries 限制显示的版本数
    """
    raw = str(text or "").strip()
    if not raw:
        return ""
    sections = _parse_changelog(raw)
    blocks = []
    if sections:
        selected = sections
        if limit_entries is not None:
            try:
                selected = sections[:max(1, int(limit_entries))]
            except (TypeError, ValueError):
                selected = sections
        for section in selected:
            title = section["version"]
            if section["date"]:
                title += f" · {section['date']}"
            body = _markdown_body_to_plain(section["body"])
            blocks.append(title + (("\n\n" + body) if body else ""))
    else:
        cleaned = _markdown_body_to_plain(raw)
        if cleaned:
            blocks.append(cleaned)
    return "\n\n".join(blocks).strip()


def _changelog_preview_text(limit=6):
    """关于对话框里的更新日志预览（最新版本在最上面，已转纯文本）。"""
    path = _find_changelog()
    if not path:
        return "（未找到 CHANGELOG.md）"
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            text = fh.read()
    except Exception:
        return "（更新日志读取失败）"
    formatted = format_changelog_text(text, limit)
    return formatted or "（更新日志为空）"


def parse_release_payload(payload, current):
    """解析 GitHub latest release JSON，返回纯数据（供 UI 与自测使用）。

    不自动下载/安装；失败时返回 {"error": "..."}。
    """
    import json
    try:
        if isinstance(payload, bytes):
            text = payload.decode("utf-8", "replace")
        else:
            text = payload
        data = json.loads(text) if isinstance(text, (str, bytes)) else payload
    except Exception as exc:
        return {"error": f"解析 release 信息失败：{exc}"}
    if not isinstance(data, dict):
        return {"error": "release 信息格式不正确"}
    raw = str(data.get("tag_name") or data.get("name") or "").strip()
    version = raw[1:] if raw[:1] in ("v", "V") else raw
    if not version:
        return {"error": "release 信息缺少版本号"}
    if not store.version_key(version):
        return {"error": f"无法识别版本号：{raw}"}
    assets = []
    for item in data.get("assets") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        url = str(item.get("browser_download_url")
                  or item.get("url") or "").strip()
        if not name or not url:
            continue
        try:
            size = int(item.get("size") or 0)
        except (TypeError, ValueError):
            size = 0
        assets.append({"name": name, "url": url, "size": max(0, size)})
    return {
        "error": "",
        "current": str(current),
        "version": version,
        "newer": store.is_newer(version, current),
        "changelog": str(data.get("body") or ""),
        "url": str(data.get("html_url") or RELEASE_PAGE),
        "name": str(data.get("name") or ""),
        "published_at": str(data.get("published_at") or ""),
        "assets": assets,
    }


def select_update_asset(payload):
    """从 release JSON/解析结果中选择更新包：优先 exe，其次 zip。"""
    if not isinstance(payload, dict):
        return None
    assets = payload.get("assets")
    if not isinstance(assets, list):
        return None
    exes, zips = [], []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "").strip()
        url = str(asset.get("url") or asset.get("browser_download_url")
                  or "").strip()
        if not name or not url:
            continue
        try:
            size = int(asset.get("size") or 0)
        except (TypeError, ValueError):
            size = 0
        item = {"name": name, "url": url, "size": max(0, size)}
        low = name.lower()
        if low.endswith(".exe"):
            item["kind"] = "exe"
            exes.append(item)
        elif low.endswith(".zip"):
            item["kind"] = "zip"
            zips.append(item)
    for group in (exes, zips):
        if not group:
            continue
        group.sort(key=lambda item: (
            0 if ("gamehub" in item["name"].lower()
                  or "allmymaa" in item["name"].lower()) else 1,
            item["name"].lower()))
        return group[0]
    return None


def build_updater_script(pid, new_exe, target_exe):
    """生成等待 PID 退出→备份→覆盖→启动新 exe 的 PowerShell 脚本。"""
    def quote(value):
        return "'" + str(value).replace("'", "''") + "'"

    try:
        pid = int(pid)
    except (TypeError, ValueError):
        pid = 0
    new_exe = os.path.normpath(str(new_exe))
    target_exe = os.path.normpath(str(target_exe))
    lines = [
        "$ErrorActionPreference = 'Stop'",
        "try {",
        f"  Wait-Process -Id {pid} -Timeout 60 -ErrorAction SilentlyContinue",
        "} catch {}",
        "Start-Sleep -Milliseconds 400",
        f"Copy-Item -LiteralPath {quote(target_exe)} "
        f"-Destination {quote(target_exe + '.bak')} -Force",
        f"Copy-Item -LiteralPath {quote(new_exe)} "
        f"-Destination {quote(target_exe + '.new')} -Force",
        f"Move-Item -LiteralPath {quote(target_exe + '.new')} "
        f"-Destination {quote(target_exe)} -Force",
        f"Start-Process -FilePath {quote(target_exe)}",
    ]
    return "\r\n".join(lines) + "\r\n"


def can_auto_update(frozen, target_writable):
    """frozen exe 且目标可写时才允许自替换。"""
    return bool(frozen and target_writable)


def should_source_update(is_git, clean):
    """源码模式只有干净 git 仓库才允许 git pull 更新。"""
    return bool(is_git and clean)


def update_available(current, latest):
    """版本门：latest 是否比 current 新。"""
    return bool(store.is_newer(latest, current))


def _script_directory(root):
    """脚本根目录（小工具：打开脚本目录）。"""
    return os.path.abspath(root) if root else store.APP_DIR


def _log_directory(app_dir=None):
    """日志目录：优先 <app>/logs 或 <app>/log，否则回退 app 目录。"""
    base = app_dir or store.APP_DIR
    for name in ("logs", "log"):
        path = os.path.join(base, name)
        if os.path.isdir(path):
            return path
    return base


def _find_changelog():
    """定位 CHANGELOG.md：源码运行用仓库根目录，打包版用 exe 同目录/_MEIPASS。"""
    import sys
    candidates = []
    bundle = getattr(sys, "_MEIPASS", "")
    if bundle:
        candidates.append(os.path.join(bundle, "CHANGELOG.md"))
    candidates.append(os.path.join(store.APP_DIR, "CHANGELOG.md"))
    candidates.append(os.path.join(os.getcwd(), "CHANGELOG.md"))
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return ""


def _parse_changelog(text):
    """解析 `## vX.Y.Z (日期)` 分节，按版本号从新到旧排序（最新在最上面）。"""
    import re
    sections = []
    current = None
    heading = re.compile(
        r"^##\s+(?:\[)?(v?\d+(?:\.\d+)*)(?:\])?\s*(?:[（(]([^）)]*)[）)])?\s*$")
    for line in (text or "").splitlines():
        match = heading.match(line.strip())
        if match:
            if current is not None:
                sections.append(current)
            current = {"version": match.group(1),
                       "date": (match.group(2) or "").strip(),
                       "body": []}
        elif current is not None:
            current["body"].append(line)
    if current is not None:
        sections.append(current)
    for section in sections:
        section["body"] = "\n".join(section["body"]).strip("\n")
    sections.sort(key=lambda item: store.version_key(item["version"]),
                  reverse=True)
    return sections


def _refresh_delay_ms(settings):
    """把 settings.refresh_interval 转成 after() 毫秒（非法值回落 1.5s）。"""
    try:
        interval = float((settings or {}).get("refresh_interval", 1.5))
    except (TypeError, ValueError):
        interval = 1.5
    if interval not in [float(item) for item in store.REFRESH_INTERVALS]:
        interval = 1.5
    return int(interval * 1000)


def run():
    import ctypes
    mutex = store.kernel32.CreateMutexW(None, False, "Local\\AllMyMaa_SingleInstance")
    if mutex and ctypes.get_last_error() == 183:
        store.focus_window(TITLE)
        return
    root = tk.Tk()
    GameHub(root)
    try:
        root.mainloop()
    finally:
        if mutex:
            store.kernel32.CloseHandle(mutex)
