# -*- coding: utf-8 -*-
"""游戏运行检测：窗口类/标题 + 进程 + 可选 ADB。

规则来源优先级：
1. app["detect"]：用户在「编辑卡片」里自定义的规则（config.json 持久化）；
2. 自动规则：MaaNTE/MaaEnd 读各自 interface.json 的 controller[].win32
   （多个 Win32 controller 取并集，云 controller 单列 cloud），
   ok-ww/MAA 使用内置表（依据 docs/game-detection-research.md §5.2/§6.3）；
3. 兼容旧配置：没有任何规则时回退 app["game_procs"]。

规则 schema（config.json 的 app.detect）::

    {
      "any_of": [
        {"type": "win", "class_re": "...", "title_re": "...",
         "title_optional": false, "match": "all", "require_visible": false,
         "min_client_size": [200, 120],
         "proc_names": ["X.exe"], "proc_path_re": "..."},
        {"type": "proc", "names": ["X.exe"], "path_re": "..."},
        {"type": "adb", "pkg": ["com.x.y"], "activity": "...", "serial_re": ".*"}
      ],
      "proc_class_check": [{"name": "X.exe", "win_class_re": "..."}],
      "launcher": {"any_of": [...]},
      "cloud": {"any_of": [...]}
    }

`launcher` / `cloud` 只用于状态文案（启动器已开 / 云游戏运行中），不计入 running。
ADB 检测默认关闭（避免每次轮询拉起 adb 进程），需要时调用 set_adb_enabled(True)。
"""
import copy
import ctypes
import json
import os
import re
import shutil
import subprocess
import time
from ctypes import wintypes

from . import store

# ------------------------------------------------------------------ 快照参数
WIN_MIN_CLIENT = (100, 100)       # 窗口快照的默认最小客户区（规则里可再放大）
WINDOW_SNAPSHOT_TTL = 1.0         # 秒；UI 每 1.5s 轮询，同一轮复用
MAX_WINDOWS = 2000
PID_PATH_TTL = 2.0
ADB_ENABLED = False               # 默认关闭
ADB_PATH = ""                     # 为空时尝试 PATH 里的 adb
ADB_TIMEOUT = 1.5
ADB_CACHE_TTL = 5.0
_RULE_TYPES = {"win": "window", "window": "window", "proc": "proc", "process": "proc",
               "adb": "adb"}

_AUTO_RULES_CACHE = {}
_WINDOW_CACHE = {"time": 0.0, "windows": []}
_PID_PATH_CACHE = {}
_ADB_CACHE = {"time": 0.0, "devices": []}


# ------------------------------------------------------------------ Win32 原型
user32 = store.user32
kernel32 = store.kernel32

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND,
                                            ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.GetClientRect.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SwitchToThisWindow.argtypes = [wintypes.HWND, wintypes.BOOL]

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                wintypes.LPWSTR,
                                                ctypes.POINTER(wintypes.DWORD)]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080


