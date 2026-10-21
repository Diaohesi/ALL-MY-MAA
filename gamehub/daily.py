# -*- coding: utf-8 -*-
"""一键清日常：单游戏执行 + 顺序队列（支持 dry-run 预览）。

设计依据：docs/daily-automation-research.md §5 / §10
- 鸣潮 ok-ww：以管理员启动 `pythonw.exe "<working>\\main.py" -t DailyTask -e`，
  完成 = 进程退出 + 日志出现 `Successfully Executed Task, Exiting Game and App!`。
- 明日方舟 MAA：以管理员启动 `MAA.exe --skip-startup-auto-run`，等就绪后
  发送配置里的 LinkStart 全局热键，监控 `debug\\gui.log` 增量：
  `任务已全部完成！` 成功、`任务出错:` 失败、`已停止` 停止。
- 异环 MaaNTE：打开正常 UI，等本次启动就绪后发送开始任务热键，HTTP/日志等待结束。
- 终末地 MaaEnd：`--autostart --instance "<实例名>" --quit-after-run`，
  完成 = MXU 进程退出（不区分成败，日志只做启发式备注）。

安全约定：
- 只结束「本次由 Hub 启动的进程」（ShellExecuteEx 拿到的进程句柄），
  绝不对用户自己开的进程做 taskkill；MAA 已在运行时只发热键、不接管进程。
- 不自动改 MAA / ok-ww / MXU 的配置；前置不满足时明确提示设置方法。
- 只启动脚本自身；异环清日常会先打开 MaaNTE，再发送开始任务热键并等待结束。
"""
import ctypes
import json
import os
import re
import subprocess
import threading
import time
import urllib.request
from ctypes import wintypes

from . import detector, store
from .runtime_log import log_event, get_logger

# ------------------------------------------------------------------ 状态
IDLE = "idle"
STARTING = "starting"
RUNNING = "running"
FINISHED = "finished"
FAILED = "failed"
TIMEOUT = "timeout"
STOPPED = "stopped"
SKIPPED = "skipped"
DRY_RUN = "dry-run"

STATE_LABELS = {
    IDLE: "空闲", STARTING: "启动中", RUNNING: "运行中",
    FINISHED: "已完成", FAILED: "失败", TIMEOUT: "超时",
    STOPPED: "已停止", SKIPPED: "已跳过", DRY_RUN: "预演",
}

POLL_SECONDS = 0.5
MAA_READY_TIMEOUT = 60          # 秒；等 MAA 主窗口/日志就绪
MAA_HOTKEY_RETRY = 3
MXU_SETTLE_SECONDS = 3          # MXU 退出后等 agent 子进程收尾
OKWW_SUCCESS_MARKER = "Successfully Executed Task, Exiting Game and App!"
MAA_SUCCESS_MARKERS = ("任务已全部完成！", "任务已全部完成")
MAA_FAILURE_MARKERS = ("任务出错:", "任务出错：")
MAA_STOP_MARKERS = ("已停止", "正在停止……")
MAA_DAILY_TASK_HINTS = ("开始唤醒", "自动公招", "基建换班", "信用收支",
                        "理智作战", "剩余理智", "领取奖励")
MXU_UI_START_MARKERS = ("开始执行任务", "任务已提交")
MXU_UI_DONE_MARKERS = ("tasks-completed", "停止任务", "已停止",
                       "任务已全部完成")
MXU_UI_FAIL_MARKERS = ("任务出错", "执行失败")
MXU_UI_NOTE = "异环：打开 MaaNTE → 发送开始任务（Ctrl+F10）→ 等待任务结束"
MXU_HTTP_DEFAULT_PORT = 12701
MXU_HTTP_FALLBACK_SECONDS = 10

# 运行时可被测试替换的钩子
_now = time.monotonic
_sleep = time.sleep

# ------------------------------------------------------------------ Win32
user32 = store.user32
kernel32 = store.kernel32
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.WaitForSingleObject.restype = wintypes.DWORD
kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE,
                                        ctypes.POINTER(wintypes.DWORD)]
kernel32.GetExitCodeProcess.restype = wintypes.BOOL
kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
kernel32.TerminateProcess.restype = wintypes.BOOL
kernel32.GetProcessId.argtypes = [wintypes.HANDLE]
kernel32.GetProcessId.restype = wintypes.DWORD
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

WAIT_TIMEOUT = 0x00000102
WAIT_OBJECT_0 = 0x00000000
SEE_MASK_NOCLOSEPROCESS = 0x00000040
ERROR_CANCELLED = 1223


class SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", ctypes.c_ulong),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", wintypes.LPVOID),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIconOrMonitor", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(SHELLEXECUTEINFOW)]
shell32.ShellExecuteExW.restype = wintypes.BOOL


class DailyError(Exception):
    """启动/执行清日常时的可读错误（message 直接给用户看）。"""


class ProcessHandle:
    """ShellExecuteEx 拿到的进程句柄（只操作本次启动的进程）。"""

    def __init__(self, handle, pid, command=""):
        self.handle = handle
        self.pid = int(pid or 0)
        self.command = command
        self._closed = False

    def alive(self):
        if not self.handle or self._closed:
            return False
        return kernel32.WaitForSingleObject(self.handle, 0) == WAIT_TIMEOUT

    def wait(self, timeout_ms=500):
        """等待退出；返回 True=已退出，False=仍在运行。"""
        if not self.handle or self._closed:
            return True
        return kernel32.WaitForSingleObject(self.handle,
                                            int(timeout_ms)) != WAIT_TIMEOUT

    def exit_code(self):
        if not self.handle or self._closed:
            return None
        code = wintypes.DWORD()
        if kernel32.GetExitCodeProcess(self.handle, ctypes.byref(code)):
            return int(code.value)
        return None

    def terminate(self):
        """只结束本句柄对应的进程（不碰用户其它进程）。"""
        if not self.handle or self._closed:
            return False
        try:
            return bool(kernel32.TerminateProcess(self.handle, 1))
        except Exception:
            return False

    def close(self):
        if self.handle and not self._closed:
            try:
                kernel32.CloseHandle(self.handle)
            except Exception:
                pass
            self._closed = True


def launch_elevated(exe, params="", cwd=None):
    """以管理员身份启动进程（UAC），返回 ProcessHandle；失败抛 DailyError。"""
    exe = str(exe or "").strip()
    if not exe or not os.path.isfile(exe):
        raise DailyError(f"文件不存在：{exe or '(空)'}")
    info = SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(SHELLEXECUTEINFOW)
    info.fMask = SEE_MASK_NOCLOSEPROCESS
    info.lpVerb = "runas"
    info.lpFile = exe
    info.lpParameters = str(params or "")
    info.lpDirectory = str(cwd or os.path.dirname(exe))
    info.nShow = 1
    ctypes.set_last_error(0)
    if not shell32.ShellExecuteExW(ctypes.byref(info)):
        code = ctypes.get_last_error()
        if code == ERROR_CANCELLED:
            raise DailyError("用户取消了管理员权限（UAC）请求")
        if code == 2:
            raise DailyError(f"找不到程序：{exe}")
        raise DailyError(f"启动失败（错误码 {code}）：{os.path.basename(exe)}")
    if not info.hProcess:
        raise DailyError("启动成功但未拿到进程句柄")
    pid = kernel32.GetProcessId(info.hProcess)
    command = _quote_arg(exe, force=True)
    if params:
        command += f" {params}"
    return ProcessHandle(info.hProcess, pid, command)


# ------------------------------------------------------------------ 日志增量读取
class LogWatcher:
    """记录 offset 的日志增量读取；处理轮转/截断，UTF-8 errors=replace。"""

    def __init__(self, path):
        self.path = str(path or "")
        self.offset = self._size()
        self.tail_lines = []

    def _size(self):
        try:
            return os.path.getsize(self.path) if self.path else 0
        except OSError:
            return 0

    def reset(self):
        self.offset = self._size()
        self.tail_lines = []

    def read(self):
        if not self.path:
            return ""
        try:
            size = self._size()
            if size < self.offset:      # 轮转/清空
                self.offset = 0
            if size == self.offset:
                return ""
            with open(self.path, "rb") as fh:
                fh.seek(self.offset)
                data = fh.read(max(0, size - self.offset))
            self.offset = size
        except OSError:
            return ""
        text = data.decode("utf-8", "replace")
        lines = text.splitlines()
        if lines:
            self.tail_lines = (self.tail_lines + lines)[-40:]
        return text

    def tail(self, count=15):
        return "\n".join(self.tail_lines[-count:])


# ------------------------------------------------------------------ 配置读取
def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def okww_paths(app):
    """Backward-compatible entry point for ok-ww callers."""
    return ok_script_paths(app)


def ok_script_paths(app):
    """Read-only paths for the installed OK script; task/log names are app-specific."""
    spec = app.get("launch")
    if not isinstance(spec, dict) or not spec.get("exe"):
        spec = store.build_pyappify_launch(app) or {}
    cwd = spec.get("cwd") or ""
    return {
        "exe": spec.get("exe") or "",
        "script": spec.get("script") or "",
        "cwd": cwd,
        "launcher": spec.get("launcher_exe") or app.get("script_exe", ""),
        "log": os.path.join(cwd, "logs", "ok-script.log") if cwd else "",
        "daily_config": os.path.join(cwd, "configs", "DailyRoutineTask.json"
                                     if app.get("key") == "oknte" else "DailyTask.json") if cwd else "",
    }


def maa_paths(app):
    base = os.path.dirname(app.get("script_exe") or "")
    return {
        "base": base,
        "exe": app.get("script_exe") or "",
        "gui_new": os.path.join(base, "config", "gui.new.json") if base else "",
        "gui_old": os.path.join(base, "config", "gui.json") if base else "",
        "log": os.path.join(base, "debug", "gui.log") if base else "",
    }


