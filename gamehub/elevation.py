# -*- coding: utf-8 -*-
"""默认管理员启动：提权决策与源码自重启（可独立测试，不启动 GUI/UAC）。"""
import ctypes
import os
import sys


def is_admin():
    """当前进程是否管理员（高完整性）。"""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _env_flag(env, name):
    value = str((env or {}).get(name, "")).strip().lower()
    return value in ("1", "true", "yes", "on")


def should_elevate(is_admin=False, argv=None, env=None, frozen=False):
    """是否需要在源码模式下自提权重启。纯逻辑，便于测试。"""
    if is_admin:
        return False
    if frozen:
        return False
    args = list(sys.argv[1:] if argv is None else argv)
    if "--no-elevate" in args or "--elevated" in args:
        return False
    if _env_flag(os.environ if env is None else env, "GAMEHUB_NO_ELEVATE"):
        return False
    return True


def pythonw_path(exe=None):
    """优先返回 pythonw.exe（源码模式避免控制台窗口）。"""
    exe = os.path.normpath(exe or sys.executable or "")
    if not exe:
        return "pythonw.exe"
    if os.path.basename(exe).lower() == "pythonw.exe":
        return exe
    candidate = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return candidate if os.path.isfile(candidate) else exe


def build_relaunch(hub_path, app_dir=None, pythonw=None, extra_args=None):
    """构造 ShellExecuteW 重启参数；hub 路径始终加引号。"""
    hub_path = os.path.abspath(hub_path)
    args = ['"' + hub_path + '"', "--elevated"]
    args.extend(str(item) for item in (extra_args or []))
    return {
        "verb": "runas",
        "file": pythonw_path(pythonw),
        "params": " ".join(args),
        "cwd": os.path.abspath(app_dir or os.path.dirname(hub_path)),
        "show": 1,
    }


def relaunch_as_admin(hub_path, app_dir=None, pythonw=None,
                      extra_args=None):
    """ShellExecuteW(runas) 重启自身；返回 ShellExecute 结果（>32 成功）。"""
    spec = build_relaunch(hub_path, app_dir, pythonw, extra_args)
    try:
        return int(ctypes.windll.shell32.ShellExecuteW(
            None, spec["verb"], spec["file"], spec["params"], spec["cwd"],
            spec["show"]))
    except Exception:
        return 0


def not_admin_message():
    """用户取消 UAC/提权失败时的说明（继续普通权限运行）。"""
    text = ("未获得管理员权限，将以普通权限运行。\n\n"
            "提示：异环清日常的「开始任务」热键、以及部分脚本的输入/截图功能"
            "可能需要管理员权限；可右键「以管理员身份运行」本程序。")
    try:
        ctypes.windll.user32.MessageBoxW(0, text, "All-My-Maa · 权限提示",
                                         0x00000040)
    except Exception:
        pass


def elevation_status(argv=None, env=None, frozen=False):
    """--elevation-check 输出（测试用，不弹 UAC）。"""
    elevated = is_admin()
    return {
        "admin": elevated,
        "frozen": bool(frozen),
        "would_elevate": should_elevate(
            elevated, sys.argv[1:] if argv is None else argv,
            os.environ if env is None else env, frozen),
        "pythonw": pythonw_path(),
    }
