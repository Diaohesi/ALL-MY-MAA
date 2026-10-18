# -*- coding: utf-8 -*-
"""数据与系统能力：应用清单、配置读写、路径识别、版本、更新检查、进程操作。"""
import ctypes
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from ctypes import wintypes

try:
    import winreg
except ImportError:   # 非 Windows 环境（仅做语法检查时）静默降级
    winreg = None

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

# 内置游戏的「游戏本体」进程名（v4 迁移时替换旧的启动器进程名误配）
BUILTIN_GAME_PROCS = {
    "maa": ["ARKNIGHTS.EXE"],
    "nte": ["HTGAME.EXE"],
    "wuwa": ["CLIENT-WIN64-SHIPPING.EXE"],
    "maaend": ["ENDFIELD.EXE"],
}

# v0.5 内置卡片把「启动器」误当成游戏本体的旧默认值；
# v4 迁移只替换这些值，用户手动配置的其它进程名（如 MUMUPLAYER.EXE）保留。
LEGACY_GAME_PROCS = {"NTELAUNCHER.EXE", "LAUNCHER.EXE"}

# 内置「一键清日常」默认设置（可被 config.json 的 app.daily 覆盖）：
#   task       ok-ww 的 -t 任务名（类名最稳，默认 DailyTask）
#   instance   MXU 实例名（MaaNTE/MaaEnd）
#   config     MAA 可选 --config 配置名
#   close_after 完成后是否结束脚本（ok-ww -e / 由 Hub 关闭启动的 MAA）
BUILTIN_DAILY = {
    "maa": {"enabled": True, "task": "", "instance": "", "config": "",
            "timeout_min": 120, "extra_args": [], "close_after": False},
    "nte": {"enabled": True, "task": "", "instance": "", "config": "",
            "timeout_min": 120, "extra_args": [], "close_after": True},
    "wuwa": {"enabled": True, "task": "DailyTask", "instance": "", "config": "",
             "timeout_min": 90, "extra_args": [], "close_after": True},
    "maaend": {"enabled": True, "task": "", "instance": "", "config": "",
               "timeout_min": 150, "extra_args": [], "close_after": True},
}
DEFAULT_DAILY_ORDER = ["maa", "nte", "wuwa", "maaend"]

# v0.8 顶层 settings（config.json 可选字段）；加载时缺省补默认、非法值清洗
DEFAULT_SETTINGS = {
    "accent": "#4fc3ff",
    "check_update_on_start": True,
    "refresh_interval": 1.5,
    "close_action": "exit",
    "clash_exe": "",
    "daily_default_timeout": 120,
    "daily_show_preview": True,
    "adb_enabled": False,
    "daily_close_after": True,
}
REFRESH_INTERVALS = (1.0, 1.5, 2.0)
_ACCENT_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
ACCENT_PRESETS = ("#4fc3ff", "#b98bff", "#5ee7c7", "#ffe066",
                  "#ff8f7a", "#ff8fc7", "#9ae66e", "#8fb8ff")

# ------------------------------------------------------------------ 通用小工具
def version_key(text):
    """取版本号里的数字段；忽略 -rc / +build 等后缀，避免预发布号被当正式版。"""
    if not text:
        return ()
    text = re.split(r"[-+]", str(text), maxsplit=1)[0]
    nums = re.findall(r"\d+", text)
    return tuple(int(x) for x in nums[:4])


def is_newer(latest, current):
    a, b = version_key(latest), version_key(current)
    if not a or not b:
        return False
    length = max(len(a), len(b))
    a = a + (0,) * (length - len(a))     # 零补齐：v6.19 == v6.19.0
    b = b + (0,) * (length - len(b))
    return a > b


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


# ------------------------------------------------------------------ 游戏启动程序自动检测
# 每款游戏的关键词：匹配注册表名称 / 安装路径 / 可执行文件名
GAME_KEYWORDS = {
    "maa": ("明日方舟", "arknights", "mumu", "mumuplayer", "mumunx", "mumu模拟器"),
    "nte": ("异环", "neverness", "neverness to everness", "perfect world",
            "perfectworld", "完美世界", "nte"),
    "wuwa": ("鸣潮", "wuthering", "wuthering waves", "kuro", "库洛"),
    "maaend": ("终末地", "endfield", "arknights: endfield", "明日方舟终末地"),
}

# 常见启动程序名（按优先级排列，越靠前越像游戏入口）
GAME_EXE_HINTS = {
    "maa": ("mumunxmain.exe", "mumuplayer.exe", "mumunxlauncher.exe", "mumu.exe",
            "arknights.exe", "mumuplayer64.exe", "mumumanager.exe", "launcher.exe"),
    "nte": ("ntelauncher.exe", "ntegame.exe", "nte.exe", "htgame.exe"),
    "wuwa": ("wuthering waves.exe", "launcher.exe", "client-win64-shipping.exe",
             "wutheringwaves.exe"),
    "maaend": ("endfield.exe", "launcher.exe", "endfield launcher.exe"),
}

# 厂商 / 启动器关键词：注册表里常只写「鹰角启动器」这类厂商启动器
GAME_VENDOR_HINTS = ("hypergryph", "鹰角", "netease", "网易", "kuro", "库洛",
                     "perfect world", "perfectworld", "完美世界", "yostar", "悠星",
                     "mumu", "bilibili")

# 明显不是游戏入口的 exe 关键词（卸载、更新、崩溃上报、辅助组件等）
GAME_EXE_NOISE = ("unins", "uninstall", "setup", "install", "updater", "update",
                  "repair", "crash", "report", "diagnos", "vcredist", "redist",
                  "dotnet", "eula", "config", "setting", "helper", "service", "sdk",
                  "platformprocess", "webengine", "cefview", "benchmark", "watchdog",
                  "cleaner", "deeplink")

# 自定义游戏名称里过于宽泛、不适合当扫描关键词的词
_GAME_NAME_STOP = {"game", "games", "游戏", "launcher", "启动器", "脚本",
                   "客户端", "client", "center", "中心"}

