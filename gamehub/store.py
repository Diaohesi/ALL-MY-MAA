# -*- coding: utf-8 -*-
"""数据与系统能力：应用清单、配置读写、路径识别、版本、更新检查、进程操作。"""
import ctypes
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from ctypes import wintypes

# ------------------------------------------------------------------ 路径
FROZEN = bool(getattr(sys, "frozen", False))
if FROZEN:
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
    ASSETS = os.path.join(getattr(sys, "_MEIPASS", APP_DIR), "assets")
else:
    APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ASSETS = os.path.join(APP_DIR, "assets")
BASE_DIR = os.path.dirname(APP_DIR)
CONFIG = os.path.join(APP_DIR, "config.json")
SEARCH_ROOT = BASE_DIR

CURL = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "curl.exe")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GameHub"}
CLASH_PROCS = {"CLASH-VERGE.EXE"}
CLASH_CANDIDATES = [
    r"C:\Program Files\Clash Verge\clash-verge.exe",
    r"C:\Program Files (x86)\Clash Verge\clash-verge.exe",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Clash Verge",
                 "clash-verge.exe"),
]

SEARCH_SKIP = {
    "cache", "config", "data", "resource", "resources", "resource_adb",
    "resource_cloud_adb", "resource_linux", "resource_macos", "resource_playcover",
    "python", "lib", "site-packages", "ebwebview", "repo", "debug", "agent",
    "thirdparty", "maafw", "__pycache__", "logs", "locales", "tasks", ".git",
    ".old", "achievement", "externals", "res", "working", "docs", "dist", "build",
    "gamehub", "tools", ".venv", "venv",
}

# ------------------------------------------------------------------ 默认应用
DEFAULT_APPS = [
    dict(key="maa", game="明日方舟", script="MAA", builtin=True,
         script_exe_name="MAA.exe", default_dir="MAA-v5.1.0-win-x64",
         script_procs=["MAA.EXE"], game_exe="", game_procs=[],
         accent="#4fc3ff", fallback_version="v6.19.0",
         site="https://maa.plus/",
         github="https://github.com/MaaAssistantArknights/MaaAssistantArknights",
         release="https://github.com/MaaAssistantArknights/MaaAssistantArknights/releases/latest",
         download="https://ak.hypergryph.com/"),
    dict(key="nte", game="异环", script="MaaNTE", builtin=True,
         script_exe_name="MaaNTE.exe", default_dir="MaaNTE",
         script_procs=["MAANTE.EXE"], game_exe="", game_procs=[],
         accent="#b98bff", fallback_version="v1.6.0",
         site="https://maante.org/",
         github="https://github.com/1bananachicken/MaaNTE",
         release="https://github.com/1bananachicken/MaaNTE/releases/latest",
         download="https://yh.wanmei.com/"),
    dict(key="wuwa", game="鸣潮", script="ok-ww", builtin=True,
         script_exe_name="ok-ww.exe", default_dir="WuwaMAA/ok-ww",
         script_procs=["OK-WW.EXE"], game_exe="", game_procs=[],
         accent="#5ee7c7", fallback_version="v3.7.4",
         site="https://ok-script.com/ok-ww",
         github="https://github.com/ok-oldking/ok-wuthering-waves",
         release="https://github.com/ok-oldking/ok-wuthering-waves/releases/latest",
         download="https://mc.kurogames.com/"),
    dict(key="maaend", game="明日方舟终末地", script="MaaEnd", builtin=True,
         script_exe_name="MaaEnd.exe", default_dir="MaaEnd-win-x86_64-v2.33.0",
         script_procs=["MAAEND.EXE"], game_exe="", game_procs=[],
         accent="#ffe066", fallback_version="v2.33.0",
         site="https://maaend.com/",
         github="https://github.com/MaaEnd/MaaEnd",
         release="https://github.com/MaaEnd/MaaEnd/releases/latest",
         download="https://endfield.hypergryph.com/"),
]

ICON_FILES = {"maa": "maa.png", "nte": "nte.png", "wuwa": "wuwa.png",
              "maaend": "maaend.png"}

# ------------------------------------------------------------------ 通用小工具
def version_key(text):
    nums = re.findall(r"\d+", text or "")
    return tuple(int(x) for x in nums[:4])


def is_newer(latest, current):
    a, b = version_key(latest), version_key(current)
    return bool(a and b and a > b)


def http_get(url, timeout=10):
    """优先系统 curl.exe（代理兼容更好），失败退回 urllib。"""
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
    match = re.search(r"/releases/tag/([^/?#]+)", final_url(url, timeout))
    return urllib.parse.unquote(match.group(1)) if match else None


# ------------------------------------------------------------------ exe 版本
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


def find_app_exe(root, exe_name, max_depth=4):
    root = os.path.abspath(root) if root else ""
    hits = []
    if not root or not os.path.isdir(root):
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
    def score(path):
        folder = os.path.basename(os.path.dirname(path))
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = 0
        return (version_key(folder), mtime)
    return max(paths, key=score) if paths else None