def mxu_paths(app):
    exe = app.get("script_exe") or ""
    base = os.path.dirname(exe)
    project = os.path.splitext(os.path.basename(exe))[0]
    return {
        "base": base,
        "exe": exe,
        "config": os.path.join(base, "config", f"mxu-{project}.json") if base else "",
        "log": os.path.join(base, "debug", "mxu-tauri.log") if base else "",
    }


def mxu_instances(app):
    """读取 MXU 实例列表（含启用任务数、是否含 LaunchGamePC 前置）。"""
    path = mxu_paths(app)["config"]
    data = _read_json(path)
    rows = []
    for inst in data.get("instances") or []:
        if not isinstance(inst, dict):
            continue
        name = str(inst.get("name") or "").strip()
        if not name:
            continue
        tasks = [task for task in (inst.get("tasks") or [])
                 if isinstance(task, dict)]
        enabled = [task for task in tasks if task.get("enabled")]
        raw = json.dumps(inst, ensure_ascii=False)
        rows.append({
            "name": name,
            "id": str(inst.get("id") or "").strip(),
            "uuid": str(inst.get("uuid") or "").strip(),
            "enabled_count": len(enabled),
            "total_tasks": len(tasks),
            "has_launch_pretask": "LaunchGamePC" in raw,
        })
    return rows


def _suggest_mxu_instance(app, instances):
    """autoStartInstanceId → 第一个有启用任务的实例；再按常用实例名兜底。"""
    target = ""
    try:
        data = mxu_config(app)
        settings = data.get("settings") if isinstance(data.get("settings"),
                                                     dict) else {}
        target = str(settings.get("autoStartInstanceId") or "").strip()
    except Exception:
        target = ""
    if target:
        for row in instances:
            if target in (row.get("id"), row.get("uuid"), row.get("name")):
                return row["name"]
    names = [row["name"] for row in instances if row.get("enabled_count", 0)]
    for preferred in ("全套日常", "快速日常", "挂机任务"):
        if preferred in names:
            return preferred
    return names[0] if names else ""


def mxu_config(app):
    """读取 MXU 配置文件。"""
    return _read_json(mxu_paths(app)["config"])


def mxu_instance_id(app, name):
    for row in mxu_instances(app):
        if row["name"] == name:
            return row.get("id") or row.get("uuid") or ""
    return ""


def mxu_ui_hotkey(app):
    """读取 MaaNTE「开始任务」全局热键；未启用/无效返回 None。"""
    data = mxu_config(app)
    settings = data.get("settings") if isinstance(data.get("settings"), dict) \
        else {}
    hotkeys = settings.get("hotkeys")
    if not isinstance(hotkeys, dict):
        return None
    if hotkeys.get("globalEnabled") is False:
        return None
    raw = hotkeys.get("startTasks")
    if isinstance(raw, dict):
        key = str(raw.get("key") or "").strip()
        mods = raw.get("modifiers") or raw.get("mods") or []
        if isinstance(mods, str):
            mods = [part.strip() for part in re.split(r"[+,]", mods)
                    if part.strip()]
        if key and _vk_code(key) is not None:
            mods = [str(item).strip() for item in mods if str(item).strip()]
            return {"key": key, "modifiers": mods,
                    "text": " + ".join(mods + [key])}
        return None
    if isinstance(raw, str) and raw.strip():
        return _parse_hotkey_text(raw)
    return None


def mxu_latest_log(app):
    """MaaNTE debug 目录下最新的 .log（tauri 日志按日期滚动）。"""
    paths = mxu_paths(app)
    debug = os.path.join(paths["base"], "debug") if paths["base"] else ""
    if debug and os.path.isdir(debug):
        try:
            files = [os.path.join(debug, name)
                     for name in os.listdir(debug)
                     if name.lower().endswith(".log")
                     and not name.lower().startswith("maafw")]
            files = [path for path in files if os.path.isfile(path)]
            if files:
                return max(files, key=os.path.getmtime)
        except OSError:
            pass
    return paths["log"] if paths["log"] and os.path.isfile(paths["log"]) \
        else ""


def mxu_web_port(app):
    settings = mxu_config(app).get("settings")
    if isinstance(settings, dict):
        try:
            return int(settings.get("webServerPort")
                       or MXU_HTTP_DEFAULT_PORT)
        except (TypeError, ValueError):
            pass
    return MXU_HTTP_DEFAULT_PORT


def mxu_http_url(app):
    return f"http://127.0.0.1:{mxu_web_port(app)}/maa/state"


def _mxu_state_row(data, instance_id, instance_name):
    """在 /maa/state 的任意嵌套结构中按 id/name 找实例状态。"""
    found = []

    def walk(node):
        if isinstance(node, dict):
            if instance_id and str(node.get("id") or
                                   node.get("instance_id") or "") == \
                    str(instance_id):
                found.append(node)
            elif instance_name and str(node.get("name") or "") == \
                    str(instance_name):
                found.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return found[0] if found else None


def mxu_http_state(app, instance_name=""):
    """轮询 MaaNTE 本地 HTTP /maa/state；返回 running/status/found。"""
    url = mxu_http_url(app)
    try:
        with urllib.request.urlopen(url, timeout=1.5) as response:
            body = response.read()
        data = json.loads(body.decode("utf-8", "replace"))
    except Exception as exc:
        return {"ok": False, "error": str(exc), "url": url}
    instance_id = mxu_instance_id(app, instance_name) if instance_name else ""
    row = _mxu_state_row(data, instance_id, instance_name)
    if not isinstance(row, dict):
        return {"ok": True, "found": False, "running": False,
                "status": "", "url": url}
    state = row.get("task_run_state") or row.get("taskRunState") or {}
    if not isinstance(state, dict):
        state = {}
    running = row.get("is_running")
    if running is None:
        running = row.get("isRunning")
    if running is None:
        running = state.get("is_running", state.get("isRunning", False))
    status = (state.get("overall_status") or state.get("overallStatus")
              or row.get("overall_status") or row.get("overallStatus") or "")
    return {"ok": True, "found": True, "running": bool(running),
            "status": str(status), "url": url}


def effective_settings(app, settings=None):
    """把 app["daily"] 与运行时自动推断（MXU 实例名）合并成生效设置。"""
    key = app.get("key", "")
    base = store._clean_daily(app.get("daily"), key)
    if isinstance(settings, dict):
        base = store._clean_daily({**base, **settings}, key)
    if key in ("nte", "maaend") and not base.get("instance"):
        instances = mxu_instances(app)
        base["instance"] = _suggest_mxu_instance(app, instances)
    return base


def _maa_section(app):
    data = _read_json(maa_paths(app)["gui_new"])
    current = str(data.get("Current") or "Default")
    configurations = data.get("Configurations")
    if not isinstance(configurations, dict):
        configurations = {}
    section = configurations.get(current)
    if not isinstance(section, dict):
        section = {}
    return data, current, section


def maa_enabled_tasks(app):
    _data, _current, section = _maa_section(app)
    tasks = section.get("TaskQueue")
    names = []
    if isinstance(tasks, list):
        for task in tasks:
            if not isinstance(task, dict) or not task.get("IsEnable"):
                continue
            names.append(str(task.get("Name") or task.get("TaskType") or ""))
    return [name for name in names if name]


def _parse_hotkey_text(text):
    """解析 "Ctrl + Shift + Alt + L" 这类文本热键。"""
    parts = [part.strip() for part in re.split(r"[+,]", str(text or "")) if part.strip()]
    if not parts:
        return None
    key = parts[-1]
    modifiers = parts[:-1]
    if _vk_code(key) is None:
        return None
    return {"key": key, "modifiers": modifiers,
            "text": " + ".join(modifiers + [key])}


def maa_hotkey(app):
    """读取 LinkStart 热键；返回 {key, modifiers, text} 或 None。"""
    data, _current, section = _maa_section(app)
    gui = data.get("Gui") if isinstance(data.get("Gui"), dict) else {}
    hotkeys = gui.get("HotKeys") if isinstance(gui.get("HotKeys"), dict) else {}
    link = hotkeys.get("LinkStart")
    if isinstance(link, dict):
        key = str(link.get("Key") or "").strip()
        mods = str(link.get("Modifiers") or "").strip()
        if key and _vk_code(key) is not None:
            return {"key": key,
                    "modifiers": [part.strip() for part in mods.split(",") if part.strip()],
                    "text": (mods + " + " + key).strip(" +")}
    if isinstance(link, str) and link.strip():
        parsed = _parse_hotkey_text(link)
        if parsed:
            return parsed
    # 旧格式 gui.json：Global.HotKeys 是 JSON 字符串，Modifiers 为数字位掩码
    old = _read_json(maa_paths(app)["gui_old"])
    global_hotkeys = old.get("Global", {}).get("HotKeys") if isinstance(
        old.get("Global"), dict) else None
    if isinstance(global_hotkeys, str):
        try:
            global_hotkeys = json.loads(global_hotkeys)
        except (TypeError, ValueError):
            global_hotkeys = None
    if isinstance(global_hotkeys, dict):
        link = global_hotkeys.get("LinkStart")
        if isinstance(link, dict):
            key = str(link.get("Key") or "").strip()
            mask = link.get("Modifiers")
            mods = []
            if isinstance(mask, int) and not isinstance(mask, bool):
                for bit, name in ((1, "Alt"), (2, "Control"), (4, "Shift"), (8, "Win")):
                    if mask & bit:
                        mods.append(name)
            if key and _vk_code(key) is not None:
                return {"key": key, "modifiers": mods,
                        "text": " + ".join(mods + [key])}
    return None


# ------------------------------------------------------------------ 热键发送
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002