# ------------------------------------------------------------------ 内置规则
# 依据 docs/game-detection-research.md：§3.2（异环）、§4.2（终末地）、
# §5.2（鸣潮 ok-ww）、§6.3（明日方舟 MAA）。
BUILTIN_RULES = {
    "maa": {
        "any_of": [
            {"type": "win", "class_re": "^UnityWndClass$",
             "title_re": r"^\s*(明日方舟|Arknights)", "min_client_size": [200, 120]},
            {"type": "proc", "names": ["Arknights.exe"],
             "path_re": r"Arknights Game\\Arknights\.exe$"},
            {"type": "adb",
             "pkg": ["com.hypergryph.arknights", "com.hypergryph.arknights.bilibili",
                     "com.YoStarEN.Arknights", "com.YoStarJP.Arknights",
                     "com.YoStarKR.Arknights", "tw.txwy.and.arknights"],
             "activity": "com.u8.sdk.U8UnityContext", "serial_re": ".*"},
        ],
        "launcher": {"any_of": [
            {"type": "win", "class_re": r"^Qt\d+QWindowIcon$",
             "title_re": "鹰角启动器"},
            {"type": "proc", "names": ["Launcher.exe"],
             "path_re": r"(Arknights bilibili|Hypergryph Launcher)\\Launcher\.exe$"},
        ]},
    },
    "nte": {
        "any_of": [
            {"type": "win", "class_re": "UnrealWindow",
             "title_re": r"^\s*(异环|NTE)\s*$", "min_client_size": [200, 120]},
            {"type": "proc", "names": ["HTGame.exe"],
             "path_re": r"\\Client\\WindowsNoEditor\\HT\\Binaries\\Win64\\HTGame\.exe$"},
        ],
        "launcher": {"any_of": [
            {"type": "proc", "names": ["NTELauncher.exe"],
             "path_re": r"Neverness To Everness\\NTELauncher\.exe$"},
        ]},
        "cloud": {"any_of": [
            {"type": "win", "class_re": "^Qt.*$",
             "title_re": r"^\s*云.*?异环\s*$", "min_client_size": [200, 120]},
        ]},
    },
    "wuwa": {
        "any_of": [
            # ok-ww：UnrealWindow + Client-Win64-Shipping.exe 双重校验（不要求标题）
            {"type": "win", "class_re": "^UnrealWindow$",
             "title_re": r"^\s*(鸣潮|Wuthering Waves)\s*$", "title_optional": True,
             "min_client_size": [200, 120],
             "proc_names": ["Client-Win64-Shipping.exe"],
             "proc_path_re": r"Wuthering Waves\\Wuthering Waves Game\\Client\\Binaries\\Win64\\Client-Win64-Shipping\.exe$"},
            {"type": "proc", "names": ["Client-Win64-Shipping.exe"],
             "path_re": r"Wuthering Waves\\Wuthering Waves Game\\Client\\Binaries\\Win64\\Client-Win64-Shipping\.exe$"},
            {"type": "proc", "names": ["Wuthering Waves.exe"],
             "path_re": r"Wuthering Waves\\Wuthering Waves\.exe$"},
        ],
        "launcher": {"any_of": [
            {"type": "proc", "names": ["launcher.exe"],
             "path_re": r"Wuthering Waves\\launcher\.exe$"},
        ]},
    },
    "maaend": {
        "any_of": [
            {"type": "win", "class_re": "UnityWndClass", "title_re": "Endfield",
             "min_client_size": [200, 120]},
            {"type": "proc", "names": ["Endfield.exe"],
             "path_re": r"\\games\\Endfield Game\\Endfield\.exe$"},
            {"type": "adb",
             "pkg": ["com.hypergryph.endfield", "com.hypergryph.endfield.bilibili",
                     "com.gryphline.endfield.gp", "com.hypergryph.endfield.vn",
                     "com.hypergryph.cloud.endfield"],
             "activity": "com.u8.sdk.U8UnityContext", "serial_re": ".*"},
        ],
        "launcher": {"any_of": [
            {"type": "win", "class_re": r"^Qt\d+QWindowIcon$",
             "title_re": "鹰角启动器"},
            {"type": "proc", "names": ["Launcher.exe"],
             "path_re": r"(Hypergryph Launcher|Arknights bilibili)\\Launcher\.exe$"},
        ]},
    },
}


# ------------------------------------------------------------------ 小工具
def _compile(pattern, default=None):
    text = str(pattern or "").strip()
    if not text:
        return None if default is None else re.compile(default, re.IGNORECASE)
    try:
        return re.compile(text, re.IGNORECASE)
    except re.error:
        return None


def _rule_kind(rule):
    if not isinstance(rule, dict):
        return ""
    return _RULE_TYPES.get(str(rule.get("type") or "").strip().lower(), "")


def _split_names(value):
    text = value if isinstance(value, str) else ""
    return [item.strip() for item in re.split(r"[,，;；\n]+", text) if item.strip()]


def _min_size(value):
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            return int(value[0]), int(value[1])
        except (TypeError, ValueError):
            pass
    return WIN_MIN_CLIENT


def _schema_only(rules):
    """去掉 source 等运行时字段，用于比较两份规则是否等价。"""
    if not isinstance(rules, dict):
        return {}
    return {key: value for key, value in rules.items()
            if key in ("any_of", "proc_class_check", "launcher", "cloud")}