# 扫描安装目录时跳过的子目录（缓存、日志、SDK、反作弊安装包等）
GAME_SCAN_SKIP = {
    "cache", "caches", "log", "logs", "temp", "tmp", "crashsightlog", "crashreport",
    "redistributables", "redist", "thirdparty", "third_party", "drivers", "driver",
    "docs", "documentation", "sdk", "patchersdk", "pxcrashsdk", "resources", "resource",
    "localization", "i18n", "locales", "plugins", "config", "configs", "userdata",
    "save", "saved", "screenshots", "benchmark", "node_modules", "site-packages",
    "__pycache__", "windows", "winsxs", "$recycle.bin", "system volume information",
}

_REG_UNINSTALL = (
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_LOCAL_MACHINE,
     r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
) if winreg else ()

# 自动检测总预算（秒）：保证界面不会卡太久
GAME_DETECT_BUDGET = 1.8


def _kw_hit(text, keyword):
    """关键词命中；短英文缩写按单词边界匹配，避免 nte 命中 center。"""
    if not text or not keyword:
        return False
    text, keyword = text.lower(), keyword.lower()
    if keyword.isascii() and keyword.isalpha() and len(keyword) <= 4:
        return re.search(r"(?<![a-z0-9])" + re.escape(keyword) + r"(?![a-z0-9])",
                         text) is not None
    return keyword in text


def _kw_hits(text, keywords):
    if not text:
        return 0
    return sum(1 for keyword in keywords if _kw_hit(text, keyword))


def _normalize_name(text):
    """游戏名归一化：去空白/中英文标点，用于精确匹配（如「明日方舟：终末地」）。"""
    return re.sub(r"[\s:：·\-_—/|()（）]+", "", str(text or "").lower())


def _game_profile(app):
    """返回 (key, 关键词, 启动程序名提示)；app 为空时返回全部游戏的合集。

    按游戏名反查时采用「精确/最长关键词优先」，避免较短的「明日方舟」
    抢先命中「明日方舟终末地」（QA-11）。
    """
    app = app or {}
    key = str(app.get("key") or "")
    if key in GAME_KEYWORDS:
        return key, GAME_KEYWORDS[key], GAME_EXE_HINTS.get(key, ())
    game = str(app.get("game") or "").strip()
    if game:
        low = _normalize_name(game)
        best_key, best_score = "", 0
        for name, keywords in GAME_KEYWORDS.items():
            for keyword in keywords:
                keyword = str(keyword)
                if not keyword:
                    continue
                score = 0
                if low and low == _normalize_name(keyword):
                    score = 1000 + len(_normalize_name(keyword))   # 完整名称精确命中
                elif _kw_hit(game, keyword):
                    score = len(keyword)                            # 包含命中，越长越优先
                if score > best_score:
                    best_key, best_score = name, score
        if best_key:
            return best_key, GAME_KEYWORDS[best_key], \
                GAME_EXE_HINTS.get(best_key, ())
        tokens = [token for token in re.split(r"[\s·:：,，/|()（）]+", game)
                  if len(token) >= 2 and token.lower() not in _GAME_NAME_STOP]
        if not tokens:
            return "", (), ()      # 名称太宽泛（如「游戏」），不适合做扫描关键词
        return "", tuple(tokens), ()
    keywords, hints = [], []
    for name, words in GAME_KEYWORDS.items():
        keywords.extend(words)
        hints.extend(GAME_EXE_HINTS.get(name, ()))
    return "", tuple(dict.fromkeys(keywords)), tuple(dict.fromkeys(hints))


def _exe_name_ok(name):
    low = name.lower()
    return low.endswith(".exe") and not any(mark in low for mark in GAME_EXE_NOISE)


def _score_exe_path(path, depth, keywords, hints):
    """给一个 exe 打分；不像游戏启动程序时返回 None。"""
    name = os.path.basename(path)
    if not _exe_name_ok(name):
        return None
    low = name.lower()
    hint_rank = hints.index(low) if low in hints else -1
    name_hits = _kw_hits(low, keywords)
    path_hits = _kw_hits(path, keywords)
    if not name_hits and not path_hits:
        return None          # 文件名和路径里都没有游戏关键词，不是它的启动程序
    if hint_rank < 0 and (not name_hits or depth > 0):
        return None          # 没命中常见启动程序名时，只认安装根目录里的 exe
    if hint_rank >= 0:
        score = 55 if hint_rank == 0 else (
            42 if hint_rank == 1 else max(24, 42 - 5 * hint_rank))
        score += 8 * name_hits + 10 * path_hits
    else:
        score = 20 + 14 * name_hits + 10 * path_hits
    if "launcher" in low or "启动器" in low:
        score += 6
    score += (8, 5, 3)[depth] if depth < 3 else 0
    try:
        if os.path.getsize(path) < 120 * 1024:   # 过小的通常是辅助程序
            score -= 18
    except OSError:
        pass
    if score < 22:
        return None
    return dict(path=path, score=score)


def _find_game_exes(root, keywords, hints, deadline, max_depth=4, max_dirs=300):
    """在目录内浅层扫描 exe，返回 [{path, score}]。"""
    hits = []
    root = os.path.abspath(root) if root else ""
    if not root or not os.path.isdir(root):
        return hits
    stack = [(root, 0)]
    scanned = 0
    while stack:
        if scanned >= max_dirs or time.monotonic() > deadline:
            break
        folder, depth = stack.pop()
        scanned += 1
        try:
            with os.scandir(folder) as iterator:
                entries = list(iterator)
        except OSError:
            continue
        for entry in entries:
            if time.monotonic() > deadline:
                return hits
            try:
                low = entry.name.lower()
                if entry.is_dir(follow_symlinks=False):
                    if depth < max_depth and low not in GAME_SCAN_SKIP \
                            and not low.startswith("."):
                        stack.append((entry.path, depth + 1))
                elif low.endswith(".exe"):
                    item = _score_exe_path(entry.path, depth, keywords, hints)
                    if item:
                        hits.append(item)
            except OSError:
                continue
    return hits