def proc_names_for_exe(exe_path):
    if exe_path:
        return [os.path.basename(exe_path).upper()]
    return []


def read_version(app):
    exe = app.get("script_exe", "")
    folder = os.path.dirname(exe)
    try:
        if app.get("key") == "maa":
            v = file_version(exe)
            if v:
                return "v" + v
            cache = os.path.join(folder, "cache", "version", "summary.json")
            with open(cache, "r", encoding="utf-8") as f:
                v = (json.load(f).get("stable") or {}).get("version", "")
            if v:
                return v if v.startswith("v") else "v" + v
        elif app.get("key") in ("nte", "maaend"):
            with open(os.path.join(folder, "interface.json"), "r", encoding="utf-8") as f:
                v = str(json.load(f).get("version", ""))
            if v:
                return v if v.startswith("v") else "v" + v
        elif app.get("key") == "wuwa":
            with open(os.path.join(folder, "data", "apps", "ok-ww", "app.json"),
                      "r", encoding="utf-8") as f:
                return json.load(f).get("current_version", "") or ""
        else:
            v = file_version(exe)
            if v:
                return "v" + v
    except Exception:
        pass
    return app.get("fallback_version", "")


def check_latest(app):
    if app.get("key") == "maa":
        try:
            body = http_get(
                "https://api.maa.plus/MaaAssistantArknights/api/version/stable.json", 8)
            version = json.loads(body.decode("utf-8", "ignore")).get("version")
            if version:
                return version
        except Exception:
            pass
    release = app.get("release") or ""
    if not release:
        return None
    try:
        return github_latest_tag(release, timeout=10)
    except Exception:
        return None


# ------------------------------------------------------------------ 配置
def _portable(path, root):
    try:
        rel = os.path.relpath(path, root)
        if not rel.startswith(".."):
            return rel.replace("\\", "/")
    except ValueError:
        pass
    return path


def _absolute(value, root):
    if not value:
        return None
    candidates = [value] if os.path.isabs(value) else []
    candidates.append(os.path.normpath(os.path.join(root, value)))
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def _clean_procs(value, fallback_exe=""):
    if isinstance(value, str):
        items = re.split(r"[,，;；\s]+", value)
    elif isinstance(value, (list, tuple)):
        items = list(value)
    else:
        items = []
    procs = []
    for item in items:
        item = str(item).strip()
        if item:
            procs.append(item.upper())
    if not procs and fallback_exe:
        procs = proc_names_for_exe(fallback_exe)
    return procs


def custom_icon_path(key):
    """自定义游戏没有专属图标时，用内置占位图标。"""
    candidate = os.path.join(ASSETS, "custom.png")
    if os.path.exists(candidate):
        return candidate
    return os.path.join(ASSETS, "maa.png")


def make_builtin(key, root):
    for base in DEFAULT_APPS:
        if base["key"] != key:
            continue
        app = dict(base)
        app["script_exe"] = os.path.join(root, bp(base.get("default_dir", "")),
                                        app["script_exe_name"])
        app["icon_path"] = os.path.join(ASSETS, ICON_FILES.get(key, "maa.png"))
        app["script_procs"] = list(app["script_procs"])
        app["game_procs"] = list(app.get("game_procs") or [])
        return app
    return None


def bp(path):
    return path.replace("/", os.sep)