# ULONG_PTR is an unsigned pointer-sized integer, not a pointer to a DWORD.
ULONG_PTR = ctypes.c_size_t


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    # The mouse member determines INPUT's size even for keyboard-only calls.
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT),
                ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT),
                             ctypes.c_int]
user32.SendInput.restype = wintypes.UINT

_VK_SPECIAL = {"space": 0x20, "enter": 0x0D, "return": 0x0D, "tab": 0x09,
               "esc": 0x1B, "escape": 0x1B, "backspace": 0x08,
               "delete": 0x2E, "insert": 0x2D, "home": 0x24, "end": 0x23,
               "pageup": 0x21, "pagedown": 0x22, "up": 0x26, "down": 0x28,
               "left": 0x25, "right": 0x27}
_MODIFIER_VK = {"alt": 0x12, "control": 0x11, "ctrl": 0x11, "shift": 0x10,
                "win": 0x5B, "windows": 0x5B}


def _vk_code(key):
    """把配置里的单键转成虚拟键码；不支持返回 None。"""
    text = str(key or "").strip()
    if not text:
        return None
    low = text.lower()
    if low in _VK_SPECIAL:
        return _VK_SPECIAL[low]
    if len(text) == 1:
        ch = text.upper()
        if "A" <= ch <= "Z" or "0" <= ch <= "9":
            return ord(ch)
    match = re.fullmatch(r"F([1-9]|1[0-9]|2[0-4])", text.upper())
    if match:
        return 0x70 + int(match.group(1)) - 1
    return None


def _modifier_codes(modifiers):
    codes = []
    for modifier in modifiers or []:
        code = _MODIFIER_VK.get(str(modifier).strip().lower())
        if code:
            codes.append(code)
    return codes


def send_hotkey(hotkey):
    """发送系统级热键（SendInput）。返回 True/False。"""
    if not isinstance(hotkey, dict):
        return False
    vk = _vk_code(hotkey.get("key"))
    if vk is None:
        return False
    mods = _modifier_codes(hotkey.get("modifiers") or [])
    events = []
    for code in mods:
        events.append((code, 0))
    events.append((vk, 0))
    events.append((vk, KEYEVENTF_KEYUP))
    for code in reversed(mods):
        events.append((code, KEYEVENTF_KEYUP))
    array = (INPUT * len(events))()
    for index, (code, flags) in enumerate(events):
        array[index].type = INPUT_KEYBOARD
        array[index].u.ki.wVk = code
        array[index].u.ki.wScan = 0
        array[index].u.ki.dwFlags = flags
        array[index].u.ki.time = 0
        array[index].u.ki.dwExtraInfo = 0
    expected = len(events)
    struct_size = ctypes.sizeof(INPUT)
    ctypes.set_last_error(0)
    try:
        sent = user32.SendInput(expected, array, struct_size)
    except Exception as exc:
        last_error = ctypes.get_last_error()
        log_event("hotkey_send_error", sent=0, expected=expected,
                  struct_size=struct_size, last_error=last_error,
                  error_type=type(exc).__name__)
        return False
    # Capture immediately: logging or another Win32 call could change the error.
    last_error = ctypes.get_last_error()
    log_event("hotkey_send", sent=sent, expected=expected,
              struct_size=struct_size, last_error=last_error)
    if sent != expected:
        log_event("hotkey_send_error", sent=sent, expected=expected,
                  struct_size=struct_size, last_error=last_error,
                  error_type="incomplete_send")
    return sent == expected


# ------------------------------------------------------------------ 命令行拼装（QA-14）
def _needs_quote(text):
    return text == "" or any(ch in text for ch in ' \t\n\v"')


def _quote_arg(value, force=False):
    """把单个参数渲染成 Windows 命令行参数（必要时加双引号并转义）。

    规则与 CommandLineToArgvW / ShellExecuteW 一致：
    - 含空白/双引号/空串时必须整体加引号；
    - 引号前的反斜杠按 2n+1 转义，结尾反斜杠按 2n 转义；
    - force=True 时即使无特殊字符也加引号（脚本路径/实例名/配置名保持稳定可读）。

    Popen 列表模式直接使用 _build_command()["argv"]（原始 token，无需手工引号）。
    """
    text = "" if value is None else str(value)
    if not force and not _needs_quote(text):
        return text
    out = ['"']
    backslashes = 0
    for char in text:
        if char == "\\":
            backslashes += 1
            continue
        if char == '"':
            out.append("\\" * (backslashes * 2 + 1))
            out.append('"')
            backslashes = 0
            continue
        if backslashes:
            out.append("\\" * backslashes)
            backslashes = 0
        out.append(char)
    if backslashes:
        out.append("\\" * (backslashes * 2))
    out.append('"')
    return "".join(out)


def _build_command(exe, args, force_quote=()):
    """统一构建命令，避免手工 f-string 拼参数（QA-14）。

    返回 dict：
      exe           可执行文件
      argv          Popen 列表模式参数（[exe, *args]，原始 token）
      args          参数列表（原始 token）
      params        ShellExecuteW 的参数字符串（已按需加引号/转义）
      command_text  展示用完整命令行
    """
    exe = str(exe or "")
    args = [str(arg) for arg in (args or [])]
    forced = set(force_quote or ())
    rendered = [_quote_arg(arg, force=index in forced)
                for index, arg in enumerate(args)]
    params = " ".join(rendered)
    command_text = _quote_arg(exe, force=True)
    if params:
        command_text += " " + params
    return {"exe": exe, "argv": [exe] + args, "args": args,
            "params": params, "command_text": command_text}


def _normalize_extra_arg(token):
    """extra_args 单项：去掉外层成对引号（UI 用 shlex(posix=False) 写入时可能带引号）。"""
    text = str(token or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1]
    return text


def _extra_args(settings):
    cleaned = []
    for item in (settings.get("extra_args") or []):
        text = _normalize_extra_arg(item)
        if text:
            cleaned.append(text)
    return cleaned


# ------------------------------------------------------------------ 计划（dry-run / 校验）
def _app_snapshot_names():
    try:
        return store.snapshot_processes()
    except Exception:
        return set()


def _script_running(app):
    key = app.get("key", "")
    names = _app_snapshot_names()
    if key in store.PYAPPIFY_APPS:
        try:
            return store.launch_spec_running(app)
        except Exception:
            return False
    exe = app.get("script_exe") or ""
    basename = os.path.basename(exe).upper()
    return bool(basename) and basename in names


def _game_running(app):
    try:
        return bool(detector.detect_game_state(app).get("running"))
    except Exception:
        return False


def _plan_okww(app, settings, plan):
    """Shared OK task plan; retain historical mode/function names for callers."""
    paths = okww_paths(app)
    script_name = "ok-nte" if app.get("key") == "oknte" else "ok-ww"
    for field, label in (("exe", "pythonw.exe"), ("script", "main.py")):
        if not paths[field] or not os.path.isfile(paths[field]):
            plan["errors"].append(
                f"未找到 {script_name} 正式脚本的 {label}（{paths[field] or '路径未知'}）")
    if not paths["cwd"] or not os.path.isdir(paths["cwd"]):
        plan["errors"].append(f"未找到 {script_name} 的 working/repo 目录")
    if paths["daily_config"] and not os.path.isfile(paths["daily_config"]):
        plan["warnings"].append(
            f"{script_name} 的 {os.path.basename(paths['daily_config'])} 不存在："
            f"请先在 {script_name} 界面里配置并保存「每日任务」"
            "（可点卡片「启动脚本」打开脚本界面）")
    if _script_running(app):
        plan["errors"].append(
            f"{script_name} 正式脚本已在运行（同目录多实例会被强杀）。请先关闭脚本，或直接用当前实例操作")
    default_task = "DailyRoutineTask" if app.get("key") == "oknte" else "DailyTask"
    task = str(settings.get("task") or default_task).strip() or default_task
    plan.update({
        "mode": "okww",
        "exe": paths["exe"],
        "cwd": paths["cwd"],
        "log_path": paths["log"],
        "success_patterns": [OKWW_SUCCESS_MARKER],
        # The framework emits its exit marker even if a routine subtask failed.
        "failure_patterns": (["DailyRoutineTask:任务失败:",
                              "DailyRoutineTask:DailyRoutineTask error",
                              "执行结束, 存在失败", "Finished with failures",
                              "状态: ❌ 异常中断", "Status: ❌ Interrupted"]
                             if app.get("key") == "oknte" else []),
        "settle_seconds": 0,
    })
    # QA-14：统一用列表 + _quote_arg 构建，-t 值含空格/引号也能正确转义
    args = [paths["script"], "-t", task, "-e"] + _extra_args(settings)
    command = _build_command(paths["exe"], args, force_quote={0})
    plan["params"] = command["params"]
    plan["argv"] = command["argv"]
    plan["args"] = command["args"]
    plan["command_text"] = command["command_text"]
    plan["notes"].append(f"完成判定：进程退出 + 日志出现「{OKWW_SUCCESS_MARKER}」")
    if app.get("key") == "oknte":
        plan["notes"].append(
            "会识别已知的日常任务失败日志；外层结束标记仍不能保证每个子任务成功，请核对 ok-nte 日常任务报告")
    plan["notes"].append(f"将以管理员权限启动（UAC）；不注入环境变量（与 {script_name} 官方计划任务一致）")
    if not settings.get("close_after", True):
        plan["notes"].append(f"（-e 为完成判定所需，任务成功后 {script_name} 仍会关闭游戏与自身）")


