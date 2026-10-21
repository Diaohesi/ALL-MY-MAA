# -*- coding: utf-8 -*-
"""Offline ok-nte integration contract tests; run: python -B tools/test_oknte.py.

Only temporary fixtures are written. No installed automation is imported/launched,
no real task/config is changed, and every process/launcher boundary is mocked.
Read-only evidence checked against the installed ok-nte distribution:
  data/apps/ok-nte/app.json: current_version v1.4.15
  working/main.py: src.config -> ok.OK(config).start()
  working/src/config.py: onetime_tasks registers DailyRoutineTask (not DailyTask)
  working/configs/DailyRoutineTask.json and DailyRoutineTaskConfigs.json
  working/ok/task/TaskExecutor.py: shared OKWW_SUCCESS_MARKER
  working/logs/ok-script.log; python/python[w].exe; root ok-nte.exe updater.
These tests intentionally use synthetic versions/config data, not live user data.
"""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from contextlib import ExitStack
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from gamehub import daily, detector, store  # noqa: E402


class Clock:
    def __init__(self):
        self.value = 1000.0

    def now(self):
        return self.value

    def sleep(self, seconds):
        self.value += max(0.0, seconds)


class Handle:
    pid = 4321

    def __init__(self, clock, exit_after=None, on_wait=None):
        self.clock = clock
        self.exit_after = exit_after
        self.on_wait = on_wait
        self.calls = 0
        self.terminated = False
        self.closed = False

    def wait(self, timeout_ms=500):
        self.calls += 1
        if self.on_wait:
            self.on_wait(self)
        self.clock.sleep(timeout_ms / 1000)
        return self.terminated or bool(self.exit_after and self.calls >= self.exit_after)

    def alive(self):
        return not self.terminated and not (self.exit_after and self.calls >= self.exit_after)

    def terminate(self):
        self.terminated = True
        return True

    def close(self):
        self.closed = True


class OkNteTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.tmp = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix="gh_oknte_")))
        # Safety tripwires, even if a future implementation changes a code path.
        for owner, name in ((store.subprocess, "Popen"), (store.subprocess, "run"),
                            (store, "launch_exe"), (daily, "launch_elevated")):
            self.stack.enter_context(mock.patch.object(owner, name,
                side_effect=AssertionError("Real process launch is forbidden in offline tests")))
        self.stack.enter_context(mock.patch.object(store, "snapshot_processes", return_value=set()))
        self.stack.enter_context(mock.patch.object(store, "pids_for_procs", return_value=set()))
        self.stack.enter_context(mock.patch.object(store, "find_app_exe", return_value=[]))
        self.stack.enter_context(mock.patch.object(store, "CLASH_CANDIDATES", []))
        detector.reset_cache()
        self.addCleanup(detector.reset_cache)

    def put(self, relative, text=""):
        path = self.tmp / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return str(path)

    def write_json(self, relative, value):
        return self.put(relative, json.dumps(value, ensure_ascii=False))

    def install(self, key="oknte", prefix=""):
        name = "ok-nte" if key == "oknte" else "ok-ww"
        base = Path(prefix) / ("ok-nte" if key == "oknte" else "WuwaMAA/ok-ww")
        appdir = base / "data/apps" / name
        launcher = self.put(base / (name + ".exe"))
        pythonw = self.put(appdir / "python/pythonw.exe")
        python = self.put(appdir / "python/python.exe")
        script = self.put(appdir / "working/main.py", "# fixture only\n")
        task = "DailyRoutineTask" if key == "oknte" else "DailyTask"
        config = self.write_json(appdir / "working/configs" / (task + ".json"), {"fixture": True})
        log = self.put(appdir / "working/logs/ok-script.log")
        meta = self.write_json(appdir / "app.json", {"current_version": "v9.8.7", "current_profile": "China"})
        app = store.make_builtin(key, str(self.tmp / prefix))
        self.assertIsNotNone(app, "Additional stable oknte builtin must exist")
        self.assertEqual(app["script_exe"], launcher)
        self.assertTrue(store.refresh_launch_spec(app), "oknte must infer direct Python launch")
        app["daily"] = store._clean_daily({}, key)
        return app, dict(launcher=launcher, pythonw=pythonw, python=python,
                         script=script, cwd=str(Path(script).parent), config=config, log=log, meta=meta)

    def plan(self, app, **kwargs):
        with mock.patch.object(store, "launch_spec_running", return_value=False):
            return daily.plan_for(app, **kwargs)

    def test_v4_migration_adds_card_preserves_saved_paths_order_selections(self):
        nte = self.put("custom MaaNTE/MaaNTE.exe")
        launcher = self.put("Neverness To Everness/NTELauncher.exe")
        maa = self.put("custom MAA/MAA.exe")
        saved_daily = {"enabled": False, "instance": "My saved selection", "timeout_min": 37,
                       "extra_args": ["--saved"], "close_after": False}
        raw = {"version": 4, "root": str(self.tmp),
               "daily_order": ["wuwa", "maaend", "nte", "maa"],
               "apps": {"nte": {"script_exe": nte, "game_exe": launcher,
                                  "game_procs": ["HTGAME.EXE"], "daily": saved_daily},
                        "maa": {"script_exe": maa, "daily": {"enabled": True}}}}
        cfg = self.write_json("hub-fixture.json", raw)
        with mock.patch.object(store, "CONFIG", cfg):
            apps, _, root, meta = store.load_state_full()
            by_key = {app["key"]: app for app in apps}
            self.assertEqual(len(apps), 5)
            self.assertEqual(by_key["nte"]["script"], "MaaNTE")
            self.assertEqual(by_key["nte"]["script_exe"], nte)
            self.assertEqual(by_key["maa"]["script_exe"], maa)
            self.assertEqual(by_key["nte"]["game_exe"], launcher)
            for field, value in saved_daily.items():
                self.assertEqual(by_key["nte"]["daily"][field], value)
            self.assertFalse(by_key["oknte"]["daily"]["enabled"])
            self.assertEqual(by_key["oknte"]["daily"]["task"], "DailyRoutineTask")
            self.assertEqual(meta["daily_order"], raw["daily_order"] + ["oknte"])
            self.assertEqual(by_key["oknte"]["game_exe"], launcher)
            self.assertTrue(store.save_state(apps, "", root, meta["daily_order"], meta["settings"]))
            again, _, _, meta2 = store.load_state_full()
        self.assertEqual(meta2["daily_order"], meta["daily_order"])
        self.assertFalse(next(a for a in again if a["key"] == "oknte")["daily"]["enabled"])
        with open(cfg, encoding="utf-8") as fh:
            persisted = json.load(fh)
        self.assertEqual(persisted["version"], 4)
        self.assertIn("nte", persisted["apps"])
        self.assertIn("oknte", persisted["apps"])

    def test_launch_metadata_environment_and_version(self):
        app, p = self.install()
        spec = app["launch"]
        self.assertEqual(spec["type"], "python")
        for field, expected in (("exe", p["pythonw"]), ("script", p["script"]),
                                ("cwd", p["cwd"]), ("launcher_exe", p["launcher"])):
            self.assertEqual(spec[field], expected)
        self.assertEqual(spec["process_exe_dirs"], [str(Path(p["pythonw"]).parent)])
        self.assertEqual(spec["process_exe_names"], ["pythonw.exe", "python.exe"])
        self.assertEqual(spec["fallback"], "launcher")
        self.assertEqual(store.read_version(app), "v9.8.7")
        for name, expected in (("PYAPPIFY_APP_VERSION", "v9.8.7"), ("PYAPPIFY_APP_PROFILE", "China"),
                               ("PYAPPIFY_APP_JSON_PATH", p["meta"]), ("PYAPPIFY_EXECUTABLE", p["launcher"])):
            self.assertEqual(spec["env"][name], expected)
        with mock.patch.dict(os.environ, {"PYTHONHOME": "bad", "PYTHONPATH": "bad", "PYAPPIFY_PID": "99"}):
            env = store._launch_env(spec)
        for name in ("PYTHONHOME", "PYTHONPATH", "PYAPPIFY_PID"):
            self.assertNotIn(name, env)
        for name, expected in store.LAUNCH_ENV_SET.items():
            self.assertEqual(env[name], expected)
        self.assertEqual(env["PATH"], store._wrapper_path())
        with mock.patch.object(store.subprocess, "Popen") as popen:
            self.assertEqual(store.launch_app(app), (True, "", "script"))
        self.assertEqual(popen.call_args.args[0], [p["pythonw"], p["script"]])
        self.assertEqual(popen.call_args.kwargs["cwd"], p["cwd"])
        self.assertEqual(popen.call_args.kwargs["env"]["PYAPPIFY_APP_VERSION"], "v9.8.7")
        with mock.patch.object(store, "launch_exe", return_value=(True, "")) as updater:
            self.assertEqual(store.launch_updater(app), (True, ""))
        updater.assert_called_once_with(p["launcher"])

    def test_version_refresh_and_malformed_metadata_fallback(self):
        app, p = self.install()
        Path(p["meta"]).write_text(json.dumps({"current_version": "v9.9.0", "current_profile": "Global"}), encoding="utf-8")
        self.assertTrue(store.refresh_launch_spec(app))
        self.assertEqual(app["launch"]["env"]["PYAPPIFY_APP_VERSION"], "v9.9.0")
        self.assertEqual(store.read_version(app), "v9.9.0")
        for data in ("not-json", "{}", '{"current_version": null}', '{"current_version": []}'):
            with self.subTest(metadata=data):
                Path(p["meta"]).write_text(data, encoding="utf-8")
                self.assertEqual(store.read_version(app), app["fallback_version"])
                self.assertTrue(store.refresh_launch_spec(app))

    def test_missing_main_or_python_falls_back_only_to_updater(self):
        for missing in ("script", "pythonw"):
            with self.subTest(missing=missing):
                app, p = self.install(prefix=missing)
                Path(p[missing]).unlink()  # Known fixture path within this test's TemporaryDirectory.
                with mock.patch.object(store, "launch_exe", return_value=(True, "")) as launch:
                    self.assertEqual(store.launch_app(app), (True, "", "launcher"))
                launch.assert_called_once_with(p["launcher"])
                Path(p["launcher"]).unlink()
                self.assertFalse(store.launch_app(app)[0])
                self.assertFalse(store.launch_updater(app)[0])

    def test_python_process_isolation_between_okww_oknte_and_nested_other_python(self):
        app, nte = self.install()
        ww_app, ww = self.install("wuwa")
        paths = {11: nte["pythonw"], 12: nte["python"], 21: ww["pythonw"],
                 22: ww["python"], 31: str(Path(nte["pythonw"]).parent / "child/pythonw.exe"),
                 32: str(Path(nte["pythonw"]).parent) + "-other\\pythonw.exe",
                 41: nte["launcher"], 42: "", 43: r"C:\OtherPython\pythonw.exe"}
        with mock.patch.object(store, "pids_for_procs", return_value=set(paths)), \
                mock.patch.object(store, "process_path", side_effect=paths.get):
            self.assertEqual(store.launch_running_pids(app), {11, 12})
            self.assertEqual(store.launch_running_pids(ww_app), {21, 22})
        with mock.patch.object(store, "pids_for_procs", return_value={42}), \
                mock.patch.object(store, "process_path", return_value=""):
            self.assertFalse(store.launch_spec_running(app))

    def test_daily_registered_task_config_path_and_quoted_arguments(self):
        app, p = self.install()
        plan = self.plan(app)
        self.assertTrue(plan["ok"], plan["errors"])
        self.assertEqual(plan["args"], [p["script"], "-t", "DailyRoutineTask", "-e"])
        self.assertEqual(plan["argv"], [p["pythonw"]] + plan["args"])
        self.assertIn('-t DailyRoutineTask -e', plan["params"])
        self.assertIn('"' + p["script"] + '"', plan["params"])
        self.assertEqual(plan["cwd"], p["cwd"])
        self.assertEqual(plan["log_path"], p["log"])
        self.assertEqual(daily.ok_script_paths(app)["daily_config"], p["config"])
        self.assertEqual(plan["success_patterns"], [daily.OKWW_SUCCESS_MARKER])
        self.assertEqual(plan["warnings"], [])
        self.assertNotIn("pre_game", plan)
        custom = self.plan(app, settings={"task": 'A task "quoted"', "extra_args": ["--fixture"]})
        self.assertEqual(custom["args"], [p["script"], "-t", 'A task "quoted"', "-e", "--fixture"])
        self.assertEqual(custom["params"], daily._build_command(p["pythonw"], custom["args"], force_quote={0})["params"])

    def test_missing_daily_config_warns_without_creating_it(self):
        app, p = self.install()
        Path(p["config"]).unlink()
        # A legacy DailyTask file must not satisfy the registered routine's config check.
        self.put(Path(p["cwd"]).relative_to(self.tmp) / "configs/DailyTask.json", "{}")
        plan = self.plan(app)
        self.assertTrue(plan["ok"], plan["errors"])
        self.assertTrue(any("DailyRoutineTask.json" in warning for warning in plan["warnings"]), plan)
        self.assertFalse(Path(p["config"]).exists())
        for field in ("script", "pythonw"):
            app2, p2 = self.install(prefix="missing_" + field)
            Path(p2[field]).unlink()
            plan2 = self.plan(app2)
            self.assertFalse(plan2["ok"])
            self.assertIn("ok-nte", " ".join(plan2["errors"]))

    def test_running_script_guard_uses_isolated_launch_spec_not_name(self):
        app, _ = self.install()
        with mock.patch.object(store, "snapshot_processes", return_value={"PYTHONW.EXE", "OK-NTE.EXE"}), \
                mock.patch.object(store, "launch_spec_running", return_value=False):
            self.assertFalse(daily._script_running(app))
        with mock.patch.object(store, "launch_spec_running", return_value=True):
            plan = daily.plan_for(app)
        self.assertFalse(plan["ok"])
        self.assertTrue(any("已在运行" in error for error in plan["errors"]))

    def test_shared_runner_completion_failure_timeout_stop_and_incremental_log(self):
        for case in ("success", "routine_failure", "report_failure", "no_marker", "old_marker", "timeout", "stop", "launch_error"):
            with self.subTest(case=case):
                app, p = self.install(prefix=case)
                app["daily"]["timeout_min"] = 1
                clock = Clock()
                stop = threading.Event()
                if case == "old_marker":
                    Path(p["log"]).write_text(daily.OKWW_SUCCESS_MARKER + "\n", encoding="utf-8")
                def on_wait(handle):
                    if handle.calls == 1 and case in ("success", "routine_failure", "report_failure"):
                        with open(p["log"], "a", encoding="utf-8") as fh:
                            if case == "routine_failure":
                                fh.write("ERROR DailyRoutineTask:任务失败: coffee\n")
                            if case == "report_failure":
                                fh.write("Status: ⚠️ Finished with failures\n")
                            fh.write(daily.OKWW_SUCCESS_MARKER + "\n")
                    if case == "stop":
                        stop.set()
                handle = Handle(clock, exit_after=2 if case in ("success", "routine_failure", "report_failure", "no_marker", "old_marker") else None, on_wait=on_wait)
                launcher = mock.Mock(return_value=handle)
                if case == "launch_error":
                    launcher.side_effect = daily.DailyError("mock UAC cancelled")
                events = []
                with mock.patch.object(daily, "_now", clock.now), \
                        mock.patch.object(daily, "_sleep", clock.sleep), \
                        mock.patch.object(store, "launch_spec_running", return_value=False):
                    result = daily.run(app, launcher=launcher, stop_event=stop, on_event=events.append)
                expected = {"success": daily.FINISHED, "routine_failure": daily.FAILED,
                            "report_failure": daily.FAILED, "no_marker": daily.FAILED,
                            "old_marker": daily.FAILED, "timeout": daily.TIMEOUT,
                            "stop": daily.STOPPED, "launch_error": daily.FAILED}[case]
                self.assertEqual(result["state"], expected, result)
                self.assertEqual(result["key"], "oknte")
                launcher.assert_called_once()
                self.assertEqual(launcher.call_args.args[0], p["pythonw"])
                self.assertEqual(handle.terminated, case in ("timeout", "stop"))
                if case != "launch_error":
                    self.assertTrue(handle.closed)
                self.assertTrue(any(e.get("type") == "done" for e in events))

    def test_default_disabled_dry_run_selection_and_maante_remains_separate(self):
        app, _ = self.install()
        nte = store.make_builtin("nte", str(self.tmp))
        nte["daily"] = store._clean_daily({"enabled": True}, "nte")
        with mock.patch.object(daily, "plan_for", side_effect=lambda a: {"key": a["key"]}):
            self.assertEqual(daily.dry_run([app, nte], order=["oknte", "nte"], include_disabled=False), [{"key": "nte"}])
        self.assertEqual(nte["script"], "MaaNTE")
        self.assertEqual(daily.effective_settings(nte)["task"], "")
        self.assertEqual(daily.effective_settings(app)["task"], "DailyRoutineTask")

    def test_nte_launcher_alias_and_detector_states_are_correct(self):
        app, _ = self.install()
        launcher = self.put("Neverness To Everness/NTELauncher.exe")
        game = self.put(Path("Neverness To Everness").joinpath(*store.NTE_GAME_RELATIVE))
        app["game_exe"] = game
        self.assertEqual(store._game_profile(app), store._game_profile({"key": "nte"}))
        self.assertEqual(store.resolve_game_exe(app), launcher)
        spec = store.build_game_launch(app)
        self.assertEqual(spec["strategy"], "launcher")
        self.assertEqual(spec["exe"], launcher)
        self.assertEqual(spec["args"], [])
        self.assertEqual(spec["wait"]["timeout_s"], 180)
        self.assertEqual(detector.read_auto_rules(app), detector.read_auto_rules({"key": "nte"}))
        for title, running, reason in (("异环", True, "window"), ("NTE", True, "window"),
                                      ("鸣潮", False, "")):
            win = {"hwnd": 7, "class_name": "UnrealWindow", "title": title,
                   "width": 1280, "height": 720, "pid": 999}
            state = detector.detect_game_state(app, windows=[win], processes=set(), adb_enabled=False)
            self.assertEqual((state["running"], state["reason"]), (running, reason))
        state = detector.detect_game_state(app, windows=[], processes={"NTELAUNCHER.EXE"}, adb_enabled=False)
        self.assertEqual((state["running"], state["reason"]), (False, "launcher"))
        state = detector.detect_game_state(app, windows=[], processes={"HTGAME.EXE"}, adb_enabled=False)
        self.assertEqual((state["running"], state["reason"]), (True, "proc"))
        user = copy.deepcopy(app)
        user["detect"] = {"any_of": [{"type": "proc", "names": ["CUSTOM.EXE"]}]}
        self.assertEqual(detector.read_game_rules(user)["source"], "user")


if __name__ == "__main__":
    unittest.main(verbosity=2)
