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
    dict(key="oknte", game="异环", script="ok-nte", builtin=True,
         script_exe_name="ok-nte.exe", default_dir="ok-nte",
         script_procs=["OK-NTE.EXE"], game_exe="", game_procs=[],
         accent="#b98bff", fallback_version="v1.4.15",
         site="https://ok-script.com/ok-nte",
         github="https://github.com/BnanZ0/ok-nte",
         release="https://github.com/BnanZ0/ok-nte/releases/latest",
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

ICON_FILES = {"maa": "maa.png", "nte": "nte.png", "oknte": "nte.png", "wuwa": "wuwa.png",
              "maaend": "maaend.png"}

# 内置游戏的「游戏本体」进程名（v4 迁移时替换旧的启动器进程名误配）
BUILTIN_GAME_PROCS = {
    "maa": ["ARKNIGHTS.EXE"],
    "nte": ["HTGAME.EXE"],
    "oknte": ["HTGAME.EXE"],
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
    "oknte": {"enabled": False, "task": "DailyRoutineTask", "instance": "", "config": "",
              "timeout_min": 120, "extra_args": [], "close_after": True},
    "wuwa": {"enabled": True, "task": "DailyTask", "instance": "", "config": "",
             "timeout_min": 90, "extra_args": [], "close_after": True},
    "maaend": {"enabled": True, "task": "", "instance": "", "config": "",
               "timeout_min": 150, "extra_args": [], "close_after": True},
}
DEFAULT_DAILY_ORDER = ["maa", "nte", "oknte", "wuwa", "maaend"]

# v0.8 顶层 settings（config.json 可选字段）；加载时缺省补默认、非法值清洗
DEFAULT_SETTINGS = {
    "accent": "#4fc3ff",
    "font_scale": 1.0,
    "auto_download_update": False,
    "check_update_on_start": True,
    "refresh_interval": 1.5,
    "close_action": "exit",
    "minimize_to_tray": True,
    "clash_exe": "",
    "daily_default_timeout": 120,
    "daily_show_preview": True,
    "adb_enabled": False,
    "daily_close_after": True,
}
REFRESH_INTERVALS = (1.0, 1.5, 2.0)
FONT_SCALES = (0.9, 1.0, 1.12, 1.25)
# v0.10 无 accent 的新默认（保留旧 DEFAULT 供旧测试/渲染兼容；load 时 UI 侧启用）
NEW_DEFAULT_ACCENT = "#b98bff"
_ACCENT_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
ACCENT_PRESETS = ("#b98bff", "#c4a7f5", "#a78bfa", "#5ee7c7",
                  "#ffe066", "#ff8f7a", "#ff8fc7", "#8fb8ff")

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
        # Product prefixes such as MAA-v5.1.0 contain a hyphen that the
        # generic version parser correctly treats as a prerelease delimiter.
        # Extract the actual version before applying that parser.
        match = re.search(r"(?i)(?:^|[-_ ])v?(\d+(?:\.\d+)+)", folder)
        return (version_key(match.group(1) if match else folder), mtime)
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
    # 异环（v0.10.1）：默认回到 NTELauncher.exe（直启 HTGame 会 UE 报错）
    "nte": ("ntelauncher.exe", "ntegame.exe", "nte.exe", "htgame.exe"),
    "wuwa": ("wuthering waves.exe", "launcher.exe", "client-win64-shipping.exe",
             "wutheringwaves.exe"),
    "maaend": ("endfield.exe", "launcher.exe", "endfield launcher.exe"),
}