def load_state():
    """读取 config.json，返回 (apps, clash_exe, root)。"""
    data = {}
    if os.path.exists(CONFIG):
        try:
            with open(CONFIG, "r", encoding="utf-8-sig") as f:
                data = json.load(f) or {}
        except Exception:
            data = {}

    root = data.get("root") or ""
    if not root or not os.path.isdir(root):
        root = SEARCH_ROOT
    root = os.path.abspath(root)

    apps = []
    saved_apps = data.get("apps") if isinstance(data.get("apps"), dict) else {}
    for base in DEFAULT_APPS:
        app = make_builtin(base["key"], root)
        saved = saved_apps.get(base["key"], {}) if isinstance(saved_apps, dict) else {}
        if isinstance(saved, str):     # 兼容 v1/v2 的纯路径格式
            saved = {"script_exe": saved}
        if isinstance(saved, dict):
            exe = _absolute(saved.get("script_exe"), root)
            if exe:
                app["script_exe"] = exe
            game_exe = _absolute(saved.get("game_exe"), root)
            if game_exe:
                app["game_exe"] = game_exe
            if saved.get("script_procs"):
                app["script_procs"] = _clean_procs(saved.get("script_procs"))
            if saved.get("game_procs"):
                app["game_procs"] = _clean_procs(saved.get("game_procs"))
            for field in ("site", "github", "release", "download", "accent"):
                if saved.get(field):
                    app[field] = saved[field]
            icon = saved.get("icon") or ""
            if icon:
                if not os.path.isabs(icon):
                    icon = os.path.join(APP_DIR, icon)
                if os.path.exists(icon):
                    app["icon_path"] = icon
        apps.append(app)

    # 内置应用：路径没找到时自动扫描
    for app in apps:
        if not os.path.isfile(app.get("script_exe", "")):
            hits = find_app_exe(root, app.get("script_exe_name", ""))
            best = pick_best_exe(hits)
            if best:
                app["script_exe"] = best

    custom = data.get("custom_apps") or []
    if isinstance(custom, list):
        for i, item in enumerate(custom):
            if not isinstance(item, dict):
                continue
            exe = _absolute(item.get("script_exe"), root) or item.get("script_exe", "")
            if not exe:
                continue
            game_exe = _absolute(item.get("game_exe"), root) or item.get("game_exe", "")
            icon = item.get("icon") or ""
            if icon and not os.path.isabs(icon):
                icon = os.path.join(APP_DIR, icon)
            if not icon or not os.path.exists(icon):
                icon = custom_icon_path(item.get("key"))
            app = dict(
                key=item.get("key") or f"custom_{i + 1}",
                game=item.get("game") or "未命名游戏",
                script=item.get("script") or "脚本",
                builtin=False,
                script_exe=exe,
                script_procs=_clean_procs(item.get("script_procs"), exe),
                game_exe=game_exe or "",
                game_procs=_clean_procs(item.get("game_procs"), game_exe),
                accent=item.get("accent") or "#4fc3ff",
                fallback_version=item.get("fallback_version") or "",
                site=item.get("site") or "",
                github=item.get("github") or "",
                release=item.get("release") or "",
                download=item.get("download") or "",
                icon_path=icon,
            )
            apps.append(app)

    clash = data.get("clash") or ""
    if not clash or not os.path.exists(clash):
        clash = next((p for p in CLASH_CANDIDATES if p and os.path.exists(p)), "")
    return apps, clash, root


def save_state(apps, clash, root):
    data = {"version": 3, "apps": {}, "custom_apps": []}
    if os.path.normpath(root) != os.path.normpath(SEARCH_ROOT):
        data["root"] = root
    if clash:
        data["clash"] = clash
    for app in apps:
        entry = {
            "script_exe": _portable(app.get("script_exe", ""), root),
            "game_exe": _portable(app.get("game_exe", ""), root) if app.get("game_exe") else "",
            "script_procs": list(app.get("script_procs") or []),
            "game_procs": list(app.get("game_procs") or []),
        }
        icon = app.get("icon_path", "")
        if icon:
            entry["icon"] = _portable(icon, APP_DIR)
        if app.get("builtin"):
            for field in ("site", "github", "release", "download", "accent"):
                if app.get(field):
                    entry[field] = app[field]
            data["apps"][app["key"]] = entry
        else:
            custom = {
                "key": app["key"],
                "game": app["game"],
                "script": app["script"],
                "accent": app.get("accent", "#4fc3ff"),
                "fallback_version": app.get("fallback_version", ""),
                "icon": _portable(app.get("icon_path", ""), APP_DIR)
                if app.get("icon_path") else "",
            }
            custom.update(entry)
            for field in ("site", "github", "release", "download"):
                custom[field] = app.get(field, "")
            data["custom_apps"].append(custom)
    try:
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ------------------------------------------------------------------ 进程
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
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
    names = set()
    try:
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
    except Exception:
        pass
    return names


def pids_for_procs(procs):
    pids = set()
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == INVALID_HANDLE:
        return pids
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
    return pids


def bring_to_front(procs):
    if not (snapshot_processes() & set(procs)):
        return False
    pids = pids_for_procs(set(procs))
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
    for hwnd in found:
        try:
            user32.ShowWindow(hwnd, 9)
            user32.SetForegroundWindow(hwnd)
            user32.SwitchToThisWindow(hwnd, True)
            return True
        except Exception:
            continue
    return False


def shell_launch(exe, verb="runas"):
    try:
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, verb, exe, None, os.path.dirname(exe), 1)
        return int(ret) > 32
    except Exception:
        return False


def launch_exe(exe):
    """启动 exe；需要管理员权限时使用 ShellExecute 提权。返回 (ok, 错误信息)。"""
    if not exe or not os.path.exists(exe):
        return False, "文件不存在"
    try:
        subprocess.Popen([exe], cwd=os.path.dirname(exe), close_fds=True,
                         creationflags=0x00000008 | 0x00000200)
        return True, ""
    except OSError as exc:
        code = getattr(exc, "winerror", None) or exc.errno
        if code == 740:
            if shell_launch(exe):
                return True, ""
            return False, "需要管理员权限"
        return False, str(exc)


def open_path(folder):
    if folder and os.path.isdir(folder):
        subprocess.Popen(["explorer", folder])
        return True
    return False


def find_hub_window(title):
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _lparam):
        cls = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, cls, 64)
        if cls.value != "TkTopLevel":
            return True
        text = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, text, 256)
        if text.value == title:
            found.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


def focus_window(title):
    hwnd = find_hub_window(title)
    if not hwnd:
        return False
    try:
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        user32.SwitchToThisWindow(hwnd, True)
        return True
    except Exception:
        return False