def _has_rules(rules):
    rules = rules or {}
    if rules.get("any_of") or rules.get("proc_class_check"):
        return True
    for field in ("launcher", "cloud"):
        group = rules.get(field)
        if isinstance(group, dict) and (group.get("any_of")
                                        or group.get("proc_class_check")):
            return True
    return False


def _has_adb_rule(rules):
    rules = rules or {}
    groups = [rules.get("any_of") or []]
    for field in ("launcher", "cloud"):
        group = rules.get(field)
        if isinstance(group, dict):
            groups.append(group.get("any_of") or [])
    return any(_rule_kind(rule) == "adb" for group in groups for rule in group)


# ------------------------------------------------------------------ 窗口快照
def snapshot_windows(force=False):
    """一次 EnumWindows 快照：hwnd / class / title / 客户区 / pid。

    允许最小化与同名多窗口；默认不要求 visible / 前台；过滤 client < 100×100
    （最小化的窗口不做尺寸过滤，避免「最小化就被判为关闭」）。
    """
    now = time.monotonic()
    if not force and now - _WINDOW_CACHE["time"] < WINDOW_SNAPSHOT_TTL:
        return _WINDOW_CACHE["windows"]
    windows = []

    def callback(hwnd, _lparam):
        if len(windows) >= MAX_WINDOWS:
            return True
        try:
            if not user32.IsWindow(hwnd):
                return True
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if ex_style & WS_EX_TOOLWINDOW:
                return True
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            class_name = cls.value or ""
            if not class_name:
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            title = ""
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 2)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value or ""
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            rect = RECT()
            user32.GetClientRect(hwnd, ctypes.byref(rect))
            width = max(0, int(rect.right - rect.left))
            height = max(0, int(rect.bottom - rect.top))
            iconic = bool(user32.IsIconic(hwnd))
            if not iconic and (width < WIN_MIN_CLIENT[0] or height < WIN_MIN_CLIENT[1]):
                return True
            windows.append(dict(
                hwnd=int(hwnd), class_name=class_name, title=title,
                width=width, height=height, pid=int(pid.value), iconic=iconic,
                visible=bool(user32.IsWindowVisible(hwnd)),
            ))
        except Exception:
            pass
        return True

    try:
        user32.EnumWindows(WNDENUMPROC(callback), 0)
    except Exception:
        windows = []
    _WINDOW_CACHE["windows"] = windows
    _WINDOW_CACHE["time"] = now
    return windows


def process_path(pid):
    """取进程完整 exe 路径；权限不足/失败返回空串。"""
    if not pid:
        return ""
    handle = None
    try:
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
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


def _pid_path(pid):
    now = time.monotonic()
    hit = _PID_PATH_CACHE.get(pid)
    if hit and now - hit[0] < PID_PATH_TTL:
        return hit[1]
    path = process_path(pid)
    if len(_PID_PATH_CACHE) > 512:
        _PID_PATH_CACHE.clear()
    _PID_PATH_CACHE[pid] = (now, path)
    return path


# ------------------------------------------------------------------ 规则匹配
def _window_proc_ok(rule, win):
    """窗口所属进程校验（ok-ww 的 class + 进程双重校验）。"""
    names = [str(name).strip().lower() for name in (rule.get("proc_names") or [])
             if str(name).strip()]
    if not names:
        return True
    path = _pid_path(win.get("pid", 0))
    if path:
        if os.path.basename(path).lower() not in names:
            return False
        path_pat = _compile(rule.get("proc_path_re"))
        if path_pat is not None and path_pat.search(path) is None:
            return False
        return True
    # 路径取不到 → 降级：用同名进程的 pid 集合核对；仍取不到则放行
    pids = store.pids_for_procs({name.upper() for name in names})
    if not pids:
        return True
    return int(win.get("pid", 0)) in pids


