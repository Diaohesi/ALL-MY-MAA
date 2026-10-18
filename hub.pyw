# -*- coding: utf-8 -*-
"""游戏脚本中心 · GameHub Lite v0.3

把「明日方舟 MAA」「异环 MaaNTE」「鸣潮 ok-ww」「明日方舟终末地 MaaEnd」
四个脚本软件收进同一个窗口：一键启动、实时状态、版本检查与更新入口、
官网/GitHub 直达、Clash Verge 快捷打开。

可移植性：脚本路径自动识别并保存为相对路径，整个文件夹搬到别的电脑 / 盘符也能用。

运行方式：双击「启动游戏中心.bat」。
依赖：仅 Python 3 + tkinter（Windows 自带）。
"""
import ctypes
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import urllib.parse
import urllib.request
import webbrowser
from ctypes import wintypes

# ------------------------------------------------------------------ 基础常量
W, H = 1200, 560
CARD_X = [48, 330, 612, 894]
CARD_Y, CARD_W, CARD_H = 126, 258, 342
BTN_W, BTN_H = CARD_W - 48, 44
BTN_Y = CARD_Y + 248
PILL_Y = CARD_Y + 204
PILL_W, PILL_H = 96, 24
ACT_Y = CARD_Y + 316                     # 卡片底部操作链接
RESCAN_RECT = (764, 35, 112, 28)         # 重新识别路径
CLASH_RECT = (886, 35, 136, 28)          # Clash Verge 按钮

# 兼容源码运行与 PyInstaller 打包运行
FROZEN = bool(getattr(sys, "frozen", False))
if FROZEN:
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
    ASSETS = os.path.join(getattr(sys, "_MEIPASS", APP_DIR), "assets")
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    ASSETS = os.path.join(APP_DIR, "assets")
HUB_DIR = APP_DIR
BASE_DIR = os.path.dirname(APP_DIR)      # 脚本所在的上一级目录
CONFIG = os.path.join(APP_DIR, "config.json")
SEARCH_ROOT = BASE_DIR                   # 默认在 Hub 所在目录附近找脚本

CLASH_PROCS = {"CLASH-VERGE.EXE"}
CLASH_CANDIDATES = [
    r"C:\Program Files\Clash Verge\clash-verge.exe",
    r"C:\Program Files (x86)\Clash Verge\clash-verge.exe",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Clash Verge",
                 "clash-verge.exe"),
]

# 颜色
COLOR_BG = "#0a0d13"
COLOR_TXT = "#eaf0f8"
COLOR_TXT2 = "#9aa8bc"
COLOR_TXT3 = "#68788e"
COLOR_OK = "#4ade80"
COLOR_ERR = "#ff7f7f"
COLOR_WAIT = "#ffce6b"

# ------------------------------------------------------------------ 应用清单
# exe_name 用于自动识别路径；default_exe 只是“预期位置”，被识别结果覆盖
APPS = [
    dict(key="maa", game="明日方舟", script="MAA", exe_name="MAA.exe",
         default_exe=os.path.join(BASE_DIR, "MAA-v5.1.0-win-x64", "MAA.exe"),
         fallback_version="v6.19.0", procs={"MAA.EXE"}, accent="#4fc3ff",
         site="https://maa.plus/",
         github="https://github.com/MaaAssistantArknights/MaaAssistantArknights",
         release="https://github.com/MaaAssistantArknights/MaaAssistantArknights/releases/latest"),
    dict(key="nte", game="异环", script="MaaNTE", exe_name="MaaNTE.exe",
         default_exe=os.path.join(BASE_DIR, "MaaNTE", "MaaNTE.exe"),
         fallback_version="v1.6.0", procs={"MAANTE.EXE"}, accent="#b98bff",
         site="https://maante.org/",
         github="https://github.com/1bananachicken/MaaNTE",
         release="https://github.com/1bananachicken/MaaNTE/releases/latest"),
    dict(key="wuwa", game="鸣潮", script="ok-ww", exe_name="ok-ww.exe",
         default_exe=os.path.join(BASE_DIR, "WuwaMAA", "ok-ww", "ok-ww.exe"),
         fallback_version="v3.7.4", procs={"OK-WW.EXE"}, accent="#5ee7c7",
         site="https://ok-script.com/ok-ww",
         github="https://github.com/ok-oldking/ok-wuthering-waves",
         release="https://github.com/ok-oldking/ok-wuthering-waves/releases/latest"),
    dict(key="maaend", game="明日方舟终末地", script="MaaEnd", exe_name="MaaEnd.exe",
         default_exe=os.path.join(BASE_DIR, "MaaEnd-win-x86_64-v2.33.0", "MaaEnd.exe"),
         fallback_version="v2.33.0", procs={"MAAEND.EXE"}, accent="#ffe066",
         site="https://maaend.com/",
         github="https://github.com/MaaEnd/MaaEnd",
         release="https://github.com/MaaEnd/MaaEnd/releases/latest"),
]

