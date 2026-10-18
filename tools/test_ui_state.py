# -*- coding: utf-8 -*-
"""v0.8 UI 状态自测（不启动 GUI 主循环、不启动脚本/游戏）。

覆盖：
- settings 清洗 / 持久化往返、refresh interval 应用
- 清日常勾选过滤、daily_order 顺序
- DailyManager 每游戏独立状态（单游戏互斥、队列顺序/跳过）
"""
import json
import os
import sys
import tempfile
import threading
import time
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from gamehub import daily, store, ui  # noqa: E402

failures = []


def check(label, got, expected):
    ok = got == expected
    print(("OK   " if ok else "FAIL ") + f"{label}: {got!r}")
    if not ok:
        failures.append(f"{label}: got {got!r}, expect {expected!r}")


# ---------------------------------------------------------------- settings
def test_settings_clean():
    print("\n=== settings 清洗 ===")
    defaults = store._clean_settings(None)
    check("缺省 accent", defaults["accent"], "#4fc3ff")
    check("缺省刷新间隔", defaults["refresh_interval"], 1.5)
    check("缺省关闭行为", defaults["close_action"], "exit")

    cleaned = store._clean_settings({
        "accent": "#B98BFF", "check_update_on_start": False,
        "refresh_interval": 2.0, "close_action": "minimize",
        "clash_exe": r"C:\Clash\clash-verge.exe",
        "daily_default_timeout": 9999, "daily_show_preview": False,
        "adb_enabled": True, "daily_close_after": False,
    })
    check("accent 小写归一", cleaned["accent"], "#b98bff")
    check("check_update_on_start", cleaned["check_update_on_start"], False)
    check("refresh 2.0 保留", cleaned["refresh_interval"], 2.0)
    check("close_action minimize", cleaned["close_action"], "minimize")
    check("默认超时上限", cleaned["daily_default_timeout"], 600)
    check("adb_enabled", cleaned["adb_enabled"], True)
    check("daily_show_preview", cleaned["daily_show_preview"], False)

    bad = store._clean_settings({
        "accent": "red", "refresh_interval": 7, "close_action": "explode",
        "daily_default_timeout": -3, "enabled": "true"})
    check("非法 accent 回退", bad["accent"], "#4fc3ff")
    check("非法刷新间隔回退", bad["refresh_interval"], 1.5)
    check("非法关闭行为回退", bad["close_action"], "exit")
    check("负超时回退最小值", bad["daily_default_timeout"], 1)

    check("refresh_delay 1.0", ui._refresh_delay_ms({"refresh_interval": 1.0}),
          1000)
    check("refresh_delay 1.5", ui._refresh_delay_ms({"refresh_interval": 1.5}),
          1500)
    check("refresh_delay 2.0", ui._refresh_delay_ms({"refresh_interval": 2.0}),
          2000)
    check("refresh_delay 非法回退 1500",
          ui._refresh_delay_ms({"refresh_interval": 9}), 1500)
    check("refresh_delay 缺省 1500", ui._refresh_delay_ms({}), 1500)


def test_settings_roundtrip(tmp):
    print("\n=== settings / 勾选 / 顺序持久化 ===")
    cfg = os.path.join(tmp, "config.json")
    apps = []
    for key in ("maa", "nte", "wuwa", "maaend"):
        app = store.make_builtin(key, tmp)
        app["daily"] = store._clean_daily({"enabled": key != "nte"}, key)
        app["daily_explicit"] = True
        apps.append(app)
    settings = store._clean_settings({
        "accent": "#9ae66e", "refresh_interval": 2.0,
        "close_action": "minimize", "daily_default_timeout": 45,
        "daily_show_preview": False, "adb_enabled": True,
    })
    with mock.patch.object(store, "CONFIG", cfg):
        check("保存成功", store.save_state(
            apps, clash="", root=tmp,
            daily_order=["wuwa", "maa", "maaend", "nte"],
            settings=settings), True)
        raw = json.load(open(cfg, encoding="utf-8"))
        check("config settings 落盘", raw["settings"]["accent"], "#9ae66e")
        check("config daily_order 落盘", raw["daily_order"],
              ["wuwa", "maa", "maaend", "nte"])
        loaded, _clash, _root, meta = store.load_state_full()
    check("重载 settings accent", meta["settings"]["accent"], "#9ae66e")
    check("重载 refresh", meta["settings"]["refresh_interval"], 2.0)
    check("重载 close_action", meta["settings"]["close_action"], "minimize")
    check("重载 daily_order", meta["daily_order"],
          ["wuwa", "maa", "maaend", "nte"])
    by_key = {app["key"]: app for app in loaded}
    check("旧 daily enabled 保留", by_key["maa"]["daily"]["enabled"], True)
    check("禁用项保留", by_key["nte"]["daily"]["enabled"], False)

    # 勾选过滤 / 顺序
    check("ordered keys", daily.ordered_daily_keys(
        loaded, meta["daily_order"]), ["wuwa", "maa", "maaend", "nte"])
    check("enabled keys", daily.enabled_daily_keys(
        loaded, meta["daily_order"]), ["wuwa", "maa", "maaend"])
    check("过滤无效 key 并补齐缺失", daily.ordered_daily_keys(
        loaded, ["bogus", "nte"]), ["nte", "maa", "wuwa", "maaend"])

    # 默认超时设置只作用于未显式写 timeout 的 daily
    legacy = {"version": 4, "root": tmp, "settings": {
        "daily_default_timeout": 55},
        "apps": {"maa": {"daily": {"enabled": True, "task": "DailyTask"}}}}
    with open(cfg, "w", encoding="utf-8") as fh:
        json.dump(legacy, fh, ensure_ascii=False)
    with mock.patch.object(store, "CONFIG", cfg):
        loaded2, _c, _r, _m = store.load_state_full()
    maa = next(app for app in loaded2 if app["key"] == "maa")
    check("未写 timeout 时用设置默认超时",
          maa["daily"]["timeout_min"], 55)