def _match_win_rule(rule, windows):
    class_pat = _compile(rule.get("class_re"))
    title_pat = None if rule.get("title_optional") else _compile(rule.get("title_re"))
    if class_pat is None and title_pat is None:
        return None
    match_any = str(rule.get("match") or "all").lower() == "any"
    require_visible = bool(rule.get("require_visible"))
    min_w, min_h = _min_size(rule.get("min_client_size"))
    for win in windows:
        if not win.get("iconic") and (win.get("width", 0) < min_w
                                      or win.get("height", 0) < min_h):
            continue
        if require_visible and not win.get("visible"):
            continue
        class_ok = class_pat is not None and \
            class_pat.search(win.get("class_name") or "") is not None
        title_ok = title_pat is not None and \
            title_pat.search(win.get("title") or "") is not None
        checks = []
        if class_pat is not None:
            checks.append(class_ok)
        if title_pat is not None:
            checks.append(title_ok)
        ok = any(checks) if match_any else all(checks)
        if not ok:
            continue
        if not _window_proc_ok(rule, win):
            continue
        return win
    return None


def _match_proc_rule(rule, processes):
    names = {str(name).strip().upper() for name in (rule.get("names") or [])
             if str(name).strip()}
    if not names or not processes:
        return False
    hits = names & set(processes)
    if not hits:
        return False
    path_pat = _compile(rule.get("path_re"))
    if path_pat is None:
        return True
    pids = store.pids_for_procs(hits)
    if not pids:
        return True          # 拿不到 PID（权限/竞态）→ 降级只比进程名
    checked = 0
    for pid in pids:
        path = _pid_path(pid)
        if not path:
            continue
        checked += 1
        if path_pat.search(path):
            return True
    return checked == 0      # 所有路径都读不到 → 降级只比进程名


def _match_proc_class_check(check, windows):
    names = [str(name).strip().lower() for name in [check.get("name")]
             if str(name).strip()]
    if not names:
        return None
    class_pat = _compile(check.get("win_class_re"))
    if class_pat is None:
        return None
    path_pat = _compile(check.get("path_re"))
    pids = None
    for win in windows:
        if class_pat.search(win.get("class_name") or "") is None:
            continue
        path = _pid_path(win.get("pid", 0))
        if path:
            if os.path.basename(path).lower() != names[0]:
                continue
            if path_pat is not None and path_pat.search(path) is None:
                continue
            return win
        if pids is None:
            pids = store.pids_for_procs({name.upper() for name in names})
        if pids and int(win.get("pid", 0)) in pids:
            return win
    return None


def _match_group(group, windows, processes, adb_state):
    if not isinstance(group, dict):
        return False
    for rule in group.get("any_of") or []:
        kind = _rule_kind(rule)
        if kind == "window" and _match_win_rule(rule, windows):
            return True
        if kind == "proc" and _match_proc_rule(rule, processes):
            return True
        if kind == "adb" and adb_state and _match_adb_rule(rule, adb_state):
            return True
    for check in group.get("proc_class_check") or []:
        if _match_proc_class_check(check, windows):
            return True
    return False


# ------------------------------------------------------------------ ADB（默认关闭）
def set_adb_enabled(enabled, adb_path=None):
    """打开/关闭 ADB 检测；adb_path 为空时用 PATH 里的 adb。"""
    global ADB_ENABLED, ADB_PATH
    ADB_ENABLED = bool(enabled)
    if adb_path is not None:
        ADB_PATH = str(adb_path or "")
    _ADB_CACHE["time"] = 0.0


def _find_adb():
    if ADB_PATH and os.path.isfile(ADB_PATH):
        return ADB_PATH
    try:
        return shutil.which("adb") or ""
    except Exception:
        return ""


def _run_adb(args):
    try:
        proc = subprocess.run(args, capture_output=True, timeout=ADB_TIMEOUT,
                              creationflags=0x08000000)
        if proc.returncode != 0:
            return ""
        return proc.stdout.decode("utf-8", "ignore")
    except Exception:
        return ""