# 自动识别路径时跳过的“重”目录，避免扫描太慢
SEARCH_SKIP = {
    "cache", "config", "data", "resource", "resources", "resource_adb",
    "resource_cloud_adb", "resource_linux", "resource_macos", "resource_playcover",
    "python", "lib", "site-packages", "ebwebview", "repo", "debug", "agent",
    "thirdparty", "maafw", "__pycache__", "logs", "locales", "tasks", ".git",
    ".old", "achievement", "externals", "res", "working", "docs", "dist", "build",
}

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GameHub"}
CURL = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "curl.exe")


# ------------------------------------------------------------------ 通用小工具
def version_key(text):
    """把 v6.16.8 / 1.6.0 之类转成可比较的元组。"""
    nums = re.findall(r"\d+", text or "")
    return tuple(int(x) for x in nums[:4])


def is_newer(latest, current):
    a, b = version_key(latest), version_key(current)
    return bool(a and b and a > b)


def http_get(url, timeout=10):
    """优先用系统 curl.exe（对代理 / TLS 兼容性更好），失败再退回 urllib。"""
    if os.path.exists(CURL):
        try:
            proc = subprocess.run(
                [CURL, "-sS", "-L", "-m", str(timeout), "-A", UA["User-Agent"], url],
                capture_output=True, creationflags=0x08000000)
            if proc.returncode == 0:
                return proc.stdout
            raise OSError(proc.stderr.decode("utf-8", "ignore").strip()[:160])
        except OSError:
            pass
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def final_url(url, timeout=10):
    """跟随跳转并返回最终地址（用于从 /releases/latest 得到最新 tag）。"""
    if os.path.exists(CURL):
        proc = subprocess.run(
            [CURL, "-sS", "-L", "-m", str(timeout), "-o", "NUL",
             "-w", "%{http_code} %{url_effective}", "-A", UA["User-Agent"], url],
            capture_output=True, creationflags=0x08000000)
        if proc.returncode != 0:
            raise OSError(proc.stderr.decode("utf-8", "ignore").strip()[:160])
        text = proc.stdout.decode("utf-8", "ignore").strip()
        code, _, effective = text.partition(" ")
        if not code.startswith("2"):
            raise OSError(f"HTTP {code}")
        return effective
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.geturl()


def github_latest_tag(url, timeout=10):
    """通过 releases/latest 的跳转地址拿到最新 tag（不消耗 GitHub API 配额）。"""
    match = re.search(r"/releases/tag/([^/?#]+)", final_url(url, timeout))
    if match:
        return urllib.parse.unquote(match.group(1))
    return None


# ------------------------------------------------------------------ 读取 exe 文件版本
_ver = ctypes.WinDLL("version", use_last_error=True)


class VS_FIXEDFILEINFO(ctypes.Structure):
    _fields_ = [
        ("dwSignature", wintypes.DWORD), ("dwStrucVersion", wintypes.DWORD),
        ("dwFileVersionMS", wintypes.DWORD), ("dwFileVersionLS", wintypes.DWORD),
        ("dwProductVersionMS", wintypes.DWORD), ("dwProductVersionLS", wintypes.DWORD),
        ("dwFileFlagsMask", wintypes.DWORD), ("dwFileFlags", wintypes.DWORD),
        ("dwFileOS", wintypes.DWORD), ("dwFileType", wintypes.DWORD),
        ("dwFileSubtype", wintypes.DWORD), ("dwFileDateMS", wintypes.DWORD),
        ("dwFileDateLS", wintypes.DWORD),
    ]


_ver.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
_ver.GetFileVersionInfoSizeW.restype = wintypes.DWORD
_ver.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                     ctypes.c_void_p]
_ver.GetFileVersionInfoW.restype = wintypes.BOOL
_ver.VerQueryValueW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR,
                                ctypes.POINTER(ctypes.c_void_p),
                                ctypes.POINTER(wintypes.UINT)]
_ver.VerQueryValueW.restype = wintypes.BOOL


def file_version(path):
    """读取 exe 的文件版本，例如 '6.19.0'。"""
    try:
        size = _ver.GetFileVersionInfoSizeW(path, None)
        if not size:
            return ""
        buf = ctypes.create_string_buffer(size)
        if not _ver.GetFileVersionInfoW(path, 0, size, buf):
            return ""
        ptr = ctypes.c_void_p()
        length = wintypes.UINT()
        if not _ver.VerQueryValueW(buf, "\\", ctypes.byref(ptr), ctypes.byref(length)):
            return ""
        info = ctypes.cast(ptr, ctypes.POINTER(VS_FIXEDFILEINFO)).contents
        ms, ls = info.dwFileVersionMS, info.dwFileVersionLS
        return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}"
    except Exception:
        return ""