def _reg_value(key, name):
    try:
        value = winreg.QueryValueEx(key, name)[0]
        return str(value).strip() if value is not None else ""
    except OSError:
        return ""


def _clean_icon_path(value):
    """把 DisplayIcon 规范成 exe 路径；不是 exe 时返回空串。"""
    value = str(value or "").strip()
    if not value:
        return ""
    # 常见形式："C:\x\game.exe",0  /  C:\x\game.exe,0  /  C:\x\game.exe
    value = value.strip('"').strip()
    if re.search(r",\s*-?\d+\s*$", value):
        value = re.sub(r",\s*-?\d+\s*$", "", value).strip().strip('"')
    if len(value) > 3 and value[1] == ":" and value.lower().endswith(".exe"):
        return value
    return ""


def _iter_registry_entries(keywords, deadline):
    """枚举卸载项，返回名称/路径命中关键词的 [{name, install, icon}]。"""
    entries, seen = [], set()
    if not _REG_UNINSTALL:
        return entries
    views = (0,)
    if hasattr(winreg, "KEY_WOW64_64KEY"):
        views = (0, winreg.KEY_WOW64_64KEY)
    for hive, subkey in _REG_UNINSTALL:
        for view in views:
            if time.monotonic() > deadline:
                return entries
            try:
                parent = winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ | view)
            except OSError:
                continue
            try:
                count = winreg.QueryInfoKey(parent)[0]
                for index in range(count):
                    if time.monotonic() > deadline:
                        break
                    try:
                        name = winreg.EnumKey(parent, index)
                        with winreg.OpenKey(parent, name) as item:
                            display = _reg_value(item, "DisplayName")
                            if not display:
                                continue
                            install = _reg_value(item, "InstallLocation").strip('"')
                            icon = _reg_value(item, "DisplayIcon")
                            publisher = _reg_value(item, "Publisher")
                    except OSError:
                        continue
                    if not _kw_hits(" ".join((display, install, icon, publisher, name)),
                                    keywords):
                        continue
                    signature = (display.lower(), install.lower(), icon.lower())
                    if signature in seen:
                        continue
                    seen.add(signature)
                    entries.append(dict(name=display, install=install, icon=icon))
            finally:
                try:
                    parent.Close()
                except Exception:
                    pass
    return entries


def _child_dirs(path):
    try:
        with os.scandir(path) as iterator:
            return [entry for entry in iterator if entry.is_dir(follow_symlinks=False)]
    except OSError:
        return []


def _drive_roots():
    try:
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        roots = []
        for index in range(26):
            if mask & (1 << index):
                root = f"{chr(65 + index)}:\\"
                if os.path.isdir(root):
                    roots.append(root)
        return roots
    except Exception:
        return [f"{letter}:\\" for letter in "CDEFGH" if os.path.isdir(f"{letter}:\\")]


def _fs_scan_roots(keywords, deadline):
    """常见安装目录：Program Files、LOCALAPPDATA\\Programs、各盘根目录/Games 等。"""
    roots, seen = [], set()
    all_hints = tuple(keywords) + GAME_VENDOR_HINTS

    def add(path, name):
        try:
            norm = os.path.normpath(path).lower()
        except (TypeError, ValueError):
            return
        if norm in seen or not os.path.isdir(path):
            return
        seen.add(norm)
        roots.append((path, name))

    def matched(name):
        return _kw_hits(name, all_hints) > 0

    program_bases = []
    for variable in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        path = os.environ.get(variable)
        if path and os.path.isdir(path) and path not in program_bases:
            program_bases.append(path)
    local = os.environ.get("LOCALAPPDATA") or ""
    if local:
        program_bases.append(os.path.join(local, "Programs"))
    for base in program_bases:
        if time.monotonic() > deadline:
            return roots
        for entry in _child_dirs(base):
            if time.monotonic() > deadline:
                return roots
            if matched(entry.name):
                add(entry.path, entry.name)

    game_folders = {"games", "game", "游戏", "my games", "游戏库"}
    for drive in _drive_roots():
        if time.monotonic() > deadline:
            return roots
        for entry in _child_dirs(drive):
            if time.monotonic() > deadline:
                return roots
            low = entry.name.lower()
            if matched(entry.name):
                add(entry.path, entry.name)
            elif low in game_folders:
                add(entry.path, entry.name)   # 统一扫描 Games/游戏 这类目录
    return roots


def _candidate_name(exe_path, hint):
    base = os.path.basename(exe_path)
    hint = (hint or "").strip()
    if hint and hint.lower() != base.lower():
        return f"{hint} · {base}"
    return base