def adb_snapshot(force=False):
    """返回 [{serial, focus}]；ADB 不可用时返回空列表（是否启用由调用方决定）。"""
    now = time.monotonic()
    if not force and now - _ADB_CACHE["time"] < ADB_CACHE_TTL:
        return _ADB_CACHE["devices"]
    devices = []
    adb = _find_adb()
    if adb:
        listing = _run_adb([adb, "devices"])
        for line in listing.splitlines()[1:]:
            parts = line.split()
            if len(parts) < 2 or parts[1] != "device":
                continue
            serial = parts[0]
            window_dump = _run_adb([adb, "-s", serial, "shell", "dumpsys", "window"])
            focus = ""
            match = re.search(r"mCurrentFocus=Window\{[^}]*?\s([A-Za-z0-9_.]+/[A-Za-z0-9_.]+)\}",
                              window_dump)
            if not match:
                match = re.search(r"mFocusedApp=.*?\s([A-Za-z0-9_.]+/[A-Za-z0-9_.]+)",
                                  window_dump)
            if match:
                focus = match.group(1)
            devices.append({"serial": serial, "focus": focus})
    _ADB_CACHE["devices"] = devices
    _ADB_CACHE["time"] = now
    return devices


def _match_adb_rule(rule, adb_state):
    packages = [str(pkg).strip().lower() for pkg in (rule.get("pkg") or [])
                if str(pkg).strip()]
    if not packages or not adb_state:
        return False
    serial_pat = _compile(rule.get("serial_re"), default=".*")
    activity = str(rule.get("activity") or "").strip().lower()
    for device in adb_state:
        serial = device.get("serial") or ""
        if serial_pat is not None and serial_pat.search(serial) is None:
            continue
        focus = (device.get("focus") or "").lower()
        if not focus:
            continue
        package = focus.split("/", 1)[0]
        if package not in packages:
            continue
        if activity and "/" in focus and activity not in focus:
            continue
        return True
    return False


# ------------------------------------------------------------------ 规则来源
def _dedupe_rules(rules):
    seen, out = set(), []
    for rule in rules:
        signature = json.dumps(rule, sort_keys=True, ensure_ascii=False)
        if signature in seen:
            continue
        seen.add(signature)
        out.append(rule)
    return out


def _rules_from_interface(key, script_dir):
    """从脚本自己的 interface.json 读取 controller[].win32 规则。"""
    path = os.path.join(script_dir, "interface.json") if script_dir else ""
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except Exception:
        return None
    controllers = data.get("controller")
    if not isinstance(controllers, list):
        return None
    win_rules, cloud_rules = [], []
    for controller in controllers:
        if not isinstance(controller, dict):
            continue
        if str(controller.get("type") or "").lower() != "win32":
            continue
        win32 = controller.get("win32")
        if not isinstance(win32, dict):
            continue
        class_re = str(win32.get("class_regex") or "").strip()
        title_re = str(win32.get("window_regex") or "").strip()
        if not class_re and not title_re:
            continue
        rule = {"type": "win", "min_client_size": [200, 120]}
        if class_re:
            rule["class_re"] = class_re
        if title_re:
            rule["title_re"] = title_re
        name = str(controller.get("name") or "").lower()
        if "cloud" in name or "云" in name:
            cloud_rules.append(rule)
        else:
            win_rules.append(rule)
    win_rules = _dedupe_rules(win_rules)
    if not win_rules:
        return None
    base = copy.deepcopy(BUILTIN_RULES.get(key) or {})
    extra_any = [rule for rule in (base.get("any_of") or [])
                 if _rule_kind(rule) != "window"]
    rules = {"any_of": win_rules + extra_any}
    if base.get("launcher"):
        rules["launcher"] = copy.deepcopy(base["launcher"])
    cloud_rules = _dedupe_rules(cloud_rules)
    if cloud_rules:
        rules["cloud"] = {"any_of": cloud_rules}
    elif base.get("cloud"):
        rules["cloud"] = copy.deepcopy(base["cloud"])
    return rules