# ------------------------------------------------------------------ 路径自动识别
def find_app_exe(root, exe_name, max_depth=4):
    """在 root 下递归查找指定 exe（跳过缓存/资源等重目录）。"""
    root = os.path.abspath(root)
    hits = []
    if not os.path.isdir(root):
        return hits
    for dirpath, dirnames, filenames in os.walk(root):
        depth = dirpath[len(root):].count(os.sep)
        if depth >= max_depth:
            dirnames[:] = []
        else:
            dirnames[:] = [d for d in dirnames
                           if d.lower() not in SEARCH_SKIP and not d.startswith(".")]
        for name in filenames:
            if name.lower() == exe_name.lower():
                hits.append(os.path.join(dirpath, name))
    return hits


def pick_best_exe(paths):
    """多个候选时，优先版本号高的目录，其次修改时间新的。"""
    def score(path):
        folder = os.path.basename(os.path.dirname(path))
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = 0
        return (version_key(folder), mtime)
    return max(paths, key=score) if paths else None


# ------------------------------------------------------------------ Win32 API
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
user32.GetAncestor.restype = wintypes.HWND

TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE = ctypes.c_void_p(-1).value


def snapshot_processes():
    """返回当前所有进程名（大写）集合。"""
    names = set()
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == INVALID_HANDLE:
        return names
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            names.add(entry.szExeFile.upper())
            ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snap)
    return names


def find_windows_for_pids(pids):
    """找出属于给定进程的可见顶层窗口。"""
    found = []
    pid_of = user32.GetWindowThreadProcessId
    pid_of.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    pid_of.restype = wintypes.DWORD

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        pid_of(hwnd, ctypes.byref(pid))
        if pid.value in pids and user32.GetWindowTextLengthW(hwnd) > 0:
            found.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return found


def bring_to_front(procs):
    """把已运行程序的主窗口提到最前；成功返回 True。"""
    names = snapshot_processes()
    if not (names & procs):
        return False
    pids = set()
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == INVALID_HANDLE:
        return False
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            if entry.szExeFile.upper() in procs:
                pids.add(entry.th32ProcessID)
            ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snap)

    for hwnd in find_windows_for_pids(pids):
        try:
            user32.ShowWindow(hwnd, 9)          # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
            user32.SwitchToThisWindow(hwnd, True)
            return True
        except Exception:
            continue
    return False


HUB_TITLE = "游戏脚本中心"


def find_hub_window():
    """找到已经在运行的 Hub 窗口。"""
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _lparam):
        cls = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, cls, 64)
        if cls.value != "TkTopLevel":
            return True
        text = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, text, 256)
        if text.value == HUB_TITLE:
            found.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


def focus_hub_window():
    hwnd = find_hub_window()
    if not hwnd:
        return False
    try:
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        user32.SwitchToThisWindow(hwnd, True)
        return True
    except Exception:
        return False


def set_dark_titlebar(root):
    """Windows 11 深色标题栏，与界面融为一体。"""
    try:
        hwnd = user32.GetAncestor(root.winfo_id(), 2)  # GA_ROOT
        dwm = ctypes.WinDLL("dwmapi")
        CAPTION = 0x00140E0B        # COLORREF: BGR(#0b0e14)
        TEXT = 0x00F9F5F2
        for attr, value in ((20, 1), (34, CAPTION), (35, CAPTION), (36, TEXT)):
            v = ctypes.c_int(value)
            dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))
    except Exception:
        pass