def _plan_maa(app, settings, plan):
    paths = maa_paths(app)
    if not paths["exe"] or not os.path.isfile(paths["exe"]):
        plan["errors"].append("未找到 MAA.exe")
        return
    hotkey = maa_hotkey(app)
    if not hotkey:
        plan["errors"].append(
            "没有读到可用的 LinkStart 热键：请在 MAA 设置→热键 中设置「开始任务」热键，"
            "或开启「启动后直接运行」；可点卡片「启动脚本」打开 MAA 设置")
    enabled = maa_enabled_tasks(app)
    if not enabled:
        plan["errors"].append(
            "MAA 任务队列没有已勾选的任务：请打开 MAA 勾选日常任务后再试"
            "（可点卡片「启动脚本」打开 MAA）")
    else:
        daily_like = [name for name in enabled
                      if any(hint in name for hint in MAA_DAILY_TASK_HINTS)]
        if not daily_like:
            plan["warnings"].append(
                "MAA 当前启用的任务不像日常任务：" + "、".join(enabled)
                + "；一键清日常会执行该队列，请确认")
    if _script_running(app):
        plan["notes"].append("MAA 已在运行：本次只发送 LinkStart 热键，不接管/不结束该进程")
        plan["attach"] = True
    plan.update({
        "mode": "maa",
        "exe": paths["exe"],
        "cwd": os.path.dirname(paths["exe"]),
        "log_path": paths["log"],
        "hotkey": hotkey,
        "success_patterns": list(MAA_SUCCESS_MARKERS),
        "failure_patterns": list(MAA_FAILURE_MARKERS),
        "stop_patterns": list(MAA_STOP_MARKERS),
        "enabled_tasks": enabled,
    })
    # QA-14：--config 值统一加引号；参数用列表构建，Popen/ShellExecute 两种渲染一致
    args = ["--skip-startup-auto-run"]
    force_quote = set()
    config_name = str(settings.get("config") or "").strip()
    if config_name:
        args += ["--config", config_name]
        force_quote.add(len(args) - 1)
    args += _extra_args(settings)
    command = _build_command(paths["exe"], args, force_quote=force_quote)
    plan["params"] = command["params"]
    plan["argv"] = command["argv"]
    plan["args"] = command["args"]
    plan["command_text"] = command["command_text"]
    if hotkey:
        plan["notes"].append(
            f"就绪后发送全局热键 {hotkey['text']}；完成判定：gui.log 出现「任务已全部完成！」")
    plan["notes"].append(
        "MAA 若已在运行则只发热键；否则以管理员权限启动（UAC）")


def _plan_mxu(app, settings, plan):
    paths = mxu_paths(app)
    if not paths["exe"] or not os.path.isfile(paths["exe"]):
        plan["errors"].append(f"未找到 {os.path.basename(paths['exe']) or 'MXU'} 程序")
        return
    instances = mxu_instances(app)
    names = [row["name"] for row in instances]
    instance = str(settings.get("instance") or "").strip()
    row = next((item for item in instances if item["name"] == instance), None)
    if not names:
        plan["errors"].append(
            "没有读到 MXU 实例配置：请先在脚本里创建实例并配置日常任务"
            "（可点卡片「启动脚本」打开脚本界面）")
    elif not instance:
        plan["errors"].append(
            "未选择 MXU 实例：请在一键清日常设置里选择实例（可用："
            + "、".join(names) + "）")
    elif row is None:
        plan["errors"].append(
            f"实例「{instance}」不存在：请到脚本里创建/选择实例（可用："
            + "、".join(names) + "；可点卡片「启动脚本」打开脚本界面）")
    else:
        if row["enabled_count"] <= 0:
            plan["errors"].append(
                f"实例「{instance}」没有启用任何任务：请先在该实例里勾选日常任务")
        elif row["enabled_count"] <= 1:
            plan["warnings"].append(
                f"实例「{instance}」只启用了 {row['enabled_count']} 个任务，请确认这就是日常任务")
        if not row["has_launch_pretask"] and not _game_running(app):
            plan["warnings"].append(
                "该实例没有 LaunchGamePC 前置任务且游戏未运行，任务可能失败")
    if _script_running(app):
        plan["errors"].append(
            f"{app.get('script') or '脚本'} 已在运行：请先关闭脚本再执行清日常")
    # QA-14：实例名统一加引号，参数列表构建（Popen/ShellExecute 两种渲染一致）
    args = ["--autostart"]
    force_quote = set()
    if instance:
        args += ["--instance", instance]
        force_quote.add(len(args) - 1)
    args.append("--quit-after-run")
    args += _extra_args(settings)
    command = _build_command(paths["exe"], args, force_quote=force_quote)
    plan.update({
        "mode": "mxu",
        "exe": paths["exe"],
        "cwd": os.path.dirname(paths["exe"]),
        "log_path": paths["log"],
        "success_patterns": [],
        "failure_patterns": [],
        "settle_seconds": MXU_SETTLE_SECONDS,
        "params": command["params"],
        "argv": command["argv"],
        "args": command["args"],
        "command_text": command["command_text"],
        "_app": app,
    })
    plan["notes"].append("完成判定：MXU 进程退出（--quit-after-run，退出码恒 0，不区分成败）")
    plan["notes"].append("将以管理员权限启动（UAC）；结束时只结束本次启动的 MXU 进程")
    if not settings.get("close_after", True):
        plan["notes"].append("（--quit-after-run 为完成判定所需，任务结束后 MXU 仍会退出）")


def _plan_mxu_ui(app, settings, plan):
    """异环：打开 MaaNTE UI → 发送开始任务热键 → 等待任务结束。"""
    paths = mxu_paths(app)
    if not paths["exe"] or not os.path.isfile(paths["exe"]):
        plan["errors"].append(
            f"未找到 {os.path.basename(paths['exe']) or 'MaaNTE'} 程序")
        return
    if _script_running(app):
        plan["errors"].append(
            f"{app.get('script') or '脚本'} 已在运行：请先关闭脚本再执行清日常")
    instances = mxu_instances(app)
    names = [row["name"] for row in instances]
    instance = str(settings.get("instance") or "").strip()
    row = next((item for item in instances if item["name"] == instance), None)
    if not names:
        plan["errors"].append(
            "没有读到 MXU 实例配置：请先在脚本里创建实例并配置日常任务")
    elif not instance:
        plan["errors"].append(
            "未选择 MXU 实例：请在一键清日常设置里选择实例（可用："
            + "、".join(names) + "）")
    elif row is None:
        plan["errors"].append(
            f"实例「{instance}」不存在：请到脚本里创建/选择实例（可用："
            + "、".join(names) + "）")
    elif row["enabled_count"] <= 0:
        plan["errors"].append(
            f"实例「{instance}」没有启用任何任务：请先在该实例里勾选日常任务")
    hotkey = mxu_ui_hotkey(app)
    log_path = mxu_latest_log(app)
    port = mxu_web_port(app)
    command = _build_command(paths["exe"], [])
    plan.update({
        "mode": "mxu_ui",
        "exe": paths["exe"],
        "cwd": paths["base"],
        "log_path": log_path,
        "success_patterns": list(MXU_UI_DONE_MARKERS),
        "failure_patterns": list(MXU_UI_FAIL_MARKERS),
        "settle_seconds": 0,
        "hotkey": hotkey,
        "instance": instance,
        "instance_id": mxu_instance_id(app, instance),
        "web_port": port,
        "params": "",
        "argv": [paths["exe"]],
        "args": [],
        "command_text": command["command_text"],
        "_app": app,
    })
    if hotkey:
        plan["notes"].append(f"打开 MaaNTE 后发送开始任务热键：{hotkey['text']}")
    else:
        plan["warnings"].append(
            "未读到 MaaNTE「开始任务」热键或 globalEnabled=false："
            "打开后需要手动点击开始任务（不会静默成功）")
        plan["notes"].append(MXU_UI_NOTE)
    plan["notes"].append(
        f"等待任务结束：优先轮询 http://127.0.0.1:{port}/maa/state"
        f"（实例 {instance}）；HTTP 不可用回退 debug 日志")
    plan["notes"].append(
        "任务完成后保留 MaaNTE 窗口（不结束本次启动的进程）；"
        "后续清日常若需要脚本会提示先关闭")
    plan["notes"].append(
        "将以管理员权限启动 MaaNTE（正常 UI，不带 --autostart/--quit-after-run）")


def plan_for(app, settings=None):
    """生成某张卡片的清日常执行计划（不启动任何进程）。"""
    app = app or {}
    plan = {
        "key": app.get("key", ""),
        "game": app.get("game", ""),
        "script": app.get("script", ""),
        "settings": effective_settings(app, settings),
        "errors": [], "warnings": [], "notes": [],
        "mode": "", "exe": "", "params": "", "cwd": "", "command_text": "",
        "argv": [], "args": [],
        "log_path": "", "success_patterns": [], "failure_patterns": [],
        "timeout_min": 120, "close_after": False,
        "elevate": True,
    }
    plan["timeout_min"] = int(plan["settings"].get("timeout_min") or 120)
    plan["close_after"] = bool(plan["settings"].get("close_after"))
    key = app.get("key", "")
    if key in store.PYAPPIFY_APPS:
        _plan_okww(app, plan["settings"], plan)
    elif key == "maa":
        _plan_maa(app, plan["settings"], plan)
    elif key == "nte":
        _plan_mxu_ui(app, plan["settings"], plan)
    elif key == "maaend":
        _plan_mxu(app, plan["settings"], plan)
    else:
        plan["errors"].append("该卡片暂不支持一键清日常")
    plan["ok"] = not plan["errors"]
    return plan


def describe_plan(plan, indent="  "):
    """dry-run / UI 预览用的可读文本。"""
    if not isinstance(plan, dict):
        return ""
    lines = [f"[{plan.get('game') or plan.get('key')}]"]
    lines.append(f"{indent}命令: {plan.get('command_text') or '(未生成)'}")
    if plan.get("cwd"):
        lines.append(f"{indent}工作目录: {plan['cwd']}")
    if plan.get("log_path"):
        lines.append(f"{indent}日志: {plan['log_path']}")
    lines.append(f"{indent}超时: {plan.get('timeout_min')} 分钟")
    for note in plan.get("notes") or []:
        lines.append(f"{indent}· {note}")
    for warning in plan.get("warnings") or []:
        lines.append(f"{indent}⚠ {warning}")
    for error in plan.get("errors") or []:
        lines.append(f"{indent}✗ {error}")
    return "\n".join(lines)