def find_game_candidates(app=None, limit=12):
    """自动检测游戏启动程序候选。

    返回按 score 降序排列的 list[dict(path, name, source, score)]；
    source 为「注册表」或「常见目录」，全程异常静默、总耗时约 < 2 秒。
    """
    started = time.monotonic()
    deadline = started + GAME_DETECT_BUDGET
    try:
        _, keywords, hints = _game_profile(app)
    except Exception:
        keywords, hints = (), ()
    registry_words = tuple(keywords) + GAME_VENDOR_HINTS
    found, scanned = {}, set()

    def merge(path, name, source, score):
        if not path or not os.path.isfile(path):
            return
        try:
            norm = os.path.normpath(path).lower()
        except (TypeError, ValueError):
            return
        candidate = dict(path=os.path.normpath(path), name=name, source=source,
                         score=int(score))
        old = found.get(norm)
        if old is None or candidate["score"] > old["score"]:
            found[norm] = candidate

    def scan(root, hint, source, base_score):
        if not root:
            return
        try:
            norm = os.path.normpath(root).lower()
        except (TypeError, ValueError):
            return
        if norm in scanned:
            return
        scanned.add(norm)
        bonus = min(24, 12 * _kw_hits(hint or "", keywords))
        try:
            hits = _find_game_exes(root, keywords, hints, deadline)
        except Exception:
            hits = []
        for hit in hits:
            merge(hit["path"], _candidate_name(hit["path"], hint), source,
                  base_score + hit["score"] + bonus)

    # 1) 注册表卸载项
    try:
        entries = _iter_registry_entries(registry_words, deadline)
    except Exception:
        entries = []
    for entry in entries:
        if time.monotonic() > deadline:
            break
        display = entry.get("name") or ""
        install = entry.get("install") or ""
        icon_exe = _clean_icon_path(entry.get("icon"))
        if icon_exe:
            hit = _score_exe_path(icon_exe, 0, keywords, hints)
            if hit:
                merge(icon_exe, _candidate_name(icon_exe, display), "注册表",
                      40 + hit["score"] + min(24, 12 * _kw_hits(display, keywords)))
        root = install if os.path.isdir(install) else (
            os.path.dirname(icon_exe) if icon_exe else "")
        scan(root, display, "注册表", 40)

    # 2) 常见安装目录
    try:
        fs_roots = _fs_scan_roots(registry_words, deadline)
    except Exception:
        fs_roots = []
    for root, root_name in fs_roots:
        if time.monotonic() > deadline:
            break
        scan(root, root_name, "常见目录", 15)

    result = sorted(found.values(), key=lambda item: (-item["score"],
                                                      item["path"].lower()))
    try:
        return result[:max(1, int(limit))]
    except (TypeError, ValueError):
        return result[:12]


def _version_text(value):
    """把 JSON 版本值安全转成字符串；非 str/int/float（含 bool/null/list）返回空串。"""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return ""
    return str(value).strip()


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
                v = _version_text((json.load(f).get("stable") or {}).get("version"))
            if v:
                return v if v.startswith("v") else "v" + v
        elif app.get("key") in ("nte", "maaend"):
            with open(os.path.join(folder, "interface.json"), "r", encoding="utf-8") as f:
                v = _version_text(json.load(f).get("version"))
            if v:
                return v if v.startswith("v") else "v" + v
        elif app.get("key") == "wuwa":
            with open(os.path.join(folder, "data", "apps", "ok-ww", "app.json"),
                      "r", encoding="utf-8") as f:
                v = _version_text(json.load(f).get("current_version"))
            if v:
                return v
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
        if not isinstance(item, str):   # 跳过 None / 数字 / 嵌套值，避免出现 "NONE"
            continue
        item = item.strip()
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


# ------------------------------------------------------------------ 检测规则（config v4）
_DETECT_TYPE_ALIASES = {"win": "win", "window": "win", "proc": "proc",
                        "process": "proc", "adb": "adb"}


def _is_legacy_game_proc(name):
    """旧配置里的进程名是否属于 v0.5 常见的「启动器冒充游戏」误配。"""
    text = str(name or "").strip().upper()
    if not text:
        return False
    return text in LEGACY_GAME_PROCS or \
        os.path.basename(text).upper() in LEGACY_GAME_PROCS


def _detect_text(value):
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _detect_texts(value):
    """通用文本列表（历史兼容，保留给旧调用/测试）。"""
    if isinstance(value, str):
        value = re.split(r"[,，;；\s]+", value)
    if not isinstance(value, (list, tuple)):
        return []
    items = [_detect_text(item) for item in value]
    return [item for item in items if item]


def _detect_names(value):
    """进程名/包名列表：字符串只按逗号/分号/换行拆分。

    单个值即使含空格也整体保留（如手写 config 的 "Wuthering Waves.exe"），
    不再按空白拆成多个进程名（QA-12）；UI/save_state 写的数组路径不受影响。
    """
    if isinstance(value, str):
        parts = re.split(r"[,，;；\n]+", value)
        return [part.strip() for part in parts if part.strip()]
    if isinstance(value, (list, tuple)):
        return [item.strip() for item in value
                if isinstance(item, str) and item.strip()]
    return []


def _clean_detect_rule(rule):
    """规整单条检测规则；非法/无内容返回 None。"""
    if not isinstance(rule, dict):
        return None
    kind = _DETECT_TYPE_ALIASES.get(str(rule.get("type") or "").strip().lower(), "")
    if not kind:
        return None
    out = {"type": kind}
    if kind == "win":
        for field in ("class_re", "title_re", "proc_path_re"):
            text = _detect_text(rule.get(field))
            if text:
                out[field] = text
        if not out.get("class_re") and not out.get("title_re"):
            return None
        if rule.get("title_optional"):
            out["title_optional"] = True
        if rule.get("match") in ("any", "all"):
            out["match"] = rule["match"]
        if rule.get("require_visible"):
            out["require_visible"] = True
        size = rule.get("min_client_size")
        if (isinstance(size, (list, tuple)) and len(size) == 2
                and all(isinstance(v, (int, float)) for v in size)):
            out["min_client_size"] = [int(size[0]), int(size[1])]
        names = _detect_names(rule.get("proc_names"))
        if names:
            out["proc_names"] = names
    elif kind == "proc":
        names = _detect_names(rule.get("names"))
        if not names:
            return None
        out["names"] = names
        path_re = _detect_text(rule.get("path_re"))
        if path_re:
            out["path_re"] = path_re
    elif kind == "adb":
        pkgs = _detect_names(rule.get("pkg"))
        if not pkgs:
            return None
        out["pkg"] = pkgs
        for field in ("activity", "serial_re"):
            text = _detect_text(rule.get(field))
            if text:
                out[field] = text
    else:
        return None
    return out


def _clean_proc_class_check(value):
    if not isinstance(value, dict):
        return None
    name = _detect_text(value.get("name"))
    class_re = _detect_text(value.get("win_class_re"))
    if not name or not class_re:
        return None
    out = {"name": name, "win_class_re": class_re}
    path_re = _detect_text(value.get("path_re"))
    if path_re:
        out["path_re"] = path_re
    return out