# ------------------------------------------------------------------ 主界面
class GameHub:
    def __init__(self, root):
        self.root = root
        self.apps = [dict(a) for a in APPS]
        for app in self.apps:
            app["exe"] = app["default_exe"]
        self.states = ["off"] * len(self.apps)
        self.versions = [a["fallback_version"] for a in self.apps]
        self.latest = [None] * len(self.apps)
        self.checked = [False] * len(self.apps)
        self.start_ts = [0.0] * len(self.apps)
        self.hover = -2            # -2 无 / -1 Clash / -3 重新识别 / >=0 卡片
        self.hover_zone = ""
        self.toast_after = None
        self.checking = False
        self.manual_check = False
        self.update_queue = queue.Queue()
        self.config = {}
        self.search_root = SEARCH_ROOT
        self.clash_exe = ""

        self._load_config()
        self._resolve_apps()
        self._setup_fonts()
        self._build_ui()
        self.root.after(120, self._poll)
        self.root.after(900, self._start_update_check)
        missing = [a["script"] for a in self.apps if not os.path.exists(a["exe"])]
        if missing:
            self._toast("未找到 " + "、".join(missing) + "，点卡片选择路径或右上角重新识别")
        else:
            self._toast("就绪 · 等待启动")

    # ---------------------------------------------------------- 配置 / 路径
    def _load_config(self):
        if os.path.exists(CONFIG):
            try:
                with open(CONFIG, "r", encoding="utf-8") as f:
                    self.config = json.load(f) or {}
            except Exception:
                self.config = {}
        root = self.config.get("root")
        if root and os.path.isdir(root):
            self.search_root = root
        self.clash_exe = self._resolve_clash()

    def _resolve_clash(self):
        stored = self.config.get("clash")
        if stored and os.path.exists(stored):
            return stored
        for path in CLASH_CANDIDATES:
            if path and os.path.exists(path):
                return path
        return CLASH_CANDIDATES[0]

    def _app_config(self):
        apps = self.config.get("apps")
        return apps if isinstance(apps, dict) else {}

    def _stored_path(self, value):
        """配置里保存的路径：优先相对 search_root 解析，也兼容旧版绝对路径。"""
        if not value:
            return None
        candidates = []
        if os.path.isabs(value):
            candidates.append(value)
        candidates.append(os.path.normpath(os.path.join(self.search_root, value)))
        for path in candidates:
            if os.path.isfile(path):
                return path
        return None

    def _portable_path(self, path):
        """尽量保存成相对路径，整体搬走也不失效。"""
        try:
            rel = os.path.relpath(path, self.search_root)
            if not rel.startswith(".."):
                return rel.replace("\\", "/")
        except ValueError:
            pass
        return path

    def _save_config(self):
        try:
            data = {
                "version": 2,
                "apps": {a["key"]: self._portable_path(a["exe"]) for a in self.apps},
                "clash": self.clash_exe,
            }
            if os.path.normpath(self.search_root) != os.path.normpath(SEARCH_ROOT):
                data["root"] = self.search_root
            with open(CONFIG, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _resolve_apps(self, force=False):
        """识别每个脚本的 exe：配置优先 → 自动扫描 → 预期位置。"""
        stored = self._app_config()
        changed = False
        for app in self.apps:
            stored_path = None if force else self._stored_path(stored.get(app["key"]))
            if stored_path:
                app["exe"] = stored_path
                continue
            hits = find_app_exe(self.search_root, app["exe_name"])
            best = pick_best_exe(hits)
            if best:
                app["exe"] = best
                changed = True
            elif not os.path.exists(app["exe"]):
                app["exe"] = app["default_exe"]
        if changed or force or not os.path.exists(CONFIG):
            self._save_config()

    def _rescan_paths(self):
        self._resolve_apps(force=True)
        self._update_versions()
        self._refresh()
        found = sum(1 for a in self.apps if os.path.exists(a["exe"]))
        self._toast(f"已重新识别：找到 {found} / {len(self.apps)} 个脚本")
        if found < len(self.apps):
            self.root.after(2500, lambda: self._toast(
                "未找到的脚本可点卡片手动选择路径，或把脚本放到 Hub 同目录"))

    def _setup_fonts(self):
        fam = "Microsoft YaHei"
        self.f_status = tkfont.Font(family=fam, size=-11)
        self.f_script = tkfont.Font(family=fam, size=-11)
        self.f_link = tkfont.Font(family=fam, size=-10)
        self.f_btn = tkfont.Font(family=fam, size=-13, weight="bold")
        self.f_foot = tkfont.Font(family=fam, size=-10)

    def _build_ui(self):
        self.root.title(HUB_TITLE)
        self.root.configure(bg=COLOR_BG)
        self.root.resizable(False, False)
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{W}x{H}+{max(0, (sw - W) // 2)}+{max(0, (sh - H) // 2 - 20)}")
        try:
            self.icon = tk.PhotoImage(file=os.path.join(ASSETS, "hub.png"))
            self.root.iconphoto(True, self.icon)
        except Exception:
            pass
        set_dark_titlebar(self.root)

        self.canvas = tk.Canvas(self.root, width=W, height=H, bg=COLOR_BG,
                                highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        # 背景（正常 + 每张卡片的悬停变体）
        self.bg_images = {}
        for name, fn in [("home", "bg_home.png")] + [
                (f"hover{i}", f"bg_hover_{i}.png") for i in range(len(self.apps))]:
            self.bg_images[name] = tk.PhotoImage(file=os.path.join(ASSETS, fn))
        self.bg_item = self.canvas.create_image(0, 0, anchor="nw",
                                                image=self.bg_images["home"])

        # 右上角两个小按钮
        self.header_buttons = {
            "rescan": {
                "rect": RESCAN_RECT,
                "label": "重新识别路径",
                "normal": tk.PhotoImage(file=os.path.join(ASSETS, "rescan_normal.png")),
                "hover": tk.PhotoImage(file=os.path.join(ASSETS, "rescan_hover.png")),
            },
            "clash": {
                "rect": CLASH_RECT,
                "label": "打开 Clash Verge",
                "normal": tk.PhotoImage(file=os.path.join(ASSETS, "clash_normal.png")),
                "hover": tk.PhotoImage(file=os.path.join(ASSETS, "clash_hover.png")),
            },
        }
        for name, btn in self.header_buttons.items():
            x, y, w, h = btn["rect"]
            btn["item"] = self.canvas.create_image(x, y, anchor="nw", image=btn["normal"])
            btn["text"] = self.canvas.create_text(
                x + w // 2, y + h // 2, text=btn["label"],
                font=self.f_link, fill=COLOR_TXT2)

        # 每个卡片的按钮、状态圆点、动态文字
        self.btn_images = {}
        for i in range(len(self.apps)):
            for state in ("normal", "hover", "off"):
                fn = f"button_{i}_{state}.png"
                self.btn_images[(i, state)] = tk.PhotoImage(file=os.path.join(ASSETS, fn))
        self.dot_on = tk.PhotoImage(file=os.path.join(ASSETS, "dot_on.png"))
        self.dot_off = tk.PhotoImage(file=os.path.join(ASSETS, "dot_off.png"))

        cx0 = lambda i: CARD_X[i] + CARD_W // 2
        self.btn_items, self.dot_items, self.btn_text, self.status_text = [], [], [], []
        self.script_text = []
        for i, app in enumerate(self.apps):
            bx = CARD_X[i] + 24
            self.btn_items.append(self.canvas.create_image(
                bx, BTN_Y, anchor="nw", image=self.btn_images[(i, "normal")]))
            self.dot_items.append(self.canvas.create_image(
                cx0(i) - 45, PILL_Y + PILL_H // 2, anchor="w", image=self.dot_off))
            self.status_text.append(self.canvas.create_text(
                cx0(i) - 37, PILL_Y + PILL_H // 2, anchor="w", text="未启动",
                font=self.f_status, fill=COLOR_TXT2))
            self.script_text.append(self.canvas.create_text(
                cx0(i), CARD_Y + 166, text=app["script"],
                font=self.f_script, fill=COLOR_TXT3))
            self.btn_text.append(self.canvas.create_text(
                cx0(i), BTN_Y + BTN_H // 2, text="启动",
                font=self.f_btn, fill=app["accent"]))

        # 卡片底部操作链接：更新 / 官网 / GitHub / 文件夹
        self.act_items, self.act_rects = [], []
        labels = [("更新", "update"), ("官网", "site"),
                  ("GitHub", "github"), ("文件夹", "folder")]
        gap = 16
        for i in range(len(self.apps)):
            widths = [self.f_link.measure(t) for t, _ in labels]
            total = sum(widths) + gap * (len(labels) - 1)
            x = CARD_X[i] + (CARD_W - total) / 2
            items, rects = [], []
            for (text, zone), w in zip(labels, widths):
                item = self.canvas.create_text(x, ACT_Y, text=text, anchor="w",
                                               font=self.f_link, fill=COLOR_TXT3)
                rects.append((x - 2, ACT_Y - 8, x + w + 2, ACT_Y + 8, zone))
                items.append((item, zone))
                x += w + gap
            self.act_items.append(items)
            self.act_rects.append(rects)

        self.foot_text = self.canvas.create_text(
            48, 520, anchor="w", text="", font=self.f_foot, fill=COLOR_TXT3)

        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", lambda e: self._set_hover(-2, ""))
        self.canvas.bind("<Button-1>", self._on_click)
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        for idx in range(len(self.apps)):
            self.root.bind(str(idx + 1), lambda e, i=idx: self.launch(i))
        self.root.bind("<F5>", lambda e: self._on_refresh())

        self._update_versions()
        self._refresh()
        self.root.focus_force()

    # ---------------------------------------------------------- 版本
    def _read_version(self, app):
        """读取本地已安装版本（脚本自己升级后也能显示正确版本）。"""
        folder = os.path.dirname(app["exe"])
        try:
            if app["key"] == "maa":
                # 已安装版本以 exe 文件版本为准（缓存 summary.json 是“最新版本”，不是本地版本）
                v = file_version(app["exe"])
                if v:
                    return "v" + v
                p = os.path.join(folder, "cache", "version", "summary.json")
                with open(p, "r", encoding="utf-8") as f:
                    v = (json.load(f).get("stable") or {}).get("version", "")
                if v:
                    return v if v.startswith("v") else "v" + v
                m = re.search(r"(\d+\.\d+\.\d+)", os.path.basename(folder))
                if m:
                    return "v" + m.group(1)
            elif app["key"] in ("nte", "maaend"):
                with open(os.path.join(folder, "interface.json"), "r", encoding="utf-8") as f:
                    v = str(json.load(f).get("version", ""))
                if v:
                    return v if v.startswith("v") else "v" + v
            elif app["key"] == "wuwa":
                with open(os.path.join(folder, "data", "apps", "ok-ww", "app.json"),
                          "r", encoding="utf-8") as f:
                    return json.load(f).get("current_version", "") or ""
        except Exception:
            pass
        return app.get("fallback_version", "")

    def _update_versions(self):
        for i, app in enumerate(self.apps):
            self.versions[i] = self._read_version(app)
        self._refresh_version_ui()

    def _has_update(self, i):
        latest = self.latest[i]
        return bool(latest and self.versions[i] and is_newer(latest, self.versions[i]))

    def _refresh_version_ui(self):
        for i, app in enumerate(self.apps):
            text = app["script"]
            if self.versions[i]:
                text += f" · {self.versions[i]}"
            has = self._has_update(i)
            if has:
                text += f" → {self.latest[i]}"
            self.canvas.itemconfigure(
                self.script_text[i], text=text,
                fill=app["accent"] if has else COLOR_TXT3)
        if getattr(self, "act_items", None):
            self._paint_links()

    # ---------------------------------------------------------- 更新检查
    def _check_latest_version(self, app):
        # MAA 有官方版本 API，优先用它
        if app["key"] == "maa":
            try:
                body = http_get(
                    "https://api.maa.plus/MaaAssistantArknights/api/version/stable.json", 8)
                version = json.loads(body.decode("utf-8", "ignore")).get("version")
                if version:
                    return version
            except Exception:
                pass
        try:
            return github_latest_tag(app["release"], timeout=10)
        except Exception:
            return None

    def _start_update_check(self, manual=False):
        if self.checking:
            if manual:
                self._toast("正在检查更新中，请稍候…")
            return
        self.checking = True
        self.manual_check = manual
        if manual:
            self._toast("正在检查更新…")
        threading.Thread(target=self._update_check_worker, daemon=True).start()

    def _update_check_worker(self):
        for i, app in enumerate(self.apps):
            try:
                latest = self._check_latest_version(app)
            except Exception:
                latest = None
            self.update_queue.put((i, latest))
        self.update_queue.put(("done", None))

    def _drain_update_queue(self):
        changed = False
        while True:
            try:
                key, value = self.update_queue.get_nowait()
            except queue.Empty:
                break
            if key == "done":
                self.checking = False
                self._refresh_version_ui()
                if self.manual_check:
                    self._toast(self._update_summary())
                self.manual_check = False
            else:
                self.latest[key] = value
                self.checked[key] = True
                changed = True
        if changed:
            self._refresh_version_ui()

    def _update_summary(self):
        pending = [i for i in range(len(self.apps)) if self._has_update(i)]
        failed = [i for i in range(len(self.apps)) if not self.latest[i]]
        if pending:
            names = "、".join(self.apps[i]["script"] for i in pending)
            extra = f"（{len(failed)} 个无法检查）" if failed else ""
            return f"发现可更新：{names}{extra}，点卡片底部「更新」"
        if len(failed) == len(self.apps):
            return "更新检查失败：网络不可用，可先打开 Clash Verge 再按 F5"
        if failed:
            names = "、".join(self.apps[i]["script"] for i in failed)
            return f"其余脚本已是最新（{names} 暂时无法检查）"
        return "全部脚本已是最新版本"

    def _on_refresh(self):
        self._update_versions()
        self._start_update_check(manual=True)
        self._refresh()

    # ---------------------------------------------------------- 状态与绘制
    def _state_of(self, i):
        app = self.apps[i]
        if not os.path.exists(app["exe"]):
            return "missing"
        return self.states[i]

    def _refresh(self):
        names = snapshot_processes()
        now = self.start_ts
        for i, app in enumerate(self.apps):
            prev = self.states[i]
            exists = os.path.exists(app["exe"])
            running = bool(names & app["procs"])
            if not exists:
                state = "missing"
            elif running:
                state = "on"
            elif self.states[i] == "starting":
                if time.time() - now[i] > 12:
                    state = "off"
                else:
                    state = "starting"
            else:
                state = "off"
            if state != prev:
                self.states[i] = state
                if prev == "starting" and state == "on":
                    self._toast(f"已启动 {app['game']} · {app['script']}")
                elif prev == "starting" and state == "off":
                    self._toast(f"{app['game']} 启动超时，请检查是否被拦截")
                elif prev == "on" and state == "off":
                    self._toast(f"{app['game']} 已退出")
            self._paint_card(i)

    def _paint_card(self, i):
        app = self.apps[i]
        state = self._state_of(i)
        zone = self.hover_zone if self.hover == i else ""

        # 状态圆点 + 文字（在胶囊内居中）
        if state == "on":
            text, color, dot = "运行中", COLOR_OK, self.dot_on
        elif state == "starting":
            text, color, dot = "启动中", COLOR_WAIT, self.dot_on
        elif state == "missing":
            text, color, dot = "路径缺失", COLOR_ERR, self.dot_off
        else:
            text, color, dot = "未启动", COLOR_TXT2, self.dot_off
        tw = self.f_status.measure(text)
        cx = CARD_X[i] + CARD_W // 2
        dot_x = cx - (20 + 3 + tw) // 2
        self.canvas.coords(self.dot_items[i], dot_x, PILL_Y + PILL_H // 2)
        self.canvas.coords(self.status_text[i], dot_x + 23, PILL_Y + PILL_H // 2)
        self.canvas.itemconfigure(self.dot_items[i], image=dot)
        self.canvas.itemconfigure(self.status_text[i], text=text, fill=color)

        # 按钮底图
        if state in ("on", "missing"):
            img = self.btn_images[(i, "off")]
        elif zone == "button":
            img = self.btn_images[(i, "hover")]
        else:
            img = self.btn_images[(i, "normal")]
        self.canvas.itemconfigure(self.btn_items[i], image=img)

        # 按钮文字
        if state == "on":
            self.canvas.itemconfigure(self.btn_text[i], text="已运行", fill=COLOR_TXT3)
        elif state == "starting":
            self.canvas.itemconfigure(self.btn_text[i], text="启动中…", fill=COLOR_WAIT)
        elif state == "missing":
            self.canvas.itemconfigure(self.btn_text[i], text="选择路径", fill=COLOR_ERR)
        else:
            self.canvas.itemconfigure(self.btn_text[i], text="启动", fill=app["accent"])

        # 底部链接颜色（可更新时「更新」高亮）
        has_update = self._has_update(i)
        for item, lzone in self.act_items[i]:
            if self.hover == i and self.hover_zone == lzone:
                fill = app["accent"]
            elif lzone == "update" and has_update:
                fill = app["accent"]
            elif self.hover == i:
                fill = COLOR_TXT2
            else:
                fill = COLOR_TXT3
            self.canvas.itemconfigure(item, fill=fill)

    def _paint_links(self):
        for i in range(len(self.apps)):
            self._paint_card(i)

    def _set_hover(self, i, zone):
        if self.hover == i and self.hover_zone == zone:
            return
        old = self.hover
        self.hover, self.hover_zone = i, zone
        if i >= 0:
            self.canvas.itemconfigure(self.bg_item, image=self.bg_images[f"hover{i}"])
        else:
            self.canvas.itemconfigure(self.bg_item, image=self.bg_images["home"])

        for name, btn in self.header_buttons.items():
            hovered = (i == -1 and name == "clash") or (i == -3 and name == "rescan")
            self.canvas.itemconfigure(btn["item"],
                                      image=btn["hover"] if hovered else btn["normal"])
            self.canvas.itemconfigure(btn["text"],
                                      fill=COLOR_TXT if hovered else COLOR_TXT2)

        if old >= 0:
            self._paint_card(old)
        if i >= 0:
            self._paint_card(i)
        self.canvas.configure(cursor="hand2" if (i >= 0 or i in (-1, -3)) else "")

    def _hit(self, x, y):
        """返回 (区域标识, 子区域)。-2 空白 / -1 Clash / -3 重新识别 / >=0 卡片。"""
        for name, btn in self.header_buttons.items():
            bx, by, bw, bh = btn["rect"]
            if bx <= x <= bx + bw and by <= y <= by + bh:
                return (-1 if name == "clash" else -3), name
        for i in range(len(self.apps)):
            x0 = CARD_X[i]
            if x0 <= x <= x0 + CARD_W and CARD_Y <= y <= CARD_Y + CARD_H:
                bx, by = x0 + 24, BTN_Y
                if bx <= x <= bx + BTN_W and by <= y <= by + BTN_H:
                    return i, "button"
                for ax0, ay0, ax1, ay1, zone in self.act_rects[i]:
                    if ax0 <= x <= ax1 and ay0 <= y <= ay1:
                        return i, zone
                return i, "card"
        return -2, ""

    # ---------------------------------------------------------- 事件
    def _on_motion(self, event):
        i, zone = self._hit(event.x, event.y)
        self._set_hover(i, zone)

    def _on_click(self, event):
        i, zone = self._hit(event.x, event.y)
        if zone == "clash":
            self.open_clash()
            return
        if zone == "rescan":
            self._rescan_paths()
            return
        if i < 0:
            return
        if zone == "update":
            self.update_app(i)
        elif zone == "site":
            self.open_link(i, "site")
        elif zone == "github":
            self.open_link(i, "github")
        elif zone == "folder":
            self.open_folder(i)
        else:
            self.launch(i)

    # ---------------------------------------------------------- 动作
    def launch(self, i, mode="launch"):
        app = self.apps[i]
        state = self._state_of(i)
        if state == "missing":
            self.choose_path(i)
            return
        if state == "on":
            if bring_to_front(app["procs"]):
                self._toast(f"已切换到 {app['game']}")
            else:
                self._toast(f"{app['game']} 正在运行中（窗口未找到）")
            return
        if state == "starting":
            return
        try:
            subprocess.Popen(
                [app["exe"]],
                cwd=os.path.dirname(app["exe"]),
                close_fds=True,
                creationflags=0x00000008 | 0x00000200,  # DETACHED | NEW_PROCESS_GROUP
            )
        except OSError as exc:
            code = getattr(exc, "winerror", None) or exc.errno
            if code == 740:  # ERROR_ELEVATION_REQUIRED
                if not self._shell_launch(app["exe"]):
                    self._toast(f"{app['game']} 需要管理员权限，启动被取消")
                    return
            else:
                self._toast(f"启动 {app['game']} 失败：{exc.strerror or exc}")
                return
        self.start_ts[i] = time.time()
        self.states[i] = "starting"
        self._paint_card(i)
        if mode == "update":
            target = f"更新到 {self.latest[i]}" if self.latest[i] else "检查更新"
            self._toast(f"正在打开 {app['game']} · {target}")
        else:
            self._toast(f"正在启动 {app['game']} · {app['script']}")

    @staticmethod
    def _shell_launch(exe):
        """通过 ShellExecute 以管理员方式启动（系统会弹出 UAC 确认）。"""
        try:
            ret = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", exe, None, os.path.dirname(exe), 1)
            return int(ret) > 32
        except Exception:
            return False

    def update_app(self, i):
        app = self.apps[i]
        state = self._state_of(i)
        if state == "missing":
            self.choose_path(i)
            return
        if state == "starting":
            return
        if state == "on":
            self._toast(f"{app['game']} 正在运行，请关闭后重新打开以检查更新")
            return
        if self.checking and self.latest[i] is None:
            self._toast("正在检查最新版本，请稍候再点一次")
            return
        if self._has_update(i):
            self.launch(i, mode="update")
        elif self.latest[i] and not self._has_update(i):
            self._toast(f"{app['script']} 已是最新版本 {self.versions[i]}")
        else:
            # 网络检查失败：直接打开脚本，让它自行检查更新
            self._toast(f"无法获取最新版本，打开 {app['game']} 自行检查更新")
            self.launch(i, mode="update")

    def open_link(self, i, kind):
        app = self.apps[i]
        url = app["site"] if kind == "site" else app["github"]
        name = "官网" if kind == "site" else "GitHub"
        try:
            if not webbrowser.open(url):
                os.startfile(url)
            self._toast(f"已在浏览器打开 {app['script']} {name}")
        except Exception:
            try:
                os.startfile(url)
                self._toast(f"已在浏览器打开 {app['script']} {name}")
            except Exception:
                self._toast(f"打开 {app['script']} {name} 失败：{url}")

    def open_folder(self, i):
        app = self.apps[i]
        folder = os.path.dirname(app["exe"])
        if not os.path.isdir(folder):
            self._toast(f"目录不存在：{folder}")
            return
        subprocess.Popen(["explorer", folder])
        self._toast(f"已打开 {app['script']} 所在文件夹")

    def open_clash(self):
        path = self.clash_exe
        if not path or not os.path.exists(path):
            self.clash_exe = self._resolve_clash()
            path = self.clash_exe
        if not path or not os.path.exists(path):
            self._toast("未找到 Clash Verge，可在 config.json 里配置 clash 路径")
            return
        if snapshot_processes() & CLASH_PROCS:
            if bring_to_front(CLASH_PROCS):
                self._toast("已切换到 Clash Verge")
            else:
                self._toast("Clash Verge 已在运行（可能最小化在托盘）")
            return
        try:
            subprocess.Popen([path], cwd=os.path.dirname(path), close_fds=True,
                             creationflags=0x00000008 | 0x00000200)
            self._toast("正在打开 Clash Verge")
        except OSError as exc:
            code = getattr(exc, "winerror", None) or exc.errno
            if code == 740 and self._shell_launch(path):
                self._toast("正在以管理员身份打开 Clash Verge")
            else:
                self._toast(f"打开 Clash Verge 失败：{exc.strerror or exc}")

    def choose_path(self, i):
        from tkinter import filedialog
        app = self.apps[i]
        path = filedialog.askopenfilename(
            title=f"请选择 {app['script']} 的启动程序",
            initialdir=os.path.dirname(app["exe"]) if os.path.isdir(
                os.path.dirname(app["exe"])) else self.search_root,
            filetypes=[("可执行程序", "*.exe"), ("所有文件", "*.*")])
        if not path:
            return
        app["exe"] = os.path.normpath(path)
        self._save_config()
        self.states[i] = "off"
        self._update_versions()
        self._refresh()
        self._toast(f"已更新 {app['script']} 的路径")

    def _toast(self, text):
        self.canvas.itemconfigure(self.foot_text, text=text)
        if self.toast_after:
            try:
                self.root.after_cancel(self.toast_after)
            except Exception:
                pass
        self.toast_after = self.root.after(6000, lambda: self.canvas.itemconfigure(
            self.foot_text, text="就绪 · 每 1.5 秒刷新状态"))

    # ---------------------------------------------------------- 轮询
    def _poll(self):
        try:
            self._drain_update_queue()
            self._refresh()
        except Exception:
            pass
        self.root.after(1500, self._poll)


def main():
    # 单实例：已有窗口在运行时，把它提到最前即可
    mutex = kernel32.CreateMutexW(None, False, "Local\\GameHubLite_SingleInstance")
    if mutex and ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        focus_hub_window()
        return
    root = tk.Tk()
    GameHub(root)
    try:
        root.mainloop()
    finally:
        if mutex:
            kernel32.CloseHandle(mutex)


if __name__ == "__main__":
    main()