def dry_run(apps, order=None, include_disabled=True):
    """只拼装计划、不启动进程；返回计划列表。"""
    by_key = {app.get("key"): app for app in apps or []}
    keys = [key for key in (order or store.DEFAULT_DAILY_ORDER) if key in by_key]
    if not keys:
        keys = [app.get("key") for app in apps or []]
    plans = []
    for key in keys:
        app = by_key[key]
        if not include_disabled and not (app.get("daily") or {}).get("enabled", True):
            continue
        plans.append(plan_for(app))
    return plans


# ------------------------------------------------------------------ 执行
def _emit(on_event, **event):
    # Deliberate allowlist: never copy plans, config, external log tails or notes.
    kind = event.get("type")
    if kind == "done":
        result = event.get("result") or {}
        state = result.get("state")
        fields = {name: result.get(name) for name in
                  ("key", "state", "pid", "started_at", "ended_at", "duration")}
        fields["success"] = state == FINISHED
        log_event("daily_result", **fields)
        if state in (STOPPED, TIMEOUT):
            log_event("daily_" + state, **fields)
    elif kind == "state":
        log_event("daily_state", **{name: event.get(name)
                                    for name in ("key", "state", "pid")})
    if not on_event:
        return
    try:
        on_event(event)
    except Exception:
        pass


def _stop_requested(stop_event):
    return bool(stop_event is not None and stop_event.is_set())


def _base_result(plan, state, reason="", pid=None, started=None,
                 log_watcher=None, notes=None):
    ended = time.time()
    return {
        "key": plan.get("key", ""),
        "game": plan.get("game", ""),
        "state": state,
        "state_label": STATE_LABELS.get(state, state),
        "reason": reason,
        "pid": pid,
        "started_at": started,
        "ended_at": ended,
        "duration": round(ended - started, 1) if started else 0,
        "command": plan.get("command_text", ""),
        "log_tail": log_watcher.tail(15) if log_watcher else "",
        "notes": list(plan.get("notes") or []) + list(notes or []),
    }


def _read_success(text, patterns):
    for pattern in patterns:
        if pattern and pattern in text:
            return True
    return False


def _wait_handle(handle, stop_event, timeout_ms=300):
    """带停止检查的等待；返回 'exit' / 'stop' / 'running'。"""
    if _stop_requested(stop_event):
        return "stop"
    if handle.wait(timeout_ms):
        return "exit"
    return "running"


def _run_okww(plan, stop_event, on_event, launcher):
    started = time.time()
    watcher = LogWatcher(plan.get("log_path"))
    try:
        handle = launcher(plan["exe"], plan["params"], plan["cwd"])
    except DailyError as exc:
        result = _base_result(plan, FAILED, str(exc), started=started,
                              log_watcher=watcher)
        _emit(on_event, type="done", result=result)
        return result
    except Exception as exc:      # 启动层异常不静默
        result = _base_result(plan, FAILED, f"启动失败：{exc}",
                              started=started, log_watcher=watcher)
        _emit(on_event, type="done", result=result)
        return result
    _emit(on_event, type="state", key=plan["key"], state=RUNNING,
          pid=handle.pid, game=plan.get("game"))
    seen_success = False
    error_line = ""
    seen_failure = False
    deadline = _now() + plan["timeout_min"] * 60
    result = None
    try:
        while True:
            text = watcher.read()
            if OKWW_SUCCESS_MARKER in text:
                seen_success = True
            if _read_success(text, plan.get("failure_patterns") or []):
                seen_failure = True
            if not error_line:
                for line in text.splitlines():
                    if re.search(r"\bERROR\b|Traceback", line):
                        error_line = line.strip()
                        break
            wait = _wait_handle(handle, stop_event, 400)
            if wait == "stop":
                handle.terminate()
                result = _base_result(plan, STOPPED, "用户停止，已结束本次启动的进程",
                                      pid=handle.pid, started=started,
                                      log_watcher=watcher)
                break
            if wait == "exit":
                final_text = watcher.read()
                seen_failure = seen_failure or _read_success(
                    final_text, plan.get("failure_patterns") or [])
                if not seen_failure and (seen_success or OKWW_SUCCESS_MARKER in watcher.tail(30)):
                    result = _base_result(plan, FINISHED, "每日任务已完成",
                                          pid=handle.pid, started=started,
                                          log_watcher=watcher)
                else:
                    reason = ("日常任务包含失败项，请检查脚本日志" if seen_failure
                              else "脚本已退出，但日志未出现成功标记")
                    if error_line:
                        reason += f"（{error_line[:120]}）"
                    result = _base_result(plan, FAILED, reason, pid=handle.pid,
                                          started=started, log_watcher=watcher)
                break
            if _now() > deadline:
                handle.terminate()
                result = _base_result(
                    plan, TIMEOUT,
                    f"超时 {plan['timeout_min']} 分钟，已结束本次启动的进程",
                    pid=handle.pid, started=started, log_watcher=watcher)
                break
            _sleep(POLL_SECONDS)
    finally:
        handle.close()
        if result:
            _emit(on_event, type="done", result=result)
    return result


def _run_mxu(plan, stop_event, on_event, launcher):
    """终末地 MXU：--autostart/--quit-after-run，按进程退出判定完成。"""
    started = time.time()
    watcher = LogWatcher(plan.get("log_path"))
    try:
        handle = launcher(plan["exe"], plan["params"], plan["cwd"])
    except DailyError as exc:
        result = _base_result(plan, FAILED, str(exc), started=started,
                              log_watcher=watcher)
        _emit(on_event, type="done", result=result)
        return result
    except Exception as exc:
        result = _base_result(plan, FAILED, f"启动失败：{exc}", started=started,
                              log_watcher=watcher)
        _emit(on_event, type="done", result=result)
        return result
    _emit(on_event, type="state", key=plan["key"], state=RUNNING,
          pid=handle.pid, game=plan.get("game"))
    deadline = _now() + plan["timeout_min"] * 60
    result = None
    try:
        while True:
            watcher.read()
            wait = _wait_handle(handle, stop_event, 400)
            if wait == "stop":
                handle.terminate()
                result = _base_result(plan, STOPPED, "用户停止，已结束本次启动的进程",
                                      pid=handle.pid, started=started,
                                      log_watcher=watcher)
                break
            if wait == "exit":
                _sleep(plan.get("settle_seconds") or 0)
                watcher.read()
                hint = _mxu_log_hint(watcher.tail(40))
                result = _base_result(plan, FINISHED,
                                      "MXU 进程已退出（--quit-after-run）"
                                      + (f"；{hint}" if hint else ""),
                                      pid=handle.pid, started=started,
                                      log_watcher=watcher)
                break
            if _now() > deadline:
                handle.terminate()
                result = _base_result(
                    plan, TIMEOUT,
                    f"超时 {plan['timeout_min']} 分钟，已结束本次启动的 MXU 进程",
                    pid=handle.pid, started=started, log_watcher=watcher)
                break
            _sleep(POLL_SECONDS)
    finally:
        handle.close()
        if result:
            _emit(on_event, type="done", result=result)
    return result


def _mxu_ui_window(pid=None):
    try:
        windows = detector.snapshot_windows(force=True)
    except Exception:
        return None
    for win in windows:
        try:
            win_pid = int(win.get("pid") or 0)
        except (TypeError, ValueError):
            win_pid = 0
        title = str(win.get("title") or "").lower()
        if pid and win_pid == int(pid):
            return win
        if not pid and any(word in title for word in ("maante", "maa", "mxu")):
            return win
    return None


def _mxu_marker_hit(text, markers):
    if not text:
        return ""
    low = text.lower()
    for marker in markers:
        if marker.lower() in low:
            return marker
    return ""


class _MxuStartupReadiness:
    """Snapshot BEFORE launch; only fresh debug bytes can establish readiness.

    Keep the completion watcher at the consumed offset, including logs first
    created after launch or a date rollover. No start/toggle hotkey is sent here.
    """

    def __init__(self, plan, watcher):
        self.watcher = watcher
        self.debug = os.path.join(plan.get("cwd") or "", "debug")
        if watcher.path:
            self.debug = os.path.dirname(watcher.path)
        self.readers = {}
        self.buffers = {}
        self.seen = set()
        for path in self._paths():
            self.readers[path] = LogWatcher(path)
        if watcher.path:
            reader = LogWatcher(watcher.path)
            reader.offset = watcher.offset
            self.readers[watcher.path] = reader

    def _paths(self):
        try:
            return [os.path.join(self.debug, name)
                    for name in os.listdir(self.debug)
                    if name.lower().endswith(".log")
                    and not name.lower().startswith("maafw")
                    and os.path.isfile(os.path.join(self.debug, name))]
        except OSError:
            return []

    def poll(self):
        for path in self._paths():
            if path not in self.readers:
                reader = LogWatcher(path)
                reader.offset = 0  # new since the pre-launch snapshot
                self.readers[path] = reader
        for path, reader in self.readers.items():
            text = reader.read()
            if not text:
                continue
            text = self.buffers.get(path, "") + text
            for marker in ("全局快捷键已注册", "加载完成"):
                if marker in text:
                    self.seen.add(marker)
            self.buffers[path] = text[-128:]
            # Transfer rather than reset: resetting here would discard bytes
            # appended between the read and the eventual start hotkey.
            self.watcher.path = path
            self.watcher.offset = reader.offset
            self.watcher.tail_lines = list(reader.tail_lines)
        return len(self.seen) == 2

    def wait(self, stop_event, on_event, grace=15, timeout=30):
        """Return ready/fallback/stopped/timeout; polling is cancellable."""
        started = _now()
        _emit(on_event, type="log", text="等待 MaaNTE 本次启动的热键注册及加载完成日志")
        while True:
            if _stop_requested(stop_event):
                return "stopped"
            if self.poll():
                _emit(on_event, type="log", text="MaaNTE 本次启动已就绪：全局快捷键已注册、加载完成")
                return "ready"
            elapsed = _now() - started
            if not self.seen and elapsed >= grace:
                _emit(on_event, type="log", text=(
                    f"MaaNTE 未提供新的启动就绪标记；已等待 {grace} 秒，"
                    "使用兼容宽限回退（未验证就绪），仅发送一次开始热键"))
                return "fallback"
            if elapsed >= timeout:
                return "timeout"
            _sleep(0.25)