def _clean_detect_group(value):
    if not isinstance(value, dict):
        return None
    rules = [_clean_detect_rule(rule) for rule in (value.get("any_of") or [])]
    rules = [rule for rule in rules if rule]
    checks = value.get("proc_class_check")
    if isinstance(checks, dict):
        checks = [checks]
    checks = [_clean_proc_class_check(item) for item in checks] \
        if isinstance(checks, (list, tuple)) else []
    checks = [item for item in checks if item]
    result = {}
    if rules:
        result["any_of"] = rules
    if checks:
        result["proc_class_check"] = checks
    return result or None


def _clean_detect(value):
    """规整 app 的检测规则（any_of / proc_class_check / launcher / cloud）。"""
    if not isinstance(value, dict):
        return None
    result = _clean_detect_group(value) or {}
    for field in ("launcher", "cloud"):
        group = _clean_detect_group(value.get(field))
        if group:
            result[field] = group
    return result or None


# ------------------------------------------------------------------ 清日常配置（v4 可选字段）
_GENERIC_DAILY = {"enabled": False, "task": "", "instance": "", "config": "",
                  "timeout_min": 120, "extra_args": [], "close_after": False}


def _clean_daily(value, key="", default_timeout=None):
    """规整某个 app 的清日常设置（缺省补内置默认值）。

    default_timeout：设置页的「清日常默认超时」，仅用于用户写过 daily 但未写
    timeout_min 的条目（不覆盖各游戏内置默认值）。
    """
    base = dict(_GENERIC_DAILY)
    if key in BUILTIN_DAILY:
        base.update(BUILTIN_DAILY[key])
        base["extra_args"] = []
    if isinstance(default_timeout, (int, float)) and not isinstance(default_timeout, bool):
        base["timeout_min"] = max(1, min(600, int(default_timeout)))
    if not isinstance(value, dict):
        return base
    out = dict(base)
    if isinstance(value.get("enabled"), bool):
        out["enabled"] = value["enabled"]
    for field in ("task", "instance", "config"):
        if isinstance(value.get(field), str):
            out[field] = value[field].strip()
    timeout = value.get("timeout_min")
    if isinstance(timeout, (int, float)) and not isinstance(timeout, bool):
        out["timeout_min"] = max(1, min(600, int(timeout)))
    args = value.get("extra_args")
    if isinstance(args, str):
        try:
            import shlex
            args = shlex.split(args, posix=True)
        except Exception:
            args = []
    if isinstance(args, (list, tuple)):
        # QA-13：只接受字符串，strip 后丢弃 None/数字/空串，绝不转成 "None"/"3"
        cleaned = []
        for item in args:
            if not isinstance(item, str):
                continue
            item = item.strip()
            if item:
                cleaned.append(item)
        out["extra_args"] = cleaned
    if isinstance(value.get("close_after"), bool):
        out["close_after"] = value["close_after"]
    return out


def _clean_daily_order(value, keys):
    """规整队列顺序：只保留存在的 app key，去重并补齐缺失项。"""
    keys = [str(key) for key in (keys or [])]
    order = []
    if isinstance(value, (list, tuple)):
        for item in value:
            key = str(item).strip()
            if key in keys and key not in order:
                order.append(key)
    for key in keys:
        if key not in order:
            order.append(key)
    return order


def _clean_settings(value):
    """v0.8 顶层 settings 清洗：缺省补默认，非法值回退默认。"""
    out = dict(DEFAULT_SETTINGS)
    out["clash_exe"] = ""
    if not isinstance(value, dict):
        return out
    accent = value.get("accent")
    if isinstance(accent, str) and _ACCENT_RE.match(accent.strip()):
        out["accent"] = accent.strip().lower()
    for field in ("check_update_on_start", "daily_show_preview",
                  "adb_enabled", "daily_close_after"):
        if isinstance(value.get(field), bool):
            out[field] = value[field]
    interval = value.get("refresh_interval")
    if isinstance(interval, (int, float)) and not isinstance(interval, bool):
        interval = float(interval)
        if interval in [float(item) for item in REFRESH_INTERVALS]:
            out["refresh_interval"] = interval
    action = str(value.get("close_action") or "").strip().lower()
    if action in ("exit", "minimize"):
        out["close_action"] = action
    clash = value.get("clash_exe")
    if isinstance(clash, str):
        out["clash_exe"] = clash.strip()
    timeout = value.get("daily_default_timeout")
    if isinstance(timeout, (int, float)) and not isinstance(timeout, bool):
        out["daily_default_timeout"] = max(1, min(600, int(timeout)))
    return out


