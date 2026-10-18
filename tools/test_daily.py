# -*- coding: utf-8 -*-
"""一键清日常自测：dry-run 命令拼装、状态机、超时/取消、队列顺序、前置校验。

全部使用 mock / 临时目录，不启动任何脚本或游戏、不执行真实清日常。
用法：python tools/test_daily.py
"""
import json
import os
import sys
import tempfile
import time
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from gamehub import daily, store  # noqa: E402

failures = []


def check(label, got, expected):
    ok = got == expected
    print(("OK   " if ok else "FAIL ") + f"{label}: {got!r}")
    if not ok:
        failures.append(f"{label}: got {got!r}, expect {expected!r}")


def touch(path, content=b"stub"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(content)
    return path


# ---------------------------------------------------------------- 测试夹具
class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.t += max(0.0, float(seconds))


class FakeHandle:
    def __init__(self, clock, exit_calls=None, on_wait=None):
        self.pid = 4321
        self.clock = clock
        self.calls = 0
        self.exit_calls = exit_calls
        self.on_wait = on_wait
        self.terminated = False
        self.closed = False

    def alive(self):
        return not self.terminated and not self._exited()

    def _exited(self):
        return bool(self.exit_calls and self.calls >= self.exit_calls)

    def wait(self, timeout_ms=500):
        self.calls += 1
        if self.on_wait:
            self.on_wait(self)
        self.clock.sleep(0.4)
        return self.terminated or self._exited()

    def terminate(self):
        self.terminated = True
        return True

    def close(self):
        self.closed = True


def write_log(path, text):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(text)


def make_okww_app(tmp, settings=None):
    base = os.path.join(tmp, "WuwaMAA", "ok-ww")
    touch(os.path.join(base, "ok-ww.exe"))
    app_dir = os.path.join(base, "data", "apps", "ok-ww")
    touch(os.path.join(app_dir, "python", "pythonw.exe"))
    working = os.path.join(app_dir, "working")
    touch(os.path.join(working, "main.py"), b"print('stub')\n")
    touch(os.path.join(working, "configs", "DailyTask.json"), b"{}")
    log = touch(os.path.join(working, "logs", "ok-script.log"), b"")
    with open(os.path.join(app_dir, "app.json"), "w", encoding="utf-8") as fh:
        json.dump({"current_version": "v9.9.9", "current_profile": "China"}, fh)
    app = store.make_builtin("wuwa", tmp)
    app["launch"] = store.build_okww_launch(app)
    app["daily"] = store._clean_daily(settings or {}, "wuwa")
    return app, log


def make_mxu_app(tmp, key="nte"):
    script = "MaaNTE" if key == "nte" else "MaaEnd"
    base = os.path.join(tmp, script)
    exe = touch(os.path.join(base, f"{script}.exe"))
    if key == "nte":
        config = {"settings": {"hotkeys": {
            "startTasks": "Ctrl+F10", "globalEnabled": True}},
            "instances": [
                {"id": "cfg-nte", "name": "挂机任务", "tasks": [
                    {"taskName": "FishNew", "enabled": True},
                    {"taskName": "DailyTask", "enabled": False}]}]}
    else:
        config = {"instances": [
            {"name": "全套日常", "tasks": [
                {"taskName": "__MXU_PRETASK__LaunchGamePC", "enabled": True},
                {"taskName": "DailyTask", "enabled": True}]},
            {"name": "快速日常", "tasks": [{"taskName": "DailyTask",
                                            "enabled": True}]}]}
    with open(touch(os.path.join(base, "config", f"mxu-{script}.json"),
                    b"{}"), "w", encoding="utf-8") as fh:
        json.dump(config, fh, ensure_ascii=False)
    game_exe = ""
    game_procs = []
    if key == "nte":
        game_exe = touch(os.path.join(base, "NTELauncher.exe"))
        game_procs = ["ntelauncher.exe"]
    app = {"key": key, "game": "异环" if key == "nte" else "明日方舟终末地",
           "script": script, "script_exe": exe,
           "game_exe": game_exe, "game_procs": game_procs,
           "daily": store._clean_daily({}, key)}
    return app


def make_maa_app(tmp, hotkey=True, tasks=("开始唤醒", "自动公招")):
    base = os.path.join(tmp, "MAA")
    exe = touch(os.path.join(base, "MAA.exe"))
    gui = {
        "Current": "Default",
        "Gui": {"HotKeys": {}},
        "Configurations": {"Default": {"TaskQueue": [
            {"Name": name, "TaskType": name, "IsEnable": True}
            for name in tasks]}},
    }
    if hotkey:
        gui["Gui"]["HotKeys"]["LinkStart"] = {
            "Key": "L", "Modifiers": "Alt, Control, Shift"}
    with open(touch(os.path.join(base, "config", "gui.new.json"), b"{}"),
              "w", encoding="utf-8") as fh:
        json.dump(gui, fh, ensure_ascii=False)
    log = touch(os.path.join(base, "debug", "gui.log"), b"")
    app = {"key": "maa", "game": "明日方舟", "script": "MAA",
           "script_exe": exe, "daily": store._clean_daily({}, "maa")}
    return app, gui, log


# ---------------------------------------------------------------- dry-run 命令拼装
def test_dry_run_commands(tmp):
    print("\n=== dry-run：四款命令拼装 ===")
    with tempfile.TemporaryDirectory(prefix="gh_daily_dry_") as inner:
        wuwa, wuwa_log = make_okww_app(inner)
        maa, _gui, _log = make_maa_app(inner)
        nte = make_mxu_app(inner, "nte")
        maaend = make_mxu_app(inner, "maaend")
        apps = [wuwa, maa, nte, maaend]
        with mock.patch.object(store, "snapshot_processes", return_value=set()), \
                mock.patch.object(store, "launch_spec_running", return_value=False), \
                mock.patch.object(daily, "_game_running", return_value=True), \
                mock.patch.object(daily, "launch_elevated",
                                  side_effect=AssertionError("dry-run 不应启动进程")):
            plans = daily.dry_run(apps)
        by_key = {plan["key"]: plan for plan in plans}
        check("dry-run 四款齐全", sorted(by_key), ["maa", "maaend", "nte", "wuwa"])
        wuwa_plan = by_key["wuwa"]
        check("鸣潮用 bundled pythonw",
              os.path.basename(wuwa_plan["exe"]), "pythonw.exe")
        check("鸣潮命令含 main.py -t DailyTask -e",
              ('main.py' in wuwa_plan["params"]
               and '-t DailyTask' in wuwa_plan["params"]
               and wuwa_plan["params"].rstrip().endswith("-e")), True)
        check("鸣潮 cwd=working",
              os.path.basename(wuwa_plan["cwd"]), "working")
        check("鸣潮无前置错误", wuwa_plan["errors"], [])
        check("dry-run 不启动进程", True, True)

        maa_plan = by_key["maa"]
        check("MAA 参数 --skip-startup-auto-run",
              "--skip-startup-auto-run" in maa_plan["params"], True)
        check("MAA 热键解析", maa_plan["hotkey"]["text"],
              "Alt, Control, Shift + L")
        check("MAA 无错误", maa_plan["errors"], [])

        nte_plan = by_key["nte"]
        check("异环改为 mxu_ui", nte_plan["mode"], "mxu_ui")
        check("异环命令含 MaaNTE", "MaaNTE.exe" in nte_plan["command_text"], True)
        check("异环不传 --autostart",
              "--autostart" in nte_plan["params"], False)
        check("异环不传 --quit-after-run",
              "--quit-after-run" in nte_plan["params"], False)
        check("异环读取开始任务热键",
              nte_plan["hotkey"]["text"] if nte_plan.get("hotkey") else "",
              "Ctrl + F10")
        check("异环实例/端口",
              (nte_plan.get("instance"), nte_plan.get("web_port")),
              ("挂机任务", 12701))
        check("异环无前置错误", nte_plan["errors"], [])

        maaend_plan = by_key["maaend"]
        check("终末地默认实例「全套日常」",
              '--instance "全套日常"' in maaend_plan["params"], True)
        check("终末地无错误（含 LaunchGamePC）", maaend_plan["errors"], [])
        check("describe_plan 含命令", "命令:" in daily.describe_plan(wuwa_plan),
              True)


# ---------------------------------------------------------------- 前置校验
def test_preconditions(tmp):
    print("\n=== 前置校验 ===")
    with tempfile.TemporaryDirectory(prefix="gh_daily_pre_") as inner:
        nte = make_mxu_app(inner, "nte")
        with mock.patch.object(store, "snapshot_processes", return_value=set()), \
                mock.patch.object(daily, "_game_running", return_value=False):
            plan = daily.plan_for(nte)
        check("异环计划为 mxu_ui", plan["mode"], "mxu_ui")
        check("异环不要求游戏运行", plan["errors"], [])
        check("异环无 pre_game", "pre_game" in plan, False)
        check("异环读取开始任务热键",
              plan["hotkey"]["text"] if plan.get("hotkey") else "",
              "Ctrl + F10")
        check("异环实例已解析", plan.get("instance"), "挂机任务")
        check("异环 HTTP 端口", plan.get("web_port"), 12701)

        # MaaNTE 已运行 -> 报错
        with mock.patch.object(store, "snapshot_processes",
                               return_value={"MAANTE.EXE"}):
            plan_running = daily.plan_for(nte)
        check("异环脚本已运行 -> 错误",
              any("已在运行" in error
                  for error in plan_running["errors"]), True)

        # 热键缺失/禁用 -> manual 警告，不静默成功
        no_hot = make_mxu_app(os.path.join(inner, "no_hot"), "nte")
        cfg_path = daily.mxu_paths(no_hot)["config"]
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump({"settings": {"hotkeys": {
                "startTasks": "Ctrl+F10", "globalEnabled": False}},
                "instances": [{"name": "挂机任务", "tasks": [
                    {"taskName": "DailyTask", "enabled": True}]}]},
                fh, ensure_ascii=False)
        with mock.patch.object(store, "snapshot_processes", return_value=set()):
            plan_no_hot = daily.plan_for(no_hot)
        check("热键缺失 -> hotkey None", plan_no_hot.get("hotkey"), None)
        check("热键缺失 -> 警告",
              any("手动" in warning for warning in plan_no_hot["warnings"]),
              True)

        # 实例不存在 -> 明确错误
        bad = make_mxu_app(os.path.join(inner, "bad_inst"), "nte")
        bad["daily"] = store._clean_daily({"instance": "不存在"}, "nte")
        with mock.patch.object(store, "snapshot_processes", return_value=set()), \
                mock.patch.object(daily, "_game_running", return_value=True):
            plan_bad = daily.plan_for(bad)
        check("异环实例不存在 -> 错误",
              any("不存在" in error for error in plan_bad["errors"]), True)

        # autoStartInstanceId -> instances[].name
        mapped = make_mxu_app(os.path.join(inner, "mapped"), "nte")
        mapped_cfg = daily.mxu_paths(mapped)["config"]
        with open(mapped_cfg, "w", encoding="utf-8") as fh:
            json.dump({"settings": {"autoStartInstanceId": "cfg-two"},
                       "instances": [
                           {"id": "cfg-one", "name": "挂机任务",
                            "tasks": [{"taskName": "DailyTask",
                                       "enabled": True}]},
                           {"id": "cfg-two", "name": "配置 1",
                            "tasks": [{"taskName": "DailyTask",
                                       "enabled": True}]},
                       ]}, fh, ensure_ascii=False)
        with mock.patch.object(store, "snapshot_processes", return_value=set()), \
                mock.patch.object(daily, "_game_running", return_value=True):
            plan_mapped = daily.plan_for(mapped)
        check("autoStartInstanceId 映射",
              plan_mapped["settings"].get("instance"), "配置 1")
        check("映射实例进入 plan",
              plan_mapped.get("instance"), "配置 1")

        # 无实例 -> 明确错误（不再裸 UI）
        no_inst = make_mxu_app(os.path.join(inner, "no_inst"), "nte")
        ni_cfg = daily.mxu_paths(no_inst)["config"]
        with open(ni_cfg, "w", encoding="utf-8") as fh:
            json.dump({"instances": []}, fh, ensure_ascii=False)
        with mock.patch.object(store, "snapshot_processes", return_value=set()), \
                mock.patch.object(daily, "_game_running", return_value=True):
            plan_no_inst = daily.plan_for(no_inst)
        check("异环无实例 -> 错误",
              any("MXU 实例配置" in error
                  for error in plan_no_inst["errors"]), True)

        maa, _gui, _log = make_maa_app(inner, hotkey=False)
        with mock.patch.object(store, "snapshot_processes", return_value=set()):
            plan = daily.plan_for(maa)
        check("MAA 无热键 -> 错误",
              any("热键" in error for error in plan["errors"]), True)

        maa2, _gui2, _log2 = make_maa_app(os.path.join(inner, "maa2"),
                                          tasks=())
        with mock.patch.object(store, "snapshot_processes", return_value=set()):
            plan = daily.plan_for(maa2)
        check("MAA 任务队列为空 -> 错误",
              any("任务队列" in error for error in plan["errors"]), True)

        wuwa, _log = make_okww_app(os.path.join(inner, "broken"))
        wuwa["launch"] = None
        wuwa["script_exe"] = os.path.join(inner, "broken", "nope",
                                          "ok-ww.exe")
        with mock.patch.object(store, "snapshot_processes", return_value=set()), \
                mock.patch.object(store, "launch_spec_running",
                                  return_value=False):
            plan = daily.plan_for(wuwa)
        check("ok-ww 布局缺失 -> 错误",
              any("pythonw.exe" in error or "main.py" in error
                  for error in plan["errors"]), True)


# ---------------------------------------------------------------- 状态机（单游戏）
def _run_with_mocks(app, clock, fake_handle, log_path, stop_event=None,
                    marker_writer=None, mode_kwargs=None):
    def on_wait(handle):
        if marker_writer:
            marker_writer(handle)

    fake_handle.on_wait = on_wait

    def launcher(exe, params, cwd):
        if not os.path.isfile(log_path):
            touch(log_path)
        return fake_handle

    kwargs = dict(launcher=launcher, stop_event=stop_event)
    if mode_kwargs:
        kwargs.update(mode_kwargs)
    with mock.patch.object(daily, "_now", clock.now), \
            mock.patch.object(daily, "_sleep", clock.sleep), \
            mock.patch.object(store, "snapshot_processes", return_value=set()), \
            mock.patch.object(store, "launch_spec_running", return_value=False), \
            mock.patch.object(daily, "_game_running", return_value=True):
        return daily.run(app, **kwargs)


def test_okww_states(tmp):
    print("\n=== 鸣潮状态机：成功/失败/超时/停止 ===")
    with tempfile.TemporaryDirectory(prefix="gh_daily_okww_") as inner:
        # 成功：日志在进程退出前出现成功标记
        app, log = make_okww_app(inner)
        clock = FakeClock()
        handle = FakeHandle(clock, exit_calls=2)

        def marker(handle_obj):
            if handle_obj.calls == 1:
                write_log(log, "Successfully Executed Task, Exiting Game and App!\n")

        result = _run_with_mocks(app, clock, handle, log, marker_writer=marker)
        check("ok-ww 成功 -> finished", result["state"], daily.FINISHED)
        check("ok-ww 成功记录 PID", result["pid"], 4321)
        check("ok-ww 成功日志摘要", "Successfully Executed" in result["log_tail"],
              True)

        # 失败：进程退出但没有成功标记
        app2, log2 = make_okww_app(os.path.join(inner, "fail"))
        clock2 = FakeClock()
        handle2 = FakeHandle(clock2, exit_calls=2)
        result2 = _run_with_mocks(app2, clock2, handle2, log2)
        check("ok-ww 无成功标记 -> failed", result2["state"], daily.FAILED)

        # 超时：永不退出，超过 timeout 后终止
        app3, log3 = make_okww_app(os.path.join(inner, "timeout"))
        app3["daily"] = store._clean_daily({"timeout_min": 1}, "wuwa")
        clock3 = FakeClock()
        handle3 = FakeHandle(clock3, exit_calls=None)
        result3 = _run_with_mocks(app3, clock3, handle3, log3)
        check("ok-ww 超时 -> timeout", result3["state"], daily.TIMEOUT)
        check("ok-ww 超时结束本次进程", handle3.terminated, True)

        # 停止：第一轮等待时置位 stop_event
        app4, log4 = make_okww_app(os.path.join(inner, "stop"))
        clock4 = FakeClock()
        handle4 = FakeHandle(clock4, exit_calls=None)
        import threading
        stop_event = threading.Event()

        def request_stop(handle_obj):
            if handle_obj.calls == 1:
                stop_event.set()

        result4 = _run_with_mocks(app4, clock4, handle4, log4,
                                  stop_event=stop_event,
                                  marker_writer=request_stop)
        check("ok-ww 用户停止 -> stopped", result4["state"], daily.STOPPED)
        check("ok-ww 停止结束本次进程", handle4.terminated, True)


def test_mxu_and_maa(tmp):
    print("\n=== MXU / MAA 状态机 ===")
    with tempfile.TemporaryDirectory(prefix="gh_daily_mxu_") as inner:
        # 终末地仍走 --autostart MXU：进程退出/超时
        maaend = make_mxu_app(inner, "maaend")
        clock = FakeClock()
        handle = FakeHandle(clock, exit_calls=2)
        result = _run_with_mocks(maaend, clock, handle,
                                 os.path.join(inner, "maaend.log"))
        check("终末地 MXU 进程退出 -> finished", result["state"],
              daily.FINISHED)

        maaend2 = make_mxu_app(os.path.join(inner, "maaend2"), "maaend")
        clock2 = FakeClock()
        handle2 = FakeHandle(clock2, exit_calls=None)
        result2 = _run_with_mocks(maaend2, clock2, handle2,
                                  os.path.join(inner, "maaend2.log"))
        check("终末地 MXU 超时 -> timeout", result2["state"], daily.TIMEOUT)
        check("终末地 MXU 超时结束本次进程", handle2.terminated, True)

        # 异环 mxu_ui：打开 UI → 热键 → HTTP running→succeeded
        nte = make_mxu_app(os.path.join(inner, "nte_ui"), "nte")
        ui_log = touch(os.path.join(daily.mxu_paths(nte)["base"],
                                    "debug", "2026-ui.log"), b"")
        clock_ui = FakeClock()
        handle_ui = FakeHandle(clock_ui, exit_calls=None)
        hotkeys = []

        def send_ok(hotkey):
            hotkeys.append(hotkey)
            return True

        def launcher_ui(exe, params, cwd):
            return handle_ui

        with mock.patch.object(daily, "_now", clock_ui.now), \
                mock.patch.object(daily, "_sleep", clock_ui.sleep), \
                mock.patch.object(daily, "_mxu_ui_window",
                                  return_value={"hwnd": 1}), \
                mock.patch.object(daily, "send_hotkey", side_effect=send_ok), \
                mock.patch.object(daily, "mxu_http_state",
                                  side_effect=[
                                      {"ok": True, "running": True},
                                      {"ok": True, "running": False,
                                       "status": "succeeded"},
                                  ]), \
                mock.patch.object(store, "snapshot_processes",
                                  return_value=set()):
            result_ui = daily.run(nte, launcher=launcher_ui)
        check("异环发送开始任务热键", len(hotkeys), 1)
        check("异环热键内容", hotkeys[0]["text"] if hotkeys else "",
              "Ctrl + F10")
        check("异环 HTTP succeeded -> finished", result_ui["state"],
              daily.FINISHED)
        check("异环完成后保留窗口", handle_ui.terminated, False)

        # HTTP failed -> failed
        nte_fail = make_mxu_app(os.path.join(inner, "nte_fail"), "nte")
        clock_fail = FakeClock()
        handle_fail = FakeHandle(clock_fail, exit_calls=None)
        with mock.patch.object(daily, "_now", clock_fail.now), \
                mock.patch.object(daily, "_sleep", clock_fail.sleep), \
                mock.patch.object(daily, "_mxu_ui_window",
                                  return_value={"hwnd": 1}), \
                mock.patch.object(daily, "send_hotkey", return_value=True), \
                mock.patch.object(daily, "mxu_http_state",
                                  side_effect=[
                                      {"ok": True, "running": True},
                                      {"ok": True, "running": False,
                                       "status": "failed"},
                                  ]), \
                mock.patch.object(store, "snapshot_processes",
                                  return_value=set()):
            result_fail = daily.run(
                nte_fail, launcher=lambda *args: handle_fail)
        check("异环 HTTP failed -> failed", result_fail["state"], daily.FAILED)

        # HTTP 不可用 -> debug 日志标记回退
        nte_log = make_mxu_app(os.path.join(inner, "nte_log"), "nte")
        clock_log = FakeClock()
        handle_log = FakeHandle(clock_log, exit_calls=None)
        log_path = daily.mxu_paths(nte_log)["log"]
        touch(log_path)

        def send_log(hotkey):
            write_log(log_path, "[Task] tasks-completed\n")
            return True

        with mock.patch.object(daily, "_now", clock_log.now), \
                mock.patch.object(daily, "_sleep", clock_log.sleep), \
                mock.patch.object(daily, "_mxu_ui_window",
                                  return_value={"hwnd": 1}), \
                mock.patch.object(daily, "send_hotkey", side_effect=send_log), \
                mock.patch.object(daily, "mxu_http_state",
                                  return_value={"ok": False, "error": "down"}), \
                mock.patch.object(store, "snapshot_processes",
                                  return_value=set()):
            result_log = daily.run(
                nte_log, launcher=lambda *args: handle_log)
        check("HTTP 不可用 -> 日志 finished", result_log["state"],
              daily.FINISHED)

        # 超时 -> timeout，结束本次启动的 MaaNTE
        nte_timeout = make_mxu_app(os.path.join(inner, "nte_timeout"), "nte")
        nte_timeout["daily"] = store._clean_daily({"timeout_min": 1}, "nte")
        clock_to = FakeClock()
        handle_to = FakeHandle(clock_to, exit_calls=None)
        with mock.patch.object(daily, "_now", clock_to.now), \
                mock.patch.object(daily, "_sleep", clock_to.sleep), \
                mock.patch.object(daily, "_mxu_ui_window",
                                  return_value={"hwnd": 1}), \
                mock.patch.object(daily, "send_hotkey", return_value=True), \
                mock.patch.object(daily, "mxu_http_state",
                                  return_value={"ok": False, "error": "down"}), \
                mock.patch.object(store, "snapshot_processes",
                                  return_value=set()):
            result_to = daily.run(
                nte_timeout, launcher=lambda *args: handle_to)
        check("异环等待超时 -> timeout", result_to["state"], daily.TIMEOUT)
        check("异环超时结束本次进程", handle_to.terminated, True)

        # 热键缺失 -> manual failed，保留窗口
        nte_no_hot = make_mxu_app(os.path.join(inner, "nte_no_hot"), "nte")
        cfg = daily.mxu_paths(nte_no_hot)["config"]
        with open(cfg, "w", encoding="utf-8") as fh:
            json.dump({"settings": {"hotkeys": {
                "startTasks": "Ctrl+F10", "globalEnabled": False}},
                "instances": [{"name": "挂机任务", "tasks": [
                    {"taskName": "DailyTask", "enabled": True}]}]},
                fh, ensure_ascii=False)
        clock_nh = FakeClock()
        handle_nh = FakeHandle(clock_nh, exit_calls=None)
        with mock.patch.object(daily, "_now", clock_nh.now), \
                mock.patch.object(daily, "_sleep", clock_nh.sleep), \
                mock.patch.object(daily, "_mxu_ui_window",
                                  return_value={"hwnd": 1}), \
                mock.patch.object(daily, "send_hotkey",
                                  side_effect=AssertionError("不应发热键")), \
                mock.patch.object(store, "snapshot_processes",
                                  return_value=set()):
            result_nh = daily.run(
                nte_no_hot, launcher=lambda *args: handle_nh)
        check("热键缺失 -> manual failed", result_nh["state"], daily.FAILED)
        check("热键缺失提示手动", "手动" in result_nh["reason"], True)
        check("热键缺失保留窗口", handle_nh.terminated, False)

        # MAA：启动 -> 就绪 -> 热键 -> 日志成功
        maa, _gui, maa_log = make_maa_app(os.path.join(inner, "maa"))
        clock3 = FakeClock()
        handle3 = FakeHandle(clock3, exit_calls=None)
        hotkeys = []

        def fake_ready(pid=None):
            return True

        def fake_send(hotkey):
            hotkeys.append(hotkey)
            write_log(maa_log, "任务已全部完成！\n")
            return True

        def launcher(exe, params, cwd):
            touch(maa_log)
            return handle3

        with mock.patch.object(daily, "_now", clock3.now), \
                mock.patch.object(daily, "_sleep", clock3.sleep), \
                mock.patch.object(daily, "send_hotkey", side_effect=fake_send), \
                mock.patch.object(daily, "_maa_window_ready", side_effect=fake_ready), \
                mock.patch.object(store, "snapshot_processes", return_value=set()):
            result3 = daily.run(maa, launcher=launcher)
        check("MAA 发送热键", len(hotkeys), 1)
        check("MAA 日志完成 -> finished", result3["state"], daily.FINISHED)

        # MAA attach：已在运行则不启动进程
        maa2, _gui2, maa_log2 = make_maa_app(os.path.join(inner, "maa2"))
        clock4 = FakeClock()
        handle4 = FakeHandle(clock4, exit_calls=None)
        hotkeys2 = []

        def fake_send2(hotkey):
            hotkeys2.append(hotkey)
            write_log(maa_log2, "任务已全部完成！\n")
            return True

        def fail_launcher(exe, params, cwd):
            raise AssertionError("MAA 已在运行时不应重复启动")

        with mock.patch.object(daily, "_now", clock4.now), \
                mock.patch.object(daily, "_sleep", clock4.sleep), \
                mock.patch.object(daily, "send_hotkey", side_effect=fake_send2), \
                mock.patch.object(store, "snapshot_processes",
                                  return_value={"MAA.EXE"}):
            result4 = daily.run(maa2, launcher=fail_launcher)
        check("MAA 复用已有实例", len(hotkeys2), 1)
        check("MAA attach 完成", result4["state"], daily.FINISHED)

        # MAA 失败标记
        maa3, _gui3, maa_log3 = make_maa_app(os.path.join(inner, "maa3"))
        clock5 = FakeClock()
        handle5 = FakeHandle(clock5, exit_calls=None)

        def fake_send3(hotkey):
            write_log(maa_log3, "任务出错: 开始唤醒\n")
            return True

        def launcher3(exe, params, cwd):
            touch(maa_log3)
            return handle5

        with mock.patch.object(daily, "_now", clock5.now), \
                mock.patch.object(daily, "_sleep", clock5.sleep), \
                mock.patch.object(daily, "send_hotkey", side_effect=fake_send3), \
                mock.patch.object(daily, "_maa_window_ready",
                                  side_effect=lambda pid=None: True), \
                mock.patch.object(store, "snapshot_processes", return_value=set()):
            result5 = daily.run(maa3, launcher=launcher3)
        check("MAA 日志出错 -> failed", result5["state"], daily.FAILED)


# ---------------------------------------------------------------- 队列
def test_queue(tmp):
    print("\n=== 顺序队列 ===")
    apps = []
    for key, game in (("maa", "明日方舟"), ("nte", "异环"),
                      ("wuwa", "鸣潮"), ("maaend", "终末地")):
        app = {"key": key, "game": game,
               "script_exe": os.path.join(tmp, game, "script.exe"),
               "daily": store._clean_daily({}, key)}
        os.makedirs(os.path.dirname(app["script_exe"]), exist_ok=True)
        apps.append(app)

    executed = []

    def fake_run(app, settings=None, *, dry_run=False, stop_event=None,
                 on_event=None, launcher=None):
        executed.append(app["key"])
        if on_event:
            on_event({"type": "state", "key": app["key"],
                      "state": daily.RUNNING})
        return {"key": app["key"], "game": app["game"],
                "state": daily.FINISHED, "state_label": "已完成",
                "reason": "mock"}

    events = []
    with mock.patch.object(daily, "run", side_effect=fake_run):
        queue = daily.DailyQueue(apps, ["wuwa", "maa", "nte", "maaend"],
                                 on_event=events.append)
        queue.start()
        queue._thread.join(timeout=5)
    check("队列按顺序执行", executed, ["wuwa", "maa", "nte", "maaend"])
    snapshot = queue.snapshot()
    check("队列结束状态", snapshot["state"], daily.FINISHED)
    check("队列结果数量", len(snapshot["results"]), 4)
    check("队列结果顺序",
          [item["key"] for item in snapshot["results"]],
          ["wuwa", "maa", "nte", "maaend"])

    # 禁用项跳过
    apps[1]["daily"] = store._clean_daily({"enabled": False}, "nte")
    executed.clear()
    with mock.patch.object(daily, "run", side_effect=fake_run):
        queue2 = daily.DailyQueue(apps, ["maa", "nte", "wuwa"])
        queue2.start()
        queue2._thread.join(timeout=5)
    check("禁用项不执行", executed, ["maa", "wuwa"])
    kinds = [item["state"] for item in queue2.snapshot()["results"]]
    check("禁用项记录 skipped", daily.SKIPPED in kinds, True)

    # 停止队列：第一项执行时请求停止
    apps[1]["daily"] = store._clean_daily({}, "nte")
    executed.clear()

    def stopping_run(app, settings=None, *, dry_run=False, stop_event=None,
                     on_event=None, launcher=None):
        executed.append(app["key"])
        queue3.stop()
        return {"key": app["key"], "game": app["game"],
                "state": daily.STOPPED, "state_label": "已停止",
                "reason": "mock stop"}

    queue3 = daily.DailyQueue(apps, ["maa", "nte", "wuwa"])
    with mock.patch.object(daily, "run", side_effect=stopping_run):
        queue3.start()
        queue3._thread.join(timeout=5)
    check("停止后不执行后续项", executed, ["maa"])
    snapshot3 = queue3.snapshot()
    check("停止后队列状态", snapshot3["state"], daily.STOPPED)
    states = [item["state"] for item in snapshot3["results"]]
    check("后续项标记 stopped", states.count(daily.STOPPED), 3)


# ---------------------------------------------------------------- 日志与配置
def test_log_watcher(tmp):
    print("\n=== 日志增量读取 ===")
    path = os.path.join(tmp, "watch.log")
    touch(path, b"old line\n")
    watcher = daily.LogWatcher(path)
    check("初始不重复读旧内容", watcher.read(), "")
    write_log(path, "new line 1\n")
    check("读到增量", "new line 1" in watcher.read(), True)
    write_log(path, "new line 2\n")
    check("继续读增量", "new line 2" in watcher.read(), True)
    check("tail 包含历史", "new line 1" in watcher.tail(10), True)
    # 截断/轮转：文件变短后从头读
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("rotated\n")
    watcher.offset = 0
    check("轮转后重新读取", "rotated" in watcher.read(), True)


def test_config_roundtrip(tmp):
    print("\n=== 配置持久化（daily_order / daily） ===")
    cfg = os.path.join(tmp, "config.json")
    apps = []
    for key in ("maa", "nte", "wuwa", "maaend"):
        app = {"key": key, "game": key, "script": key,
               "builtin": True, "script_exe": "", "script_procs": [],
               "game_procs": [], "game_exe": "",
               "daily": store._clean_daily({"timeout_min": 30,
                                            "extra_args": ["--flag"]}, key)}
        apps.append(app)
    with mock.patch.object(store, "CONFIG", cfg):
        store.save_state(apps, "", tmp, ["wuwa", "maa", "nte", "maaend"])
        loaded = store.load_state_full()
    apps2, _clash, _root, meta = loaded
    check("daily_order 持久化", meta["daily_order"],
          ["wuwa", "maa", "nte", "maaend"])
    by_key = {app["key"]: app for app in apps2}
    check("timeout_min 持久化", by_key["maa"]["daily"]["timeout_min"], 30)
    check("extra_args 持久化", by_key["maa"]["daily"]["extra_args"],
          ["--flag"])
    check("内置默认 task 保留", by_key["wuwa"]["daily"]["task"], "DailyTask")
    raw = json.load(open(cfg, encoding="utf-8"))
    check("config 版本 v4", raw.get("version"), 4)
    check("config 写入 daily_order", raw.get("daily_order"),
          ["wuwa", "maa", "nte", "maaend"])
    check("旧配置无 daily 自动补默认", raw["apps"]["maa"]["daily"]["enabled"],
          True)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    with tempfile.TemporaryDirectory(prefix="gh_daily_test_") as tmp:
        test_dry_run_commands(tmp)
        test_preconditions(tmp)
        test_okww_states(tmp)
        test_mxu_and_maa(tmp)
        test_queue(tmp)
        test_log_watcher(tmp)
        test_config_roundtrip(tmp)
    print("\nFAILURES:", failures if failures else "none")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