def read_auto_rules(app):
    """读取脚本自动规则：MaaNTE/MaaEnd 优先 interface.json，其余用内置表。"""
    app = app or {}
    key = str(app.get("key") or "")
    if key not in BUILTIN_RULES:
        # 添加卡片时可能只有游戏名称（如「鸣潮」），按名称反查内置规则
        try:
            inferred = store._game_profile(app)[0]
        except Exception:
            inferred = ""
        if inferred:
            key = inferred
    script_dir = os.path.dirname(app.get("script_exe") or "")
    if key in ("nte", "maaend"):
        path = os.path.join(script_dir, "interface.json") if script_dir else ""
        try:
            mtime = os.path.getmtime(path) if path and os.path.isfile(path) else 0.0
        except OSError:
            mtime = 0.0
        cache_key = (key, path.lower(), mtime)
        if cache_key in _AUTO_RULES_CACHE:
            return copy.deepcopy(_AUTO_RULES_CACHE[cache_key])
        rules = _rules_from_interface(key, script_dir)
        if not rules:
            rules = copy.deepcopy(BUILTIN_RULES.get(key))
        if len(_AUTO_RULES_CACHE) > 32:
            _AUTO_RULES_CACHE.clear()
        if rules:
            _AUTO_RULES_CACHE[cache_key] = rules
            return copy.deepcopy(rules)
        return None
    rules = BUILTIN_RULES.get(key)
    return copy.deepcopy(rules) if rules else None


def read_game_rules(app):
    """返回某张卡片当前生效的检测规则（含 source：user/auto/legacy/none）。"""
    app = app or {}
    user_rules = store._clean_detect(app.get("detect"))
    if _has_rules(user_rules):
        user_rules["source"] = "user"
        return user_rules
    auto_rules = read_auto_rules(app)
    if _has_rules(auto_rules):
        auto_rules["source"] = "auto"
        return auto_rules
    procs = [str(name).strip() for name in (app.get("game_procs") or [])
             if str(name).strip()]
    if procs:
        return {"any_of": [{"type": "proc", "names": procs}], "source": "legacy"}
    return {"any_of": [], "source": "none"}


# ------------------------------------------------------------------ 检测入口
def detect_game_state(app, windows=None, processes=None, adb_enabled=None,
                      rules=None):
    """返回完整检测状态 dict。

    字段：running / reason(window|proc|adb|launcher|cloud|"") / label（中文文案）/
    hwnd / source(user/auto/legacy/none) / configured / rules / adb_enabled。
    """
    app = app or {}
    rules = rules or read_game_rules(app)
    if windows is None:
        windows = snapshot_windows()
    if processes is None:
        processes = store.snapshot_processes()
    enabled = ADB_ENABLED if adb_enabled is None else bool(adb_enabled)
    adb_state = adb_snapshot() if enabled and _has_adb_rule(rules) else []
    configured = _has_rules(rules) or bool(app.get("game_exe")) \
        or bool(app.get("game_procs"))
    state = {
        "running": False, "reason": "", "label": "未运行", "hwnd": None,
        "rules": rules, "source": rules.get("source", "none"),
        "configured": configured, "adb_enabled": enabled,
    }
    if not configured:
        state["label"] = "未配置"
        return state
    match = _match_detect(rules, windows, processes, adb_state)
    if match:
        state.update(running=True, reason=match["reason"],
                     hwnd=match.get("hwnd"))
        state["label"] = {
            "window": "运行中（窗口）",
            "proc": "运行中（进程）",
            "adb": "运行中（ADB）",
        }[match["reason"]]
        return state
    # 启动器 / 云游戏只影响状态文案，不计入 running
    if _match_group(rules.get("launcher"), windows, processes, adb_state):
        state["reason"] = "launcher"
        state["label"] = "启动器已开"
        return state
    if _match_group(rules.get("cloud"), windows, processes, adb_state):
        state["reason"] = "cloud"
        state["label"] = "云游戏运行中"
        return state
    return state


def _match_detect(rules, windows, processes, adb_state):
    """先窗口、再进程、再 ADB；proc_class_check 是窗口+进程双重校验。"""
    any_of = rules.get("any_of") or []
    for wanted in ("window", "proc", "adb"):
        for rule in any_of:
            if _rule_kind(rule) != wanted:
                continue
            if wanted == "window":
                win = _match_win_rule(rule, windows)
                if win:
                    return {"reason": "window", "hwnd": win.get("hwnd"), "rule": rule}
            elif wanted == "proc":
                if _match_proc_rule(rule, processes):
                    return {"reason": "proc", "rule": rule}
            elif adb_state and _match_adb_rule(rule, adb_state):
                return {"reason": "adb", "rule": rule}
    for check in rules.get("proc_class_check") or []:
        win = _match_proc_class_check(check, windows)
        if win:
            return {"reason": "window", "hwnd": win.get("hwnd"), "rule": check}
    return None