def load_state_full():
    """读取 config.json，返回 (apps, clash_exe, root, meta)。

    meta 目前包含：daily_order（一键清日常顺序）。保留 load_state() 三元组
    包装以兼容既有调用方（QA 回归/test 工具）。
    """
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
    settings = _clean_settings(data.get("settings"))

    apps = []
    saved_apps = data.get("apps") if isinstance(data.get("apps"), dict) else {}
    saved_launch_specs = {}
    for base in DEFAULT_APPS:
        app = make_builtin(base["key"], root)
        saved = saved_apps.get(base["key"], {}) if isinstance(saved_apps, dict) else {}
        if isinstance(saved, str):     # 兼容 v1/v2 的纯路径格式
            saved = {"script_exe": saved}
        saved_daily = saved.get("daily") if isinstance(saved, dict) else None
        default_timeout = None
        if isinstance(saved_daily, dict) and "timeout_min" not in saved_daily:
            default_timeout = settings["daily_default_timeout"]
        if isinstance(saved, dict):
            saved_launch_specs[base["key"]] = saved.get("launch")
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
            detect = _clean_detect(saved.get("detect"))
            if detect:
                app["detect"] = detect          # 用户自定义检测规则优先
                app["detect_custom"] = True
            app["daily"] = _clean_daily(saved_daily, base["key"],
                                        default_timeout=default_timeout)
            app["daily_explicit"] = isinstance(saved_daily, dict)
            for field in ("site", "github", "release", "download", "accent"):
                if saved.get(field):
                    app[field] = saved[field]
            icon = saved.get("icon") or ""
            if icon:
                if not os.path.isabs(icon):
                    icon = os.path.join(APP_DIR, icon)
                if os.path.exists(icon):
                    app["icon_path"] = icon
        if "daily" not in app:
            app["daily"] = _clean_daily(None, base["key"])
            app["daily_explicit"] = False
        apps.append(app)

    # 内置应用：路径没找到时自动扫描
    for app in apps:
        if not os.path.isfile(app.get("script_exe", "")):
            hits = find_app_exe(root, app.get("script_exe_name", ""))
            best = pick_best_exe(hits)
            if best:
                app["script_exe"] = best

    # v4 迁移：只纠正「空值 / 全部是旧启动器误配」的内置 game_procs。
    # 用户手动配置的其它进程名（如 MAA 模拟器用户填的 MUMUPLAYER.EXE）必须保留，
    # 不能一刀切覆盖；自定义了检测规则的卡片本来就不迁移。
    for app in apps:
        defaults = BUILTIN_GAME_PROCS.get(app.get("key", ""))
        if not defaults or app.get("detect_custom"):
            continue
        current = [str(name).strip() for name in (app.get("game_procs") or [])
                   if str(name).strip()]
        if not current or all(_is_legacy_game_proc(name) for name in current):
            app["game_procs"] = list(defaults)

    # v0.7 启动规格：内置鸣潮改为「bundled pythonw + working\main.py」直接跑正式脚本
    # （ok-ww.exe 只是 PyAppify 启动器/更新器）；旧配置没有 launch 时自动补齐，
    # 保存后持久化到 config.json，便于其它应用复用同一结构。
    for app in apps:
        saved_launch = _clean_launch(saved_launch_specs.get(app.get("key", "")), root)
        if app.get("key") == "wuwa":
            app["launch"] = _merge_launch_spec(saved_launch, build_okww_launch(app))
        elif saved_launch:
            app["launch"] = saved_launch

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
            detect = _clean_detect(item.get("detect"))
            if detect:
                app["detect"] = detect          # 自定义游戏的检测规则
                app["detect_custom"] = True
            launch = _clean_launch(item.get("launch"), root)
            if launch:
                app["launch"] = launch          # 自定义游戏也可复用启动规格
            saved_custom_daily = item.get("daily")
            custom_default = None
            if isinstance(saved_custom_daily, dict) \
                    and "timeout_min" not in saved_custom_daily:
                custom_default = settings["daily_default_timeout"]
            app["daily"] = _clean_daily(saved_custom_daily, app["key"],
                                        default_timeout=custom_default)
            app["daily_explicit"] = isinstance(saved_custom_daily, dict)
            apps.append(app)

    # QA-15：settings.clash_exe 与顶层 clash 一样按 root 还原相对路径，
    # 顶层 clash 仍优先；settings 路径不存在时保留原值并回退自动查找。
    raw_clash = data.get("clash") or ""
    top_clash = _absolute(raw_clash, root) if raw_clash else None
    raw_settings_clash = settings.get("clash_exe") or ""
    settings_clash = _absolute(raw_settings_clash, root) \
        if raw_settings_clash else None
    if settings_clash:
        settings["clash_exe"] = settings_clash
    elif raw_settings_clash:
        settings["clash_exe"] = raw_settings_clash
    if top_clash:
        clash = top_clash
    elif settings_clash:
        clash = settings_clash
    else:
        clash = next((p for p in CLASH_CANDIDATES if p and os.path.exists(p)), "")
    builtin_keys = [app["key"] for app in apps if app.get("builtin")]
    meta = {"daily_order": _clean_daily_order(data.get("daily_order"),
                                              builtin_keys),
            "settings": settings}
    return apps, clash, root, meta


def load_state():
    """兼容包装：返回 (apps, clash_exe, root)。"""
    apps, clash, root, _meta = load_state_full()
    return apps, clash, root


def save_state(apps, clash, root, daily_order=None, settings=None):
    """写入 config.json（v4），返回是否成功（失败由调用方负责提示用户）。"""
    data = {"version": 4, "apps": {}, "custom_apps": []}
    if os.path.normpath(root) != os.path.normpath(SEARCH_ROOT):
        data["root"] = root
    if clash:
        data["clash"] = clash
    cleaned_settings = _clean_settings(settings)
    cleaned_settings["clash_exe"] = (_portable(clash, root) if clash else "")
    data["settings"] = cleaned_settings
    builtin_keys = [app["key"] for app in apps if app.get("builtin")]
    if daily_order is None:
        daily_order = DEFAULT_DAILY_ORDER
    data["daily_order"] = _clean_daily_order(daily_order, builtin_keys)
    for app in apps:
        entry = {
            "script_exe": _portable(app.get("script_exe", ""), root),
            "game_exe": _portable(app.get("game_exe", ""), root) if app.get("game_exe") else "",
            "script_procs": list(app.get("script_procs") or []),
            "game_procs": list(app.get("game_procs") or []),
            "daily": _clean_daily(app.get("daily"), app.get("key", "")),
        }
        icon = app.get("icon_path", "")
        if icon:
            entry["icon"] = _portable(icon, APP_DIR)
        if app.get("detect") and (app.get("detect_custom") or not app.get("builtin")):
            cleaned = _clean_detect(app["detect"])
            if cleaned:
                entry["detect"] = cleaned
                entry["detect_custom"] = True
        launch = _portable_launch(app.get("launch"), root)
        if launch:
            entry["launch"] = launch
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
        return True
    except Exception:
        return False


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
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                wintypes.LPWSTR,
                                                ctypes.POINTER(wintypes.DWORD)]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
user32.GetAncestor.restype = wintypes.HWND

TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE = ctypes.c_void_p(-1).value
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def process_path(pid):
    """取进程完整 exe 路径（QueryFullProcessImageNameW）；失败返回空串。"""
    if not pid:
        return ""
    handle = None
    try:
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False,
                                      int(pid))
        if not handle:
            return ""
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value or ""
    except Exception:
        pass
    finally:
        if handle:
            try:
                kernel32.CloseHandle(handle)
            except Exception:
                pass
    return ""


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