# 异环游戏本体（v0.10）：从启动器所在安装根优先寻找该相对路径
NTE_GAME_EXE = "HTGame.exe"
NTE_LAUNCHER_EXE = "NTELauncher.exe"
NTE_GAME_RELATIVE = ("Client", "WindowsNoEditor", "HT", "Binaries",
                     "Win64", "HTGame.exe")

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
    if key == "oknte":
        key = "nte"     # Same game/launcher; never infer a direct HTGame launch.
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
    if low == NTE_LAUNCHER_EXE.lower():
        score += 18          # 异环默认走启动器
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
    scanned_roots = []

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
        scanned_roots.append(root)
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
    # v0.10.1：异环默认优先 NTELauncher.exe（HTGame 仅保留为候选）
    try:
        profile_key = _game_profile(app)[0]
    except Exception:
        profile_key = ""
    if profile_key == "nte":
        for root in scanned_roots:
            launcher = os.path.join(root, NTE_LAUNCHER_EXE)
            if os.path.isfile(launcher):
                merge(launcher, _candidate_name(launcher, "异环启动器"),
                      "异环启动器", 200)
        result = sorted(found.values(), key=lambda item: (
            -item["score"], item["path"].lower()))
        for item in result:
            if os.path.basename(item["path"]).lower() == \
                    NTE_LAUNCHER_EXE.lower():
                item["score"] += 100
        result.sort(key=lambda item: (-item["score"], item["path"].lower()))
    try:
        return result[:max(1, int(limit))]
    except (TypeError, ValueError):
        return result[:12]


def _apply_resolved_game_exe(app, path):
    """把解析到的游戏本体写回 app（game_exe + game_procs）。"""
    norm = os.path.normpath(path)
    app["game_exe"] = norm
    try:
        app["game_procs"] = proc_names_for_exe(norm)
    except Exception:
        pass
    return norm


def resolve_game_exe(app, deadline_seconds=1.9):
    """v0.10.1：异环默认解析 NTELauncher.exe（直启 HTGame 会 UE 报错）。

    - 已是 NTELauncher.exe 直接返回；
    - 若当前是 HTGame.exe，向安装根/脚本目录查找 NTELauncher.exe 并写回；
    - 找不到保留原值，由 UI/调用方提示。
    其它游戏直接返回现有 game_exe。
    """
    if not isinstance(app, dict):
        return ""
    current = str(app.get("game_exe") or "").strip()
    if str(app.get("key") or "") not in ("nte", "oknte"):
        return current
    if current and os.path.isfile(current) \
            and os.path.basename(current).lower() == \
            NTE_LAUNCHER_EXE.lower():
        return _apply_resolved_game_exe(app, current)
    roots = _normalize_roots(app)
    launcher = _find_relative(roots, (NTE_LAUNCHER_EXE,))
    if launcher:
        return _apply_resolved_game_exe(app, launcher)
    if current and os.path.isfile(current):
        return current
    return current


def _migrate_nte_game_exe(apps):
    """v0.10.1：HTGame.exe 错误配置改回同安装根 NTELauncher.exe 并保存。"""
    for app in apps or []:
        if app.get("key") != "nte":
            continue
        current = str(app.get("game_exe") or "").strip()
        if not current or os.path.basename(current).lower() != \
                NTE_GAME_EXE.lower():
            continue
        resolved = resolve_game_exe(app)
        if resolved and os.path.basename(resolved).lower() == \
                NTE_LAUNCHER_EXE.lower():
            return True
    return False


GAME_LAUNCH_TIMEOUTS = {
    "wuwa": 120,
    "nte": 180,
    "oknte": 180,
    "maaend": 180,
    "maa": 120,
}