# ---------------------------------------------------------------- manager
def make_apps():
    apps = []
    for key, game in (("maa", "MAA"), ("nte", "NTE"),
                      ("wuwa", "WW"), ("maaend", "ENDFIELD")):
        apps.append({
            "key": key, "game": game, "script": game, "builtin": True,
            "script_exe": "", "script_procs": [], "game_procs": [],
            "game_exe": "", "daily": store._clean_daily({}, key),
            "daily_explicit": False,
        })
    return apps


def test_manager_isolation():
    print("\n=== 每游戏独立状态（单游戏互斥） ===")
    apps = make_apps()
    gate = threading.Event()
    started = threading.Event()
    executed = []

    def fake_run(app, settings=None, *, dry_run=False, stop_event=None,
                 on_event=None, launcher=None):
        executed.append(app["key"])
        if on_event:
            on_event({"type": "state", "key": app["key"],
                      "state": daily.RUNNING, "pid": 4321})
        started.set()
        gate.wait(timeout=5)
        state = daily.STOPPED if (stop_event and stop_event.is_set()) \
            else daily.FINISHED
        return {"key": app["key"], "game": app["game"], "state": state,
                "reason": "mock", "pid": 4321}

    events = []
    with mock.patch.object(daily, "run", side_effect=fake_run):
        manager = daily.DailyManager(apps, on_event=events.append)
        ok, reason = manager.start_single("maa")
        check("开始单游戏", ok, True)
        check("单游戏进行中", manager.state_of("maa")["state"] in
              (daily.STARTING, daily.RUNNING), True)
        started.wait(timeout=2)
        # 其它行必须保持自己的空闲状态
        for key in ("nte", "wuwa", "maaend"):
            check(f"{key} 不被标记为运行中",
                  manager.state_of(key)["state"], daily.IDLE)
        ok2, reason2 = manager.start_single("nte")
        check("另一项运行时拒绝开始", ok2, False)
        check("拒绝原因提示", "进行中" in reason2, True)
        check("队列进行中提示", "队列" in manager.busy_reason("nte")
              or "进行中" in manager.busy_reason("nte"), True)
        gate.set()
        time.sleep(0.2)
        check("单游戏结束状态", manager.state_of("maa")["state"],
              daily.FINISHED)
        check("其它行仍空闲", manager.state_of("nte")["state"], daily.IDLE)
        check("busy 释放", manager.busy, False)

        # 队列顺序 + 勾选过滤
        executed.clear()
        gate.clear()
        started.clear()
        apps[1]["daily"] = store._clean_daily({"enabled": False}, "nte")
        keys = daily.enabled_daily_keys(apps, ["maend", "maa", "wuwa"])
        keys = daily.enabled_daily_keys(apps, ["maa", "nte", "wuwa", "maaend"])
        check("队列只含勾选项", keys, ["maa", "wuwa", "maaend"])
        ok, reason = manager.start_queue(keys)
        check("开始队列", ok, True)
        started.wait(timeout=2)
        check("队列当前项运行中",
              manager.state_of("maa")["state"] in
              (daily.STARTING, daily.RUNNING), True)
        gate.set()
        for _ in range(50):
            if not manager.busy:
                break
            time.sleep(0.05)
        check("队列执行顺序", executed, ["maa", "wuwa", "maaend"])
        for key in ("maa", "wuwa", "maaend"):
            check(f"{key} 队列完成", manager.state_of(key)["state"],
                  daily.FINISHED)
        check("未勾选项保持空闲", manager.state_of("nte")["state"], daily.IDLE)


def test_manager_stop():
    print("\n=== 单游戏停止 ===")
    apps = make_apps()
    stop_seen = threading.Event()
    started = threading.Event()

    def fake_run(app, settings=None, *, dry_run=False, stop_event=None,
                 on_event=None, launcher=None):
        started.set()
        for _ in range(100):
            if stop_event is not None and stop_event.is_set():
                stop_seen.set()
                break
            time.sleep(0.02)
        return {"key": app["key"], "game": app["game"],
                "state": daily.STOPPED, "reason": "用户停止"}

    with mock.patch.object(daily, "run", side_effect=fake_run):
        manager = daily.DailyManager(apps)
        manager.start_single("wuwa")
        started.wait(timeout=2)
        check("停止接口返回", manager.stop_single("wuwa"), True)
        stop_seen.wait(timeout=2)
        check("stop_event 传递到 runner", stop_seen.is_set(), True)
        for _ in range(50):
            if not manager.busy:
                break
            time.sleep(0.05)
        check("停止后状态", manager.state_of("wuwa")["state"], daily.STOPPED)
        check("停止非当前项返回 False", manager.stop_single("maa"), False)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    with tempfile.TemporaryDirectory(prefix="gh_ui_state_") as tmp:
        test_settings_clean()
        test_settings_roundtrip(tmp)
        test_manager_isolation()
        test_manager_stop()
    print("\nFAILURES:", failures if failures else "none")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