def bring_pids_to_front(pids):
    """把指定进程集合的可见窗口切到前台（用于正式脚本/多窗口场景）。"""
    pids = set(pids or ())
    if not pids:
        return False
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


def bring_to_front(procs):
    if not (snapshot_processes() & set(procs)):
        return False
    return bring_pids_to_front(pids_for_procs(set(procs)))


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


# ------------------------------------------------------------------ 启动规格（launch spec）
# 有些脚本的「启动器 exe」其实只是 PyAppify 更新器，真正脚本是 bundled python 进程。
# 这里用可复用的 launch spec 描述启动方式，并持久化到 config.json：
#   {"type":"python","exe":...pythonw.exe,"script":...main.py,"cwd":working,
#    "env":{...},"clear_env":[...],"launcher_exe":ok-ww.exe,
#    "process_exe_names":[...],"process_exe_dirs":[...],"fallback":"launcher"}
LAUNCH_ENV_CLEAR = ("PYTHONHOME", "PYTHONSTARTUP", "VIRTUAL_ENV", "PYTHONPATH",
                    "PYTHONUSERBASE", "PYTHONCASEOK", "PYTHONHASHSEED",
                    "PYTHONOPTIMIZE", "PYTHONVERBOSE", "PYTHONDEBUG",
                    "PYTHONWARNINGS", "PYTHONIOENCODING", "PYTHONINSPECT",
                    "PYAPPIFY_PID")
LAUNCH_ENV_SET = {"PYTHONNOUSERSITE": "1", "PYTHONIOENCODING": "utf-8",
                  "PYTHONUNBUFFERED": "1"}
OKWW_APP_SUBDIR = ("data", "apps", "ok-ww")
_LAUNCH_PATH_FIELDS = ("exe", "script", "cwd", "launcher_exe")


def _wrapper_path():
    """PyAppify 包装器使用的系统默认 PATH。"""
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    return os.pathsep.join((
        os.path.join(system_root, "system32"),
        system_root,
        os.path.join(system_root, "System32", "Wbem"),
        os.path.join(system_root, "System32", "WindowsPowerShell", "v1.0"),
        os.path.join(system_root, "System32", "OpenSSH"),
    ))


def _launch_text(value):
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _launch_list(value):
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _resolve_launch_path(value, root):
    text = _launch_text(value)
    if not text:
        return ""
    if os.path.isabs(text):
        return os.path.normpath(text)
    return os.path.normpath(os.path.join(root, text))


def _clean_launch(value, root=None):
    """规整持久化的启动规格；非法/无内容返回 None。"""
    if not isinstance(value, dict):
        return None
    root = root or SEARCH_ROOT
    kind = (_launch_text(value.get("type")) or "python").lower()
    spec = {"type": kind}
    for field in _LAUNCH_PATH_FIELDS:
        path = _resolve_launch_path(value.get(field), root)
        if path:
            spec[field] = path
    dirs = [_resolve_launch_path(item, root)
            for item in _launch_list(value.get("process_exe_dirs"))]
    dirs = [item for item in dirs if item]
    if dirs:
        spec["process_exe_dirs"] = dirs
    names = _launch_list(value.get("process_exe_names"))
    if names:
        spec["process_exe_names"] = names
    args = _launch_list(value.get("args"))
    if args:
        spec["args"] = args
    clear = _launch_list(value.get("clear_env"))
    if clear:
        spec["clear_env"] = clear
    env = value.get("env")
    if isinstance(env, dict):
        cleaned = {}
        for key, item in env.items():
            key = str(key).strip()
            if key and isinstance(item, (str, int, float)) \
                    and not isinstance(item, bool):
                cleaned[key] = str(item)
        if cleaned:
            spec["env"] = cleaned
    fallback = _launch_text(value.get("fallback")).lower()
    if fallback:
        spec["fallback"] = fallback
    if not spec.get("exe") and not spec.get("launcher_exe"):
        return None
    if spec.get("exe") and kind == "python" and not spec.get("script"):
        return None
    return spec


def _portable_launch(value, root):
    """把启动规格里的路径转成相对 root 的便携格式（写 config 用）。"""
    spec = _clean_launch(value, root)
    if not spec:
        return None
    out = dict(spec)
    for field in _LAUNCH_PATH_FIELDS:
        if out.get(field):
            out[field] = _portable(out[field], root)
    if out.get("process_exe_dirs"):
        out["process_exe_dirs"] = [_portable(item, root)
                                   for item in out["process_exe_dirs"]]
    return out


def build_okww_launch(app):
    """从内置鸣潮卡片的 ok-ww 安装目录推导「直接运行正式脚本」的启动规格。

    目录布局：<ok-ww>\\data\\apps\\ok-ww\\python\\pythonw.exe + working\\main.py。
    布局缺失时仍返回规格（launch_app 会回退启动器）。
    """
    app = app or {}
    launcher = _launch_text(app.get("script_exe"))
    install_dir = os.path.dirname(launcher)
    if not install_dir:
        return None
    app_dir = os.path.join(install_dir, *OKWW_APP_SUBDIR)
    python_dir = os.path.join(app_dir, "python")
    working = os.path.join(app_dir, "working")
    spec = {
        "type": "python",
        "exe": os.path.join(python_dir, "pythonw.exe"),
        "script": os.path.join(working, "main.py"),
        "cwd": working,
        "launcher_exe": launcher,
        "clear_env": list(LAUNCH_ENV_CLEAR),
        "env": dict(LAUNCH_ENV_SET),
        "process_exe_names": ["pythonw.exe", "python.exe"],
        "process_exe_dirs": [python_dir],
        "fallback": "launcher",
    }
    app_json = os.path.join(app_dir, "app.json")
    metadata = {}
    try:
        with open(app_json, "r", encoding="utf-8-sig") as fh:
            metadata = json.load(fh) or {}
    except Exception:
        metadata = {}
    if isinstance(metadata, dict):
        version = metadata.get("current_version")
        if isinstance(version, str) and version.strip():
            spec["env"]["PYAPPIFY_APP_VERSION"] = version.strip()
        profile = metadata.get("current_profile")
        if isinstance(profile, str) and profile.strip():
            spec["env"]["PYAPPIFY_APP_PROFILE"] = profile.strip()
    if os.path.isfile(app_json):
        spec["env"]["PYAPPIFY_APP_JSON_PATH"] = app_json
    if os.path.isfile(launcher):
        spec["env"]["PYAPPIFY_EXECUTABLE"] = launcher
    return spec