def detect_game(app, windows=None, processes=None, adb_enabled=None):
    """兼容要求的精简接口：返回 (running: bool, reason: str)。"""
    state = detect_game_state(app, windows=windows, processes=processes,
                              adb_enabled=adb_enabled)
    return state["running"], state["reason"]


def focus_window(hwnd):
    """把游戏的顶层窗口切到前台（最小化时先恢复）。"""
    if not hwnd:
        return False
    try:
        if not user32.IsWindow(hwnd):
            return False
        user32.ShowWindow(hwnd, 9)      # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        user32.SwitchToThisWindow(hwnd, True)
        return True
    except Exception:
        return False


# ------------------------------------------------------------------ 规则 ⇄ 编辑框
def rules_to_fields(rules):
    """把规则压成编辑框里的四个字符串（窗口类/标题/进程名/ADB 包名）。"""
    rules = rules or {}
    any_of = rules.get("any_of") or []
    win = next((rule for rule in any_of if _rule_kind(rule) == "window"), None)
    proc_names = []
    for rule in any_of:
        if _rule_kind(rule) == "proc":
            proc_names.extend(str(name) for name in (rule.get("names") or []))
    if not proc_names and win:
        proc_names.extend(str(name) for name in (win.get("proc_names") or []))
    adb = next((rule for rule in any_of if _rule_kind(rule) == "adb"), None)
    return {
        "win_class": (win or {}).get("class_re", ""),
        "win_title": (win or {}).get("title_re", ""),
        "detect_procs": ", ".join(dict.fromkeys(proc_names)),
        "adb_pkg": ", ".join((adb or {}).get("pkg") or []),
    }


def rules_from_fields(win_class="", win_title="", detect_procs="", adb_pkg="",
                      base=None):
    """根据编辑框内容生成规则；尽量保留原规则里的 path_re/launcher/cloud。"""
    base = base or {}
    win_class = str(win_class or "").strip()
    win_title = str(win_title or "").strip()
    proc_names = _split_names(detect_procs)
    packages = _split_names(adb_pkg)
    old_rules = list(base.get("any_of") or [])
    any_of = []
    if win_class or win_title:
        rule = {"type": "win", "min_client_size": [200, 120]}
        if win_class:
            rule["class_re"] = win_class
        if win_title:
            rule["title_re"] = win_title
        old = next((item for item in old_rules if _rule_kind(item) == "window"), None)
        if old:
            for field in ("title_optional", "match", "require_visible",
                          "min_client_size", "proc_names", "proc_path_re"):
                if field in old:
                    rule[field] = copy.deepcopy(old[field])
        any_of.append(rule)
    if proc_names:
        rule = {"type": "proc", "names": proc_names}
        wanted = {name.lower() for name in proc_names}
        old = next((item for item in old_rules if _rule_kind(item) == "proc"
                    and {str(name).lower() for name in (item.get("names") or [])}
                    == wanted), None)
        if old and old.get("path_re"):
            rule["path_re"] = old["path_re"]
        any_of.append(rule)
    if packages:
        rule = {"type": "adb", "pkg": packages}
        old = next((item for item in old_rules if _rule_kind(item) == "adb"), None)
        if old:
            for field in ("activity", "serial_re"):
                if old.get(field):
                    rule[field] = old[field]
        any_of.append(rule)
    result = {"any_of": any_of}
    for field in ("proc_class_check", "launcher", "cloud"):
        group = base.get(field)
        if group:
            result[field] = copy.deepcopy(group)
    return result


def rules_equal(left, right):
    """比较两份规则是否等价（忽略 source 等运行时字段）。"""
    return json.dumps(_schema_only(left), sort_keys=True, ensure_ascii=False) == \
        json.dumps(_schema_only(right), sort_keys=True, ensure_ascii=False)


def reset_cache():
    """测试用：清空窗口/进程路径/ADB 缓存。"""
    _WINDOW_CACHE["time"] = 0.0
    _WINDOW_CACHE["windows"] = []
    _PID_PATH_CACHE.clear()
    _ADB_CACHE["time"] = 0.0
    _ADB_CACHE["devices"] = []