def _read_json_file(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            return json.load(fh)
    except Exception:
        return None


def _json_first_value(data, key, max_depth=8):
    """在嵌套 JSON 中找第一个 key 对应的标量/对象（tolerant，用于 MAA 配置）。"""
    if max_depth < 0:
        return None
    if isinstance(data, dict):
        if key in data:
            return data.get(key)
        for value in data.values():
            found = _json_first_value(value, key, max_depth - 1)
            if found is not None:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _json_first_value(item, key, max_depth - 1)
            if found is not None:
                return found
    return None


def _normalize_roots(app):
    roots = []
    for path in (app.get("game_exe"), app.get("script_exe")):
        if not path:
            continue
        try:
            root = os.path.dirname(os.path.abspath(path))
        except (TypeError, ValueError):
            continue
        for _ in range(8):
            if root and root not in roots:
                roots.append(root)
            parent = os.path.dirname(root)
            if not parent or parent == root:
                break
            root = parent
    return roots


def _first_file(candidates):
    for path in candidates:
        if path and os.path.isfile(path):
            return os.path.normpath(path)
    return ""


def _find_relative(roots, relatives):
    for root in roots:
        for rel in relatives:
            path = os.path.join(root, *rel.split("\\"))
            if os.path.isfile(path):
                return os.path.normpath(path)
    return ""


def _okww_devices_pc_exe(app):
    """ok-ww devices.json 中的 pc_full_path（源码/配置发现路径）。"""
    roots = _normalize_roots(app)
    for root in roots:
        for name in ("devices.json", os.path.join("configs", "devices.json")):
            path = os.path.join(root, name)
            if not os.path.isfile(path):
                continue
            data = _read_json_file(path)
            target = _json_first_value(data, "pc_full_path")
            if isinstance(target, str) and os.path.isfile(target) \
                    and os.path.basename(target).lower().endswith(".exe"):
                return os.path.normpath(target)
    return ""


def _hypergryph_installs():
    """注册表里所有「鹰角启动器」InstallLocation（终末地/明日方舟各一个）。"""
    installs = []
    if not winreg:
        return installs
    try:
        entries = _iter_registry_entries(("鹰角", "hypergryph"), time.monotonic() + 1.5)
    except Exception:
        entries = []
    seen = set()
    for entry in entries:
        install = str(entry.get("install") or "").strip()
        icon = str(entry.get("icon") or "").strip()
        exe = icon or os.path.join(install, "Launcher.exe")
        if not exe or not os.path.isfile(exe):
            continue
        norm = os.path.normpath(exe).lower()
        if norm in seen:
            continue
        seen.add(norm)
        installs.append({"install": install or os.path.dirname(exe),
                         "launcher": os.path.normpath(exe),
                         "name": str(entry.get("name") or "")})
    return installs


def _maa_settings(app):
    """读取 MAA gui.new.json/gui.json 的启动相关键（容错）。"""
    roots = _normalize_roots(app)
    data = None
    for root in roots:
        for name in ("gui.new.json", "gui.json",
                     os.path.join("config", "gui.new.json"),
                     os.path.join("config", "gui.json")):
            path = os.path.join(root, name)
            if os.path.isfile(path):
                data = _read_json_file(path)
                if data is not None:
                    break
        if data is not None:
            break
    settings = {"pc_path": "", "pc_add": "", "pc_wait": 60,
                "emu_path": "", "emu_add": "", "emu_wait": 60,
                "adb_path": "", "adb_serial": "", "package": "",
                "mode": "", "config": ""}

    def truthy(value):
        return value is True or (isinstance(value, str)
                                 and value.strip().lower() in ("true", "pc"))

    if isinstance(data, dict):
        pc = _json_first_value(data, "PcClientPath")
        emu = _json_first_value(data, "EmulatorPath")
        pc_add = _json_first_value(data, "PcClientAddCommand")
        emu_add = _json_first_value(data, "EmulatorAddCommand")
        pc_wait = _json_first_value(data, "PcClientWaitSeconds")
        emu_wait = _json_first_value(data, "EmulatorWaitSeconds")
        adb_path = _json_first_value(data, "AdbPath")
        adb_serial = _json_first_value(data, "AdbSerial") or \
            _json_first_value(data, "Serial")
        package = _json_first_value(data, "PackageName")
        connect = _json_first_value(data, "ConnectConfig")
        is_pc = _json_first_value(data, "IsPCConnectConfig")
        settings.update({
            "pc_path": str(pc or "").strip(),
            "pc_add": str(pc_add or "").strip(),
            "pc_wait": int(pc_wait) if isinstance(pc_wait, (int, float)) else 60,
            "emu_path": str(emu or "").strip(),
            "emu_add": str(emu_add or "").strip(),
            "emu_wait": int(emu_wait) if isinstance(emu_wait, (int, float)) else 60,
            "adb_path": str(adb_path or "").strip(),
            "adb_serial": str(adb_serial or "").strip(),
            "package": str(package or "").strip(),
            "config": str(connect or "").strip(),
            "mode": "pc" if (truthy(is_pc) or truthy(connect)) else "emulator",
        })
    return settings


def _maa_launch_spec(app):
    settings = _maa_settings(app)
    roots = _normalize_roots(app)
    pc_exe = settings["pc_path"]
    if not (pc_exe and os.path.isfile(pc_exe)):
        pc_exe = _find_relative(roots, (
            r"games\Arknights Game\Arknights.exe",
            r"Arknights Game\Arknights.exe",
        ))
    if not pc_exe:
        for install in _hypergryph_installs():
            candidate = os.path.join(install["install"],
                                     "games", "Arknights Game",
                                     "Arknights.exe")
            if os.path.isfile(candidate):
                pc_exe = os.path.normpath(candidate)
                break
    if not pc_exe:
        current = str(app.get("game_exe") or "")
        if os.path.isfile(current) and os.path.basename(current).lower() \
                == "arknights.exe":
            pc_exe = os.path.normpath(current)
    launcher = _find_relative(roots, (r"Launcher.exe",))
    if not launcher:
        for install in _hypergryph_installs():
            if "arknights" in (install["install"] + install["name"]).lower() \
                    or "明日方舟" in install["name"]:
                launcher = install["launcher"]
                break
    mode = settings["mode"]
    has_emulator = bool(settings["emu_path"] or settings["adb_path"])
    if mode == "pc" or (not settings["config"] and not has_emulator
                        and pc_exe):
        if pc_exe:
            return {
                "strategy": "maa_pc", "exe": pc_exe,
                "args": ([settings["pc_add"]] if settings["pc_add"] else []),
                "cwd": os.path.dirname(pc_exe), "elevated": False,
                "wait": {"timeout_s": max(10, settings["pc_wait"]),
                         "poll_ms": 500,
                         "any_of": [
                             {"type": "win", "class_re": "^UnityWndClass$",
                              "title_re": "明日方舟"},
                             {"type": "proc", "names": ["Arknights.exe"]},
                         ]},
                "fallback": ([{"type": "exe", "exe": launcher,
                               "hint": "已打开鹰角启动器，请点击开始游戏"}]
                             if launcher else []) +
                            [{"type": "user_pick",
                              "reason": "未找到 MAA PC 客户端 Arknights.exe"}],
            }
    emu = settings["emu_path"]
    if not (emu and os.path.isfile(emu)):
        emu = ""
    adb = settings["adb_path"]
    if not (adb and os.path.isfile(adb)):
        adb = ""
    serial = settings["adb_serial"]
    package = settings["package"] or "com.hypergryph.arknights"
    return {
        "strategy": "maa_adb", "exe": emu,
        "args": ([settings["emu_add"]] if settings["emu_add"] else []),
        "cwd": os.path.dirname(emu) if emu else "",
        "elevated": False,
        "adb": {"path": adb, "serial": serial, "package": package},
        "wait": {"timeout_s": max(10, settings["emu_wait"]),
                 "poll_ms": 500,
                 "any_of": [{"type": "adb_pkg", "package": package}]},
        "fallback": ([{"type": "exe", "exe": launcher,
                       "hint": "已打开鹰角启动器，请点击开始游戏"}]
                     if launcher else []) +
                    [{"type": "user_pick",
                      "reason": "未找到模拟器/ADB，请从 MAA 或模拟器手动启动"}],
    }


def build_game_launch(app):
    """v0.10 数据化游戏启动规格（策略/exe/args/cwd/wait/fallback）。"""
    app = app or {}
    key = str(app.get("key") or "")
    roots = _normalize_roots(app)
    current = str(app.get("game_exe") or "")
    timeout = GAME_LAUNCH_TIMEOUTS.get(key, 120)
    if key == "wuwa":
        exe = ""
        if current and os.path.basename(current).lower() \
                == "wuthering waves.exe" and os.path.isfile(current):
            exe = os.path.normpath(current)
        if not exe:
            exe = _okww_devices_pc_exe(app)
        if not exe:
            exe = _find_relative(roots, (
                r"Wuthering Waves Game\Wuthering Waves.exe",
                r"Wuthering Waves.exe",
            ))
        launcher = ""
        if current and os.path.basename(current).lower() == "launcher.exe" \
                and os.path.isfile(current):
            launcher = os.path.normpath(current)
        if not launcher:
            launcher = _find_relative(roots, (r"launcher.exe",))
        exe = exe or launcher
        return {
            "strategy": "exe", "exe": exe,
            "args": ["-krqlv=hd"] if exe else [],
            "cwd": os.path.dirname(exe) if exe else "",
            "elevated": False,
            "wait": {"timeout_s": timeout, "poll_ms": 500,
                     "any_of": [
                         {"type": "win", "class_re": "^UnrealWindow$",
                          "title_re": r"^\s*鸣潮\s*$"},
                         {"type": "proc", "names": ["Client-Win64-Shipping.exe"]},
                     ]},
            "fallback": ([{"type": "exe", "exe": launcher,
                           "hint": "已打开游戏启动器，请点击开始游戏"}]
                         if launcher else []) +
                        [{"type": "user_pick",
                          "reason": "未找到 Wuthering Waves.exe"}],
        }
    if key in ("nte", "oknte"):
        launcher = current if current and os.path.isfile(current) \
            and os.path.basename(current).lower() == "ntelauncher.exe" else ""
        if not launcher:
            launcher = _find_relative(roots, (r"NTELauncher.exe",))
        if not launcher:
            resolved = resolve_game_exe(app)
            launcher = resolved if resolved and os.path.basename(
                resolved).lower() == "ntelauncher.exe" else ""
        return {
            "strategy": "launcher", "exe": launcher, "args": [],
            "cwd": os.path.dirname(launcher) if launcher else "",
            "elevated": False,
            "wait": {"timeout_s": timeout, "poll_ms": 500,
                     "any_of": [
                         {"type": "win", "class_re": "^UnrealWindow$",
                          "title_re": r"^\s*(异环|NTE)\s*$"},
                         {"type": "proc", "names": ["HTGame.exe"]},
                     ]},
            "hint": "请在异环启动器中登录并点击开始游戏",
            "fallback": [{"type": "user_pick",
                          "reason": "未找到 NTELauncher.exe（直启 HTGame 可能 UE 报错）"}],
        }
    if key == "maaend":
        endfield = _find_relative(roots, (
            r"games\Endfield Game\Endfield.exe",
            r"Endfield Game\Endfield.exe",
            r"Endfield.exe",
        ))
        launcher = current if current and os.path.isfile(current) else ""
        install_root = os.path.dirname(launcher) if launcher else ""
        if not endfield:
            for install in _hypergryph_installs():
                candidate = os.path.join(install["install"], "games",
                                         "Endfield Game", "Endfield.exe")
                if os.path.isfile(candidate):
                    endfield = os.path.normpath(candidate)
                    launcher = launcher or install["launcher"]
                    install_root = install["install"]
                    break
        return {
            "strategy": "launcher", "exe": launcher or endfield,
            "args": [], "cwd": install_root or
            (os.path.dirname(launcher) if launcher else ""),
            "elevated": False,
            "wait": {"timeout_s": timeout, "poll_ms": 500,
                     "any_of": [
                         {"type": "win", "class_re": "^UnityWndClass$",
                          "title_re": "Endfield"},
                         {"type": "proc", "names": ["Endfield.exe"]},
                     ]},
            "hint": "请在鹰角启动器中点击「开始游戏」",
            "fallback": ([{"type": "exe", "exe": endfield,
                           "hint": "已尝试直接启动 Endfield（可能白屏），"
                                   "如异常请改用启动器"}]
                         if endfield else []) +
                        [{"type": "user_pick",
                          "reason": "未找到 Endfield 启动器/本体"}],
        }
    if key == "maa":
        return _maa_launch_spec(app)
    # 自定义游戏：保持现有 game_exe 直接启动
    return {
        "strategy": "exe", "exe": current, "args": [],
        "cwd": os.path.dirname(current) if current else "",
        "elevated": False,
        "wait": {"timeout_s": timeout, "poll_ms": 500,
                 "any_of": []},
        "fallback": [{"type": "user_pick", "reason": "未找到游戏启动程序"}],
    }


class _NoProcess:
    """ShellExecute/startfile 启动的进程没有 PID 句柄，用于统一等待接口。"""

    pid = None

    def poll(self):
        return None


def _spawn_game_process(exe, args=None, cwd=""):
    if not exe:
        return None, "未找到游戏启动程序"
    args = [str(item) for item in (args or []) if str(item)]
    try:
        if str(exe).lower().endswith(".lnk"):
            os.startfile(exe)
            return _NoProcess(), ""
        proc = subprocess.Popen(
            [exe] + args, cwd=cwd or os.path.dirname(exe),
            close_fds=True,
            creationflags=0x00000008 | 0x00000200)
        return proc, ""
    except Exception as exc:
        return None, str(exc)


def wait_game_launched(app, spec, *, state_fn=None, sleep_fn=None,
                       clock_fn=None, process=None):
    """复用 detector 轮询等待游戏窗口/进程；返回 (ok, reason)。"""
    import time as _time
    sleep_fn = sleep_fn or _time.sleep
    clock_fn = clock_fn or _time.monotonic
    wait = spec.get("wait") or {}
    timeout = float(wait.get("timeout_s") or GAME_LAUNCH_TIMEOUTS.get(
        app.get("key"), 120))
    poll = max(0.05, float(wait.get("poll_ms") or 500) / 1000.0)
    deadline = clock_fn() + timeout
    if state_fn is None:
        def state_fn():
            from . import detector
            probe = dict(app)
            if spec.get("exe"):
                probe["game_exe"] = spec["exe"]
            try:
                state = detector.detect_game_state(
                    probe, adb_enabled=bool(spec.get("strategy") == "maa_adb"))
                return bool(state.get("running"))
            except Exception:
                return False
    import time as _time
    start = clock_fn()
    while clock_fn() < deadline:
        if state_fn():
            return True, ""
        if process is not None:
            try:
                if process.poll() is not None:
                    return False, "启动进程提前退出"
            except Exception:
                pass
            if clock_fn() - start > 30:
                process = None
        sleep_fn(poll)
    return False, f"等待游戏窗口超时（{int(timeout)}s）"


def launch_game_with_wait(app, spec=None, *, spawn_fn=None, state_fn=None,
                          sleep_fn=None, clock_fn=None):
    """按 game_launch 启动→等待→失败回退；返回结果 dict。"""
    spec = spec or build_game_launch(app)
    if not spec or not spec.get("strategy"):
        return {"ok": False, "reason": "无启动规格", "spec": spec}
    spawn_fn = spawn_fn or _spawn_game_process
    if spec["strategy"] == "maa_adb":
        adb = spec.get("adb") or {}
        adb_path = adb.get("path") or ""
        serial = adb.get("serial") or ""
        package = adb.get("package") or ""
        if adb_path and os.path.isfile(adb_path) and package:
            try:
                args = [adb_path]
                if serial:
                    args += ["-s", serial]
                args += ["shell", "am", "start", "-n",
                         f"{package}/com.u8.sdk.U8UnityContext"]
                subprocess.Popen(args, creationflags=0x08000000)
            except Exception as exc:
                return {"ok": False, "reason": f"ADB 启动失败：{exc}",
                        "spec": spec}
        emu = spec.get("exe") or ""
        proc, error = (None, "")
        if emu:
            proc, error = spawn_fn(emu, spec.get("args"), spec.get("cwd"))
        ok, reason = wait_game_launched(app, spec, state_fn=state_fn,
                                        sleep_fn=sleep_fn,
                                        clock_fn=clock_fn, process=proc)
        if ok:
            return {"ok": True, "spec": spec, "reason": ""}
        fallback = spec.get("fallback") or []
        fallback_spec = fallback[0] if fallback else None
        if fallback_spec and fallback_spec.get("type") == "exe" \
                and fallback_spec.get("exe"):
            spawn_fn(fallback_spec["exe"], [], os.path.dirname(
                fallback_spec["exe"]))
        return {"ok": False, "spec": spec, "reason": reason,
                "fallback": fallback_spec, "error": error}
    proc, error = spawn_fn(spec.get("exe"), spec.get("args"),
                           spec.get("cwd"))
    if proc is None:
        return {"ok": False, "spec": spec, "reason": error or "启动失败"}
    ok, reason = wait_game_launched(app, spec, state_fn=state_fn,
                                    sleep_fn=sleep_fn, clock_fn=clock_fn,
                                    process=proc)
    if ok:
        return {"ok": True, "spec": spec, "reason": "", "pid": getattr(
            proc, "pid", None)}
    fallback = spec.get("fallback") or []
    fallback_spec = fallback[0] if fallback else None
    if fallback_spec and fallback_spec.get("type") == "exe" \
            and fallback_spec.get("exe"):
        spawn_fn(fallback_spec["exe"], [], os.path.dirname(
            fallback_spec["exe"]))
    return {"ok": False, "spec": spec, "reason": reason,
            "fallback": fallback_spec, "pid": getattr(proc, "pid", None)}



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
        elif app.get("key") in PYAPPIFY_APPS:
            with open(os.path.join(folder, "data", "apps", PYAPPIFY_APPS[app["key"]], "app.json"),
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


# ------------------------------------------------------------------ 权限/进程环境
def hub_is_elevated():
    """当前 Hub 进程是否以管理员（高完整性）运行。"""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        try:
            import ctypes as _ctypes
            return bool(_ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False


def process_is_elevated(pid):
    """目标进程是否提权（读不到时返回 False）。"""
    try:
        import ctypes as _ctypes
        from ctypes import wintypes as _wintypes
        kernel32 = _ctypes.windll.kernel32
        advapi32 = _ctypes.windll.advapi32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        TOKEN_QUERY = 0x0008
        TokenElevation = 20
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,
                                      False, int(pid))
        if not handle:
            return None
        token = _wintypes.HANDLE()
        if not advapi32.OpenProcessToken(handle, TOKEN_QUERY,
                                         _ctypes.byref(token)):
            kernel32.CloseHandle(handle)
            return None
        elevation = _wintypes.DWORD()
        size = _wintypes.DWORD()
        ok = advapi32.GetTokenInformation(token, TokenElevation,
                                          _ctypes.byref(elevation),
                                          _ctypes.sizeof(elevation),
                                          _ctypes.byref(size))
        kernel32.CloseHandle(token)
        kernel32.CloseHandle(handle)
        if not ok:
            return None
        return bool(elevation.value)
    except Exception:
        return None


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
                  "adb_enabled", "daily_close_after",
                  "auto_download_update", "minimize_to_tray"):
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
    scale = value.get("font_scale")
    if isinstance(scale, (int, float)) and not isinstance(scale, bool):
        scale = float(scale)
        if scale in [float(item) for item in FONT_SCALES]:
            out["font_scale"] = scale
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
    raw_settings = data.get("settings") \
        if isinstance(data.get("settings"), dict) else {}
    settings = _clean_settings(raw_settings)
    explicit_accent = isinstance(raw_settings.get("accent"), str) \
        and bool(_ACCENT_RE.match(raw_settings.get("accent").strip()))

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

    # The additional NTE script shares the configured game launcher, not script settings.
    nte_app = next((app for app in apps if app.get("key") == "nte"), {})
    for app in apps:
        if app.get("key") == "oknte" and not app.get("game_exe"):
            app["game_exe"] = nte_app.get("game_exe", "")

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
        if app.get("key") in PYAPPIFY_APPS:
            app["launch"] = _merge_launch_spec(saved_launch, build_pyappify_launch(app))
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
            "settings": settings,
            "settings_explicit_accent": explicit_accent}
    # v0.10：内置异环若错误指向 NTELauncher.exe，加载时纠正并保存
    if _migrate_nte_game_exe(apps):
        try:
            save_state(apps, clash, root, meta["daily_order"], settings)
        except Exception:
            pass
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
PYAPPIFY_APPS = {"wuwa": "ok-ww", "oknte": "ok-nte"}
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
    """Backward-compatible ok-ww helper (including keyless fixture callers)."""
    return build_pyappify_launch(app, app_name="ok-ww")


def build_pyappify_launch(app, app_name=None):
    """Discover bundled Python + working/main.py (repo fallback) without running it."""
    app = app or {}
    launcher = _launch_text(app.get("script_exe"))
    install_dir = os.path.dirname(launcher)
    if not install_dir:
        return None
    app_name = app_name or PYAPPIFY_APPS.get(app.get("key"), "ok-ww")
    app_dir = os.path.join(install_dir, "data", "apps", app_name)
    python_dir = os.path.join(app_dir, "python")
    working = os.path.join(app_dir, "working")
    repo = os.path.join(app_dir, "repo")
    if not os.path.isfile(os.path.join(working, "main.py")) \
            and os.path.isfile(os.path.join(repo, "main.py")):
        working = repo
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
    if str(app.get("key") or "") in PYAPPIFY_APPS:
        spec = build_pyappify_launch(app)
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
        if os.path.basename(lower) in {name.lower() for name in names} \
                and os.path.dirname(lower) in dirs:
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