def _run_mxu_ui(plan, stop_event, on_event, launcher):
    """异环：打开 MaaNTE UI → 发送开始任务热键 → HTTP/日志等待结束。"""
    started = time.time()
    watcher = LogWatcher(plan.get("log_path"))
    readiness = _MxuStartupReadiness(plan, watcher)
    app = plan.get("_app") or {}
    handle = None
    try:
        handle = launcher(plan["exe"], "", plan["cwd"])
    except DailyError as exc:
        result = _base_result(plan, FAILED, str(exc), started=started,
                              log_watcher=watcher)
        _emit(on_event, type="done", result=result)
        return result
    except Exception as exc:
        result = _base_result(plan, FAILED, f"启动失败：{exc}", started=started,
                              log_watcher=watcher)
        _emit(on_event, type="done", result=result)
        return result
    pid = handle.pid
    _emit(on_event, type="state", key=plan["key"], state=STARTING,
          pid=pid, game=plan.get("game"))
    window = None
    deadline = _now() + 60
    while _now() < deadline:
        if _stop_requested(stop_event):
            handle.terminate()
            result = _base_result(plan, STOPPED, "用户停止", pid=pid,
                                  started=started, log_watcher=watcher)
            handle.close()
            _emit(on_event, type="done", result=result)
            return result
        window = _mxu_ui_window(pid)
        if window:
            break
        _sleep(0.5)
    if not window:
        handle.terminate()
        handle.close()
        result = _base_result(plan, FAILED, "未检测到 MaaNTE 主窗口",
                              pid=pid, started=started, log_watcher=watcher)
        _emit(on_event, type="done", result=result)
        return result
    ready = readiness.wait(stop_event, on_event)
    log_event("mxu_startup_readiness", key=plan.get("key"),
              pid=pid, outcome=ready)
    if ready in ("stopped", "timeout"):
        handle.terminate()
        handle.close()
        result = _base_result(
            plan, STOPPED if ready == "stopped" else FAILED,
            "用户停止" if ready == "stopped" else
            "MaaNTE 启动就绪超时：未同时检测到热键注册和加载完成；未发送开始热键",
            pid=pid, started=started, log_watcher=watcher)
        _emit(on_event, type="done", result=result)
        return result
    try:
        detector.focus_window(window.get("hwnd"))
    except Exception:
        pass
    _sleep(0.4)
    if _stop_requested(stop_event):
        handle.terminate()
        handle.close()
        result = _base_result(plan, STOPPED, "用户停止", pid=pid,
                              started=started, log_watcher=watcher)
        _emit(on_event, type="done", result=result)
        return result
    hotkey = plan.get("hotkey")
    sent = False
    if hotkey:
        try:
            sent = send_hotkey(hotkey)
        except Exception:
            sent = False
    if not sent:
        text = ("未找到/无法发送 MaaNTE「开始任务」热键："
                "请手动点击 MaaNTE 中的开始任务")
        _emit(on_event, type="manual", text=text)
        handle.close()
        result = _base_result(plan, FAILED, text, pid=pid,
                              started=started, log_watcher=watcher)
        _emit(on_event, type="done", result=result)
        return result
    _emit(on_event, type="state", key=plan["key"], state=RUNNING,
          pid=pid, game=plan.get("game"))
    _emit(on_event, type="log", text=f"已发送开始任务热键 {hotkey['text']}")
    timeout_deadline = _now() + plan["timeout_min"] * 60
    http_fail_since = None
    use_http = True
    http_started = False
    result = None
    try:
        while True:
            if use_http:
                state = mxu_http_state(app, plan.get("instance") or "")
                if state.get("ok"):
                    http_fail_since = None
                    status = str(state.get("status") or "").lower()
                    if state.get("running"):
                        if not http_started:
                            http_started = True
                            _emit(on_event, type="log",
                                  text="HTTP 检测到任务正在运行")
                    elif http_started:
                        ok_state = "fail" not in status and \
                            "error" not in status
                        result = _base_result(
                            plan, FINISHED if ok_state else FAILED,
                            f"任务结束（HTTP overall_status={status or 'unknown'}）；"
                            "MaaNTE 窗口保留", pid=pid, started=started,
                            log_watcher=watcher)
                        break
                    elif status in ("succeeded", "failed", "stopped"):
                        result = _base_result(
                            plan, FINISHED if status != "failed" else FAILED,
                            f"任务已结束（HTTP overall_status={status}）；"
                            "MaaNTE 窗口保留", pid=pid, started=started,
                            log_watcher=watcher)
                        break
                else:
                    if http_fail_since is None:
                        http_fail_since = _now()
                    elif _now() - http_fail_since >= MXU_HTTP_FALLBACK_SECONDS:
                        use_http = False
                        _emit(on_event, type="log",
                              text="HTTP 状态不可用，改用 MaaNTE debug 日志判定")
            text = watcher.read()
            if text:
                if _mxu_marker_hit(text, MXU_UI_START_MARKERS):
                    http_started = True
                done = _mxu_marker_hit(text, MXU_UI_DONE_MARKERS)
                if done:
                    result = _base_result(
                        plan, FINISHED,
                        f"日志检测到任务结束标记「{done}」；MaaNTE 窗口保留",
                        pid=pid, started=started, log_watcher=watcher)
                    break
                failed_marker = _mxu_marker_hit(text, MXU_UI_FAIL_MARKERS)
                if failed_marker:
                    result = _base_result(
                        plan, FAILED,
                        f"日志检测到失败标记「{failed_marker}」",
                        pid=pid, started=started, log_watcher=watcher)
                    break
            if _stop_requested(stop_event):
                handle.terminate()
                result = _base_result(plan, STOPPED,
                                      "用户停止，已结束本次启动的 MaaNTE",
                                      pid=pid, started=started,
                                      log_watcher=watcher)
                break
            wait = _wait_handle(handle, stop_event, 400)
            if wait == "exit":
                result = _base_result(
                    plan, FAILED, "MaaNTE 已退出，但未检测到任务结束",
                    pid=pid, started=started, log_watcher=watcher)
                break
            if _now() > timeout_deadline:
                handle.terminate()
                result = _base_result(
                    plan, TIMEOUT,
                    f"超时 {plan['timeout_min']} 分钟，已结束本次启动的 MaaNTE",
                    pid=pid, started=started, log_watcher=watcher)
                break
            _sleep(1)
    finally:
        handle.close()
        if result:
            _emit(on_event, type="done", result=result)
    return result


def _mxu_log_hint(text):
    if not text:
        return ""
    for line in reversed(text.splitlines()):
        low = line.lower()
        if "error" in low or "fail" in low or "异常" in line:
            return f"日志提示：{line.strip()[:120]}"
    return ""


def _maa_window_ready(pid=None):
    try:
        windows = detector.snapshot_windows(force=True)
    except Exception:
        return False
    for win in windows:
        if pid and int(win.get("pid") or 0) == int(pid):
            return True
        if pid:
            continue
        title = (win.get("title") or "").lower()
        if "maa" in title or "maassistant" in title:
            return True
    return False