def _merge_launch_spec(saved, auto):
    """已持久化的规格可用时优先，否则回退到自动推导；补全启动器/目录字段。"""
    if not saved:
        return auto
    spec = dict(auto or {})
    spec.update(saved)
    if auto:
        # 环境变量：保留用户自定义项，但 PYAPPIFY_* 等元数据以本次自动读取的
        # app.json 为准（ok-ww 更新后版本号会变，避免持久化旧版本号）。
        env = dict(saved.get("env") or {})
        env.update(auto.get("env") or {})
        if env:
            spec["env"] = env
        for field in ("clear_env", "process_exe_names", "process_exe_dirs",
                      "fallback"):
            if not spec.get(field) and auto.get(field):
                spec[field] = auto[field]
        launcher = auto.get("launcher_exe") or ""
        if launcher and not os.path.isfile(spec.get("launcher_exe") or ""):
            spec["launcher_exe"] = launcher
        for field in ("exe", "script", "cwd"):
            expected = auto.get(field) or ""
            current = spec.get(field) or ""
            exists = os.path.isdir(current) if field == "cwd" \
                else os.path.isfile(current)
            if expected and not exists:
                spec[field] = expected
    return spec


def refresh_launch_spec(app):
    """脚本路径变化后重新推导启动规格（内置鸣潮）；返回是否有规格。"""
    if not isinstance(app, dict):
        return False
    if str(app.get("key") or "") == "wuwa":
        spec = build_okww_launch(app)
        if spec:
            app["launch"] = spec
        return bool(spec)
    return isinstance(app.get("launch"), dict)


def _launch_env(spec):
    env = dict(os.environ)
    for name in spec.get("clear_env") or LAUNCH_ENV_CLEAR:
        env.pop(str(name), None)
    env["PATH"] = _wrapper_path()
    for key, value in (spec.get("env") or {}).items():
        env[str(key)] = str(value)
    return env


def launch_app(app):
    """按启动规格启动卡片脚本，返回 (ok, error, mode)。

    mode: "script"=正式脚本（bundled python）、"launcher"=回退启动器、
    "exe"=普通 exe（MAA/MaaNTE/MaaEnd 等）。
    """
    app = app or {}
    spec = app.get("launch") if isinstance(app.get("launch"), dict) else None
    if spec and spec.get("exe"):
        exe = spec.get("exe") or ""
        script = spec.get("script") or ""
        command = [exe]
        if script:
            command.append(script)
        command.extend(str(arg) for arg in (spec.get("args") or []))
        cwd = spec.get("cwd") or os.path.dirname(exe)
        error = ""
        if os.path.isfile(exe) and (not script or os.path.isfile(script)):
            try:
                subprocess.Popen(
                    command, cwd=cwd if os.path.isdir(cwd) else None,
                    env=_launch_env(spec), close_fds=True,
                    creationflags=0x00000008 | 0x00000200)
                return True, "", "script"
            except OSError as exc:
                code = getattr(exc, "winerror", None) or exc.errno
                error = "需要管理员权限" if code == 740 else str(exc)
        else:
            error = "正式脚本目录不完整"
        launcher = spec.get("launcher_exe") or app.get("script_exe", "")
        if spec.get("fallback") != "none" and launcher and os.path.isfile(launcher):
            ok, fallback_error = launch_exe(launcher)
            if ok:
                return True, "", "launcher"
            return False, fallback_error or error, "launcher"
        return False, error or "正式脚本与启动器都不存在", "none"
    ok, error = launch_exe(app.get("script_exe", ""))
    return ok, error, "exe"


def launch_updater(app):
    """「更新」仍走启动器 exe（ok-ww.exe），保留其更新能力。"""
    app = app or {}
    spec = app.get("launch") if isinstance(app.get("launch"), dict) else {}
    launcher = spec.get("launcher_exe") or app.get("script_exe", "")
    if launcher and os.path.isfile(launcher):
        return launch_exe(launcher)
    return False, "更新器不存在"


def launch_running_pids(app):
    """返回启动规格对应的正式脚本进程 PID（按 exe 完整路径判定）。

    不能用进程名判断：ok-ww 正式脚本是 bundled pythonw，和用户其它 python 同名；
    启动器 ok-ww.exe 不算脚本运行中。
    """
    app = app or {}
    spec = app.get("launch")
    if not isinstance(spec, dict):
        return set()
    names = _launch_list(spec.get("process_exe_names"))
    if not names and spec.get("exe"):
        names = [os.path.basename(spec["exe"])]
    if not names:
        return set()
    dirs = [os.path.normpath(str(item)).lower()
            for item in (spec.get("process_exe_dirs") or []) if str(item).strip()]
    if not dirs and spec.get("exe"):
        dirs = [os.path.normpath(os.path.dirname(spec["exe"])).lower()]
    if not dirs:
        return set()
    matched = set()
    for pid in pids_for_procs({name.upper() for name in names}):
        path = process_path(pid)
        if not path:
            continue
        lower = os.path.normpath(path).lower()
        if any(lower == item or lower.startswith(item + os.sep) for item in dirs):
            matched.add(pid)
    return matched


def launch_spec_running(app):
    return bool(launch_running_pids(app))


def focus_launch_spec(app):
    """把正式脚本进程的窗口切到前台（ok-ww 的窗口属于 bundled pythonw）。"""
    pids = launch_running_pids(app)
    if not pids:
        return False
    return bring_pids_to_front(pids)
