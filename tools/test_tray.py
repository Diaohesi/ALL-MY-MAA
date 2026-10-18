# -*- coding: utf-8 -*-
"""v0.11 托盘：设置默认/持久化、TrayManager 幂等/降级/回调调度（不建真实托盘）。"""
import os
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from gamehub import store, tray  # noqa: E402

failures = []


def check(label, got, expected):
    ok = got == expected
    print(("OK   " if ok else "FAIL ") + f"{label}: {got!r}")
    if not ok:
        failures.append(f"{label}: got {got!r}, expect {expected!r}")


class FakeRoot:
    def __init__(self):
        self.after_calls = []

    def after(self, delay, callback):
        self.after_calls.append((delay, callback))
        return "after-id"


def test_settings():
    print("=== settings ===")
    defaults = store._clean_settings(None)
    check("默认最小化到托盘", defaults["minimize_to_tray"], True)
    check("显式 false 保留",
          store._clean_settings({"minimize_to_tray": False})
          ["minimize_to_tray"], False)
    check("非法值回退默认",
          store._clean_settings({"minimize_to_tray": "yes"})
          ["minimize_to_tray"], True)
    check("默认项包含字段", "minimize_to_tray" in store.DEFAULT_SETTINGS, True)


def test_tooltip():
    print("\n=== tooltip ===")
    manager = tray.TrayManager(None, tooltip="All-My-Maa")
    check("默认 tooltip", manager.tooltip, "All-My-Maa")
    long_text = "x" * 300
    manager.update_tooltip(long_text)
    check("tooltip 截断 127", len(manager.tooltip), 127)
    manager.update_tooltip("")
    check("空 tooltip 回退", manager.tooltip, "All-My-Maa")


def test_fallback_and_idempotent():
    print("\n=== 失败降级/幂等 ===")
    old = tray._ENABLED
    try:
        tray._ENABLED = False
        manager = tray.TrayManager(None)
        check("不支持平台 start false", manager.start(), False)
        check("重复 start false", manager.start(), False)
        check("stop 幂等", (manager.stop(), manager.stop()), (True, True))
        check("failed 标记", manager.failed, True)

        tray._ENABLED = True
        broken = tray.TrayManager(None)

        def boom():
            raise RuntimeError("no shell")

        broken._start_native = boom
        check("启动异常安全降级", broken.start(), False)
        check("保留错误信息", "no shell" in broken.last_error, True)
        check("失败后可 stop", broken.stop(), True)
    finally:
        tray._ENABLED = old

    # 成功路径用 mock，仅验证 start/stop 幂等，不创建真实 Windows 托盘
    manager = tray.TrayManager(None)
    started, stopped = [], []
    manager._start_native = lambda: started.append(1)
    manager._stop_native = lambda: stopped.append(1)
    with_start = manager.start()
    with_again = manager.start()
    check("成功 start", with_start, True)
    check("重复 start 不重复创建", len(started), 1)
    manager.stop()
    manager.stop()
    check("stop 只清理一次", len(stopped), 1)
    check("重复 start 返回值", with_again, True)


def test_callbacks():
    print("\n=== 回调调度 ===")
    root = FakeRoot()
    shown, exited = [], []
    manager = tray.TrayManager(root, on_show=lambda: shown.append(1),
                               on_exit=lambda: exited.append(1))
    manager._handle_menu_command(tray.MENU_SHOW)
    manager._handle_menu_command(tray.MENU_EXIT)
    check("菜单回调调度", (len(shown), len(exited)), (0, 0))
    check("通过 root.after 切回 UI 线程", len(root.after_calls), 2)
    for _delay, callback in root.after_calls:
        callback()
    check("显示回调执行", shown, [1])
    check("退出回调执行", exited, [1])
    # 根窗口已销毁时不抛出
    class DeadRoot:
        def after(self, *args):
            raise RuntimeError("main thread is not in main loop")
    manager2 = tray.TrayManager(DeadRoot(), on_show=lambda: None)
    manager2._handle_menu_command(tray.MENU_SHOW)
    check("死根窗口安全", True, True)


def test_minimize_branch():
    print("\n=== 最小化分支（mock tray） ===")
    from gamehub import ui

    class FakeTray:
        def __init__(self, ok=True):
            self.ok = ok
            self.starts = 0

        def start(self):
            self.starts += 1
            return self.ok

    class FakeTk:
        def __init__(self):
            self.withdraw_calls = 0

        def withdraw(self):
            self.withdraw_calls += 1

    obj = SimpleNamespace(settings={"minimize_to_tray": True},
                          tray=FakeTray(True), root=FakeTk(),
                          _tray_hidden=False)
    hidden = ui.GameHub._hide_to_tray(obj)
    check("开启托盘 -> withdraw", hidden, True)
    check("隐藏状态记录", obj._tray_hidden, True)
    check("root.withdraw 调用", obj.root.withdraw_calls, 1)

    obj2 = SimpleNamespace(settings={"minimize_to_tray": False},
                           tray=FakeTray(True), root=FakeTk(),
                           _tray_hidden=False)
    check("关闭托盘 -> 不隐藏", ui.GameHub._hide_to_tray(obj2), False)
    check("关闭托盘不 withdraw", obj2.root.withdraw_calls, 0)

    obj3 = SimpleNamespace(settings={"minimize_to_tray": True},
                           tray=FakeTray(False), root=FakeTk(),
                           _tray_hidden=False)
    check("托盘启动失败 -> 回退", ui.GameHub._hide_to_tray(obj3), False)
    check("回退不 withdraw", obj3.root.withdraw_calls, 0)
    check("托盘 start 尝试", obj3.tray.starts, 1)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    test_settings()
    test_tooltip()
    test_fallback_and_idempotent()
    test_callbacks()
    test_minimize_branch()
    print("\nFAILURES:", failures if failures else "none")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