def _run_maa(plan, stop_event, on_event, launcher):
    started = time.time()
    watcher = LogWatcher(plan.get("log_path"))
    handle = None
    pid = None
    attach = bool(plan.get("attach"))
    if not attach:
        try:
            handle = launcher(plan["exe"], plan["params"], plan["cwd"])
            pid = handle.pid
        except DailyError as exc:
            result = _base_result(plan, FAILED, str(exc), started=started,
                                  log_watcher=watcher)
            _emit(on_event, type="done", result=result)
            return result
        except Exception as exc:
            result = _base_result(plan, FAILED, f"启动失败：{exc}",
                                  started=started, log_watcher=watcher)
            _emit(on_event, type="done", result=result)
            return result
        _emit(on_event, type="state", key=plan["key"], state=STARTING,
              pid=pid, game=plan.get("game"))
        ready_deadline = _now() + MAA_READY_TIMEOUT
        ready = False
        while _now() < ready_deadline:
            text = watcher.read()
            if "MaaAssistantArknights GUI started" in text or _maa_window_ready(pid):
                ready = True
                break
            wait = _wait_handle(handle, stop_event, 200)
            if wait == "stop":
                handle.terminate()
                result = _base_result(plan, STOPPED, "用户停止，已结束本次启动的 MAA",
                                      pid=pid, started=started, log_watcher=watcher)
                handle.close()
                _emit(on_event, type="done", result=result)
                return result
            if wait == "exit":
                result = _base_result(plan, FAILED, "MAA 启动后异常退出",
                                      pid=pid, started=started, log_watcher=watcher)
                handle.close()
                _emit(on_event, type="done", result=result)
                return result
            _sleep(POLL_SECONDS)
        if not ready:
            handle.terminate()
            result = _base_result(
                plan, FAILED,
                f"MAA 在 {MAA_READY_TIMEOUT} 秒内未就绪，已结束本次启动的 MAA",
                pid=pid, started=started, log_watcher=watcher)
            handle.close()
            _emit(on_event, type="done", result=result)
            return result
    else:
        _emit(on_event, type="state", key=plan["key"], state=RUNNING,
              pid=None, game=plan.get("game"))
    # 发送热键
    hotkey = plan.get("hotkey")
    sent = False
    for _attempt in range(MAA_HOTKEY_RETRY):
        if _stop_requested(stop_event):
            break
        if send_hotkey(hotkey):
            sent = True
            break
        _sleep(0.5)
    if not sent:
        if handle:
            handle.terminate()
            handle.close()
        if _stop_requested(stop_event):
            result = _base_result(plan, STOPPED,
                                  "用户停止，已结束本次启动的 MAA",
                                  pid=pid, started=started, log_watcher=watcher)
        else:
            result = _base_result(
                plan, FAILED,
                "发送 LinkStart 热键失败：请在 MAA 界面手动开始，或检查热键是否被其它程序占用",
                pid=pid, started=started, log_watcher=watcher)
        _emit(on_event, type="done", result=result)
        return result
    _emit(on_event, type="state", key=plan["key"], state=RUNNING,
          pid=pid, game=plan.get("game"))
    deadline = _now() + plan["timeout_min"] * 60
    result = None
    try:
        while True:
            text = watcher.read()
            if _read_success(text, plan.get("success_patterns") or []):
                if plan.get("close_after") and handle:
                    handle.terminate()
                result = _base_result(plan, FINISHED, "每日任务已完成",
                                      pid=pid, started=started,
                                      log_watcher=watcher)
                break
            failed = next((marker for marker in plan.get("failure_patterns") or []
                           if marker in text), "")
            if failed:
                result = _base_result(plan, FAILED, f"MAA 任务出错（日志：{failed.strip()}）",
                                      pid=pid, started=started,
                                      log_watcher=watcher)
                break
            stopped_marker = next((marker for marker in plan.get("stop_patterns") or []
                                   if marker in text), "")
            if stopped_marker:
                result = _base_result(plan, STOPPED, "MAA 任务已停止（日志：已停止）",
                                      pid=pid, started=started,
                                      log_watcher=watcher)
                break
            if _stop_requested(stop_event):
                if handle:
                    handle.terminate()
                    reason = "用户停止，已结束本次启动的 MAA"
                else:
                    reason = "用户停止监控（MAA 仍在运行，请在其界面里停止任务）"
                result = _base_result(plan, STOPPED, reason, pid=pid,
                                      started=started, log_watcher=watcher)
                break
            if handle and handle.wait(200):
                watcher.read()
                if _read_success(watcher.tail(40),
                                 plan.get("success_patterns") or []):
                    result = _base_result(plan, FINISHED, "每日任务已完成",
                                          pid=pid, started=started,
                                          log_watcher=watcher)
                else:
                    result = _base_result(plan, FAILED, "MAA 进程已退出（任务未完成）",
                                          pid=pid, started=started,
                                          log_watcher=watcher)
                break
            if _now() > deadline:
                if handle:
                    handle.terminate()
                    reason = f"超时 {plan['timeout_min']} 分钟，已结束本次启动的 MAA"
                else:
                    reason = (f"超时 {plan['timeout_min']} 分钟（MAA 非 Hub 启动，未结束进程）")
                result = _base_result(plan, TIMEOUT, reason, pid=pid,
                                      started=started, log_watcher=watcher)
                break
            _sleep(POLL_SECONDS)
    finally:
        if handle:
            handle.close()
        if result:
            _emit(on_event, type="done", result=result)
    return result


def run(app, settings=None, *, dry_run=False, stop_event=None, on_event=None,
        launcher=None):
    """执行单个游戏的清日常；dry_run=True 时只返回计划，不启动进程。"""
    plan = plan_for(app, settings)
    log_event("daily_plan", key=plan.get("key"), mode=plan.get("mode"),
              command_path=plan.get("exe"), timeout_min=plan.get("timeout_min"),
              dry_run=bool(dry_run), success=bool(plan.get("ok")),
              error_count=len(plan.get("errors") or []),
              warning_count=len(plan.get("warnings") or []))
    if dry_run:
        return {
            "key": plan["key"], "game": plan["game"], "state": DRY_RUN,
            "state_label": STATE_LABELS[DRY_RUN], "plan": plan,
            "command": plan.get("command_text", ""),
            "reason": "预演：未启动任何进程",
        }
    if plan.get("errors"):
        result = _base_result(plan, FAILED,
                              "前置检查未通过：" + "；".join(plan["errors"]))
        _emit(on_event, type="done", result=result)
        return result
    _emit(on_event, type="state", key=plan["key"], state=STARTING,
          game=plan.get("game"))
    launcher = launcher or launch_elevated
    mode = plan.get("mode")
    log_event("daily_start", key=plan.get("key"), mode=mode,
              command_path=plan.get("exe"))
    try:
        if mode == "okww":
            return _run_okww(plan, stop_event, on_event, launcher)
        if mode == "maa":
            return _run_maa(plan, stop_event, on_event, launcher)
        if mode == "mxu":
            return _run_mxu(plan, stop_event, on_event, launcher)
        if mode == "mxu_ui":
            return _run_mxu_ui(plan, stop_event, on_event, launcher)
    except Exception as exc:       # 兜底：执行层异常不静默崩溃
        get_logger("daily").exception("daily_exception")
        result = _base_result(plan, FAILED, f"执行异常：{exc}")
        _emit(on_event, type="done", result=result)
        return result
    result = _base_result(plan, FAILED, "不支持的模式")
    _emit(on_event, type="done", result=result)
    return result


# ------------------------------------------------------------------ 顺序队列
class DailyQueue:
    """按 config 顺序串行执行清日常；线程安全地暴露进度快照。"""

    def __init__(self, apps, order=None, *, launcher=None, on_event=None,
                 dry_run=False):
        self.apps = list(apps or [])
        self.by_key = {app.get("key"): app for app in self.apps}
        if not order:
            order = store.DEFAULT_DAILY_ORDER
        self.order = [key for key in order if key in self.by_key]
        self.launcher = launcher
        self.on_event = on_event
        self.dry_run = bool(dry_run)
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = None
        self._state = IDLE
        self._current = None
        self._results = []
        self._index = -1

    # -------------------------------------------------- 状态
    def snapshot(self):
        with self._lock:
            return {
                "state": self._state,
                "state_label": STATE_LABELS.get(self._state, self._state),
                "current": self._current,
                "index": self._index,
                "total": len(self.order),
                "results": [dict(item) for item in self._results],
                "order": list(self.order),
            }

    def is_running(self):
        return bool(self._thread and self._thread.is_alive())

    def stop(self):
        self._stop.set()

    # -------------------------------------------------- 执行
    def start(self):
        if self.is_running():
            return False
        self._thread = threading.Thread(
            target=self._run, name="gamehub-daily-queue", daemon=True)
        self._thread.start()
        return True

    def _emit(self, **event):
        if not self.on_event:
            return
        try:
            self.on_event(event)
        except Exception:
            pass

    def _set(self, **kwargs):
        with self._lock:
            for key, value in kwargs.items():
                setattr(self, "_" + key, value)

    def _run(self):
        self._set(state=RUNNING)
        self._emit(type="queue", state=RUNNING, total=len(self.order))
        try:
            for index, key in enumerate(self.order):
                app = self.by_key[key]
                settings = app.get("daily") or {}
                if self._stop.is_set():
                    skipped = {
                        "key": key, "game": app.get("game", ""),
                        "state": STOPPED, "state_label": STATE_LABELS[STOPPED],
                        "reason": "队列已停止，未执行",
                    }
                    with self._lock:
                        self._results.append(skipped)
                    self._emit(type="item", key=key, result=skipped)
                    continue
                if not settings.get("enabled", True):
                    skipped = {
                        "key": key, "game": app.get("game", ""),
                        "state": SKIPPED,
                        "state_label": STATE_LABELS[SKIPPED],
                        "reason": "未启用清日常",
                    }
                    with self._lock:
                        self._results.append(skipped)
                    self._set(current=None, index=index)
                    self._emit(type="item", key=key, result=skipped)
                    continue
                self._set(current=key, index=index)
                self._emit(type="item_start", key=key,
                           game=app.get("game", ""), index=index)
                result = run(app, settings,
                             dry_run=self.dry_run,
                             stop_event=self._stop,
                             on_event=self._forward_event,
                             launcher=self.launcher)
                with self._lock:
                    self._results.append(result)
                self._set(current=None)
                self._emit(type="item", key=key, result=result)
            final_state = STOPPED if self._stop.is_set() else FINISHED
        except Exception as exc:       # 队列异常：标记失败，不让线程静默死掉
            self._set(current=None)
            self._emit(type="queue_error", error=str(exc))
            final_state = FAILED
        self._set(state=final_state, current=None)
        self._emit(type="queue", state=final_state, snapshot=self.snapshot())

    def _forward_event(self, event):
        self._emit(**{"type": "runner", "event": event})


# ------------------------------------------------------------------ 每游戏独立状态管理（v0.8）
def ordered_daily_keys(apps, order=None):
    """按 daily_order 过滤出存在的 app key；未列出的卡片补在末尾。"""
    by_key = {app.get("key"): app for app in (apps or [])}
    keys = []
    for key in (order or store.DEFAULT_DAILY_ORDER):
        if key in by_key and key not in keys:
            keys.append(key)
    for app in apps or []:
        key = app.get("key")
        if key in by_key and key not in keys:
            keys.append(key)
    return keys


def enabled_daily_keys(apps, order=None):
    """按 daily_order 返回已勾选（daily.enabled）的 app key。"""
    by_key = {app.get("key"): app for app in (apps or [])}
    result = []
    for key in ordered_daily_keys(apps, order):
        settings = store._clean_daily(by_key[key].get("daily"), key)
        if settings.get("enabled", True):
            result.append(key)
    return result


def _empty_app_state(app):
    key = app.get("key", "")
    return {
        "key": key,
        "game": app.get("game", ""),
        "state": IDLE,
        "state_label": STATE_LABELS[IDLE],
        "reason": "",
        "pid": None,
        "started_at": None,
        "ended_at": None,
        "duration": 0,
        "command": "",
        "log_tail": "",
        "updated_at": time.time(),
    }


class DailyManager:
    """管理单游戏/队列的清日常独立状态（v0.8 UI 使用）。

    - 同一时刻只允许一个任务/队列运行；其它行保持自己的空闲/历史状态，
      绝不全部显示「清日常中」。
    - start_single(key)/stop_single(key) 与 start_queue(keys)/stop_all() 共用 run()。
    - snapshot() 线程安全，可供 UI 轮询。
    """

    def __init__(self, apps, *, on_event=None, launcher=None):
        self.apps = list(apps or [])
        self.by_key = {app.get("key"): app for app in self.apps}
        self.on_event = on_event
        self.launcher = launcher
        self._lock = threading.RLock()
        self._states = {}
        for app in self.apps:
            self._states[app.get("key")] = _empty_app_state(app)
        self._active = None
        self._thread = None
        self._stop = threading.Event()
        self._mode = ""          # single / queue / ""
        self._queue = {"state": IDLE, "state_label": STATE_LABELS[IDLE],
                       "order": [], "results": [], "current": None,
                       "index": -1, "total": 0}
        self._log = []

    # -------------------------------------------------- 查询
    @property
    def busy(self):
        return bool(self._thread and self._thread.is_alive())

    def state_of(self, key):
        with self._lock:
            return dict(self._states.get(key) or {})

    def _busy_reason_for(self, key):
        with self._lock:
            if not self.busy:
                return ""
            if self._active and self._active != key:
                app = self.by_key.get(self._active) or {}
                return f"「{app.get('game') or self._active}」清日常进行中，请等待完成或先停止"
            if self._mode == "queue" and self._active is None:
                return "清日常队列进行中"
            return ""

    def busy_reason(self, key):
        return self._busy_reason_for(key)

    def snapshot(self):
        with self._lock:
            queue = dict(self._queue)
            queue["results"] = [dict(item) for item in queue.get("results") or []]
            return {
                "busy": self.busy,
                "active": self._active,
                "mode": self._mode,
                "apps": {key: dict(state) for key, state in self._states.items()},
                "queue": queue,
                "log": list(self._log[-200:]),
            }

    # -------------------------------------------------- 内部
    def _emit(self, payload):
        if not self.on_event:
            return
        try:
            self.on_event(payload)
        except Exception:
            pass

    def _log_line(self, text):
        line = time.strftime("%H:%M:%S ") + text
        with self._lock:
            self._log.append(line)
            self._log = self._log[-300:]
        return line

    def _update_state(self, key, **fields):
        with self._lock:
            state = self._states.setdefault(key, {"key": key})
            state.update(fields)
            state["state_label"] = STATE_LABELS.get(state.get("state"),
                                                    state.get("state"))
            state["updated_at"] = time.time()
            snapshot = dict(state)
        self._emit({"type": "state", "key": key, "state": snapshot})
        return snapshot

    def _apply_result(self, key, result):
        result = result or {}
        self._update_state(
            key,
            state=result.get("state") or FAILED,
            reason=result.get("reason") or "",
            pid=result.get("pid"),
            started_at=result.get("started_at"),
            ended_at=result.get("ended_at"),
            duration=result.get("duration") or 0,
            command=result.get("command") or "",
            log_tail=result.get("log_tail") or "",
        )

    def _runner_event(self, event):
        if not isinstance(event, dict):
            return
        if event.get("type") == "state":
            key = event.get("key")
            if key:
                self._update_state(key, state=event.get("state") or RUNNING,
                                   pid=event.get("pid"))
        self._emit({"type": "runner", "event": event})

    def _run_job(self, key):
        app = self.by_key.get(key)
        if app is None:
            result = {"key": key, "game": "", "state": FAILED,
                      "reason": "卡片不存在"}
            self._apply_result(key, result)
            return result
        self._update_state(key, state=STARTING, started_at=time.time(),
                           ended_at=None, reason="")
        result = run(app, stop_event=self._stop,
                     on_event=self._runner_event, launcher=self.launcher)
        self._apply_result(key, result)
        return result

    # -------------------------------------------------- 单游戏
    def start_single(self, key):
        with self._lock:
            if self.busy:
                return False, self._busy_reason_for(key) or "已有清日常任务在运行"
            if key not in self.by_key:
                return False, "卡片不存在"
            self._stop.clear()
            self._active = key
            self._mode = "single"
            self._queue = {"state": RUNNING, "state_label": STATE_LABELS[RUNNING],
                           "order": [key], "results": [], "current": key,
                           "index": 0, "total": 1}
            self._update_state(key, state=STARTING, started_at=time.time(),
                               ended_at=None, reason="")
            self._thread = threading.Thread(
                target=self._single_worker, args=(key,),
                name="gamehub-daily-single", daemon=True)
            self._thread.start()
        self._emit({"type": "queue", "state": RUNNING, "mode": "single",
                    "order": [key], "current": key})
        return True, ""

    def _single_worker(self, key):
        try:
            result = self._run_job(key)
        except Exception as exc:
            result = {"key": key, "game": (self.by_key.get(key) or {}).get("game", ""),
                      "state": FAILED, "reason": f"执行异常：{exc}"}
            self._apply_result(key, result)
        with self._lock:
            self._log_line(f"■ {(self.by_key.get(key) or {}).get('game', key)}："
                           f"{(result or {}).get('state')}")
            self._queue["results"] = [dict(result or {})]
            self._queue["state"] = FINISHED
            self._queue["state_label"] = STATE_LABELS[FINISHED]
            self._queue["current"] = None
            self._active = None
            self._mode = ""
        self._emit({"type": "done", "key": key, "result": dict(result or {}),
                    "snapshot": self.snapshot()})

    def stop_single(self, key):
        with self._lock:
            if not self.busy or self._active != key:
                return False
            self._stop.set()
            self._log_line(f"用户请求停止：{(self.by_key.get(key) or {}).get('game', key)}")
        self._emit({"type": "stop", "key": key})
        return True

    # -------------------------------------------------- 队列
    def start_queue(self, keys=None):
        keys = list(keys or enabled_daily_keys(self.apps))
        keys = [key for key in keys if key in self.by_key]
        with self._lock:
            if self.busy:
                return False, "已有清日常任务在运行"
            if not keys:
                return False, "没有勾选任何游戏"
            self._stop.clear()
            self._active = None
            self._mode = "queue"
            self._queue = {"state": RUNNING, "state_label": STATE_LABELS[RUNNING],
                           "order": keys, "results": [], "current": None,
                           "index": -1, "total": len(keys)}
            self._thread = threading.Thread(
                target=self._queue_worker, args=(keys,),
                name="gamehub-daily-queue2", daemon=True)
            self._thread.start()
        self._emit({"type": "queue", "state": RUNNING, "mode": "queue",
                    "order": keys, "current": None})
        return True, ""

    def _queue_worker(self, keys):
        try:
            for index, key in enumerate(keys):
                with self._lock:
                    self._queue["index"] = index
                    if self._stop.is_set():
                        skipped = {"key": key,
                                   "game": (self.by_key.get(key) or {}).get("game", ""),
                                   "state": STOPPED, "reason": "队列已停止"}
                        self._queue["results"].append(skipped)
                        self._update_state(key, state=STOPPED,
                                           reason="队列已停止")
                        self._emit({"type": "item", "key": key,
                                    "result": skipped})
                        continue
                    self._active = key
                    self._queue["current"] = key
                self._update_state(key, state=STARTING, started_at=time.time(),
                                   ended_at=None, reason="")
                self._log_line(f"▶ 开始：{(self.by_key.get(key) or {}).get('game', key)}")
                self._emit({"type": "item_start", "key": key,
                            "game": (self.by_key.get(key) or {}).get("game", ""),
                            "index": index})
                try:
                    result = self._run_job(key)
                except Exception as exc:
                    result = {"key": key, "state": FAILED,
                              "reason": f"执行异常：{exc}"}
                    self._apply_result(key, result)
                with self._lock:
                    self._queue["results"].append(dict(result or {}))
                    self._queue["current"] = None
                    self._log_line(f"■ {(self.by_key.get(key) or {}).get('game', key)}："
                                   f"{(result or {}).get('state')}")
                self._emit({"type": "item", "key": key,
                            "result": dict(result or {})})
            with self._lock:
                final_state = STOPPED if self._stop.is_set() else FINISHED
                self._queue["state"] = final_state
                self._queue["state_label"] = STATE_LABELS[final_state]
                self._queue["current"] = None
                self._active = None
                self._mode = ""
        finally:
            self._emit({"type": "queue", "state": self._queue.get("state"),
                        "snapshot": self.snapshot()})

    def stop_all(self):
        with self._lock:
            if not self.busy:
                return False
            self._stop.set()
            self._log_line("用户请求停止清日常…")
        self._emit({"type": "stop", "key": self._active})
        return True

    def reset(self):
        """清空历史状态（重新加载配置后使用）。"""
        with self._lock:
            for key, app in self.by_key.items():
                self._states[key] = _empty_app_state(app)
            self._queue = {"state": IDLE, "state_label": STATE_LABELS[IDLE],
                           "order": [], "results": [], "current": None,
                           "index": -1, "total": 0}
