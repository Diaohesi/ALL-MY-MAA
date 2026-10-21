# -*- coding: utf-8 -*-
"""Offline temp-only runtime log tests. Never launches scripts, games or UI."""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import threading
import types
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gamehub import runtime_log as logs


class RuntimeLogTests(unittest.TestCase):
    def setUp(self):
        self.hooks = (sys.excepthook, threading.excepthook)
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        logs.shutdown_logging()

    def tearDown(self):
        logs.shutdown_logging()
        sys.excepthook, threading.excepthook = self.hooks
        self.temp.cleanup()

    def text(self):
        logs._handler.flush()
        return logs.current_log_path().read_text(encoding="utf-8")

    def test_structure_redaction_and_objects(self):
        logs.setup_logging(self.root)
        class Unsafe:
            def __repr__(self):
                raise AssertionError("must not dump arbitrary objects")
        cycle = []
        cycle.append(cycle)
        logs.log_event("test", nested={"Password": "P4SS", "items": [
            {"refresh_token": "T0KEN", "cdk": "C0DE", "cookies": "C00KIE",
             "authorization": "AUTH", "secret": "S3CRET"}]},
            url="https://alice:URLPASS@example.test/?anything=QUERYSECRET#fragment",
            win=r"C:\Users\Alice\Desktop\main.py", posix="/home/bob/main.py",
            command='run --token CLISECRET --password="QUOTEDSECRET"',
            environment={"FOO": "ENVSECRET"}, config={"x": "CONFIGSECRET"},
            arbitrary=Unsafe(), cycle=cycle)
        text = self.text()
        for secret in ("P4SS", "T0KEN", "C0DE", "C00KIE", "AUTH", "S3CRET",
                       "URLPASS", "QUERYSECRET", "Alice", "bob", "CLISECRET",
                       "QUOTEDSECRET", "ENVSECRET", "CONFIGSECRET"):
            self.assertNotIn(secret, text)
        row = json.loads(text.splitlines()[-1])
        self.assertEqual(row["event"], "test")
        self.assertTrue(row["session_id"])
        self.assertEqual(row["level"], "INFO")
        self.assertIn("timestamp", row)
        self.assertIn("thread", row)

    def test_rotation(self):
        logs.setup_logging(self.root)
        self.assertEqual(logs._handler.maxBytes, 2 * 1024 * 1024)
        self.assertEqual(logs._handler.backupCount, 4)
        # Use a smaller real threshold to exercise rotation quickly/offline.
        logs._handler.maxBytes = 900
        for index in range(60):
            logs.log_event("rotate", index=index, data="x" * 200)
        self.text()
        self.assertEqual(len(list((self.root / "logs").glob("hub.log*"))), 5)
        for path in (self.root / "logs").glob("hub.log*"):
            self.assertLessEqual(path.stat().st_size, 900)

    def test_export_allowlist_fresh_redaction_and_bounds(self):
        path = logs.setup_logging(self.root)
        logs.log_event("export_test")
        logs._handler.flush()
        path.with_name("script.log").write_text("EXTERNALSECRET")
        path.with_name("config.json").write_text("CONFIGSECRET")
        Path(str(path) + ".5").write_text("OLDSECRET")
        Path(str(path) + ".1").write_text(
            '{"event":"legacy", "fields":{"password":"LEGACYSECRET", '
            '"url":"https://example.test/?x=QUERYSECRET"}}\n', encoding="utf-8")
        Path(str(path) + ".2").write_text("z" * (logs.MAX_BYTES + 100))
        target = logs.export_diagnostics(self.root / "chosen.zip")
        with zipfile.ZipFile(target) as archive:
            self.assertEqual(set(archive.namelist()), {"hub.log", "hub.log.1", "hub.log.2"})
            text = "\n".join(archive.read(name).decode() for name in archive.namelist())
            for secret in ("LEGACYSECRET", "QUERYSECRET", "EXTERNALSECRET", "CONFIGSECRET", "OLDSECRET"):
                self.assertNotIn(secret, text)
            self.assertLessEqual(len(archive.read("hub.log.2")), logs.MAX_BYTES + 1)
        with self.assertRaises(OSError):
            logs.export_diagnostics(path)

    def test_fallback_and_total_failure(self):
        blocked = self.root / "not-a-directory"
        blocked.write_text("blocked")
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(self.root / "local")}):
            path = logs.setup_logging(blocked)
            self.assertEqual(path, self.root / "local" / "All-My-Maa" / "logs" / "hub.log")
        logs.shutdown_logging()
        with mock.patch.object(logs, "_SafeHandler", side_effect=PermissionError):
            self.assertIsNone(logs.setup_logging(self.root))
            logs.log_event("safe_without_storage")
            with self.assertRaises(OSError):
                logs.export_diagnostics(self.root / "none.zip")

    def test_hooks_and_redacted_tracebacks(self):
        previous = (sys.excepthook, threading.excepthook)
        logs.setup_logging(self.root)
        try:
            raise RuntimeError("password=HOOKSECRET /Users/charlie/test.py")
        except RuntimeError:
            info = sys.exc_info()
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            sys.excepthook(*info)
            threading.excepthook(types.SimpleNamespace(
                exc_type=info[0], exc_value=info[1], exc_traceback=info[2]))
        text = self.text()
        self.assertIn("Traceback", text)
        self.assertIn("RuntimeError", text)
        self.assertNotIn("HOOKSECRET", text)
        self.assertNotIn("charlie", text)
        self.assertEqual(output.getvalue(), "")
        logs.shutdown_logging()
        self.assertIs(sys.excepthook, previous[0])
        self.assertIs(threading.excepthook, previous[1])

    def test_logging_errors_never_escape(self):
        logs.setup_logging(self.root)
        with mock.patch.object(logs._handler, "shouldRollover", side_effect=OSError("disk failed")):
            logs.log_event("safe")
            logs.get_logger("ui").exception("safe")
        self.assertEqual(logs.setup_logging(self.root), logs.current_log_path())

    def test_daily_events_are_allowlisted(self):
        from gamehub import daily
        logs.setup_logging(self.root)
        plan = {"key": "offline", "game": "test", "mode": "okww", "ok": True,
                "exe": r"C:\Users\User Name\main.exe", "timeout_min": 1,
                "errors": [], "warnings": [], "settings": {"secret": "PLANSECRET"}}
        with mock.patch.object(daily, "plan_for", return_value=plan):
            result = daily.run({}, dry_run=True)
        self.assertEqual(result["state"], daily.DRY_RUN)
        daily._emit(None, type="done", result={"key": "offline", "state": daily.TIMEOUT,
                    "pid": 42, "duration": 3, "log_tail": "EXTERNALLOGSECRET",
                    "reason": "REASONSECRET", "command": "--token COMMANDSECRET"})
        text = self.text()
        for secret in ("User Name", "PLANSECRET", "EXTERNALLOGSECRET", "REASONSECRET", "COMMANDSECRET"):
            self.assertNotIn(secret, text)
        rows = [json.loads(line) for line in text.splitlines()]
        self.assertTrue({"daily_plan", "daily_result", "daily_timeout"} <= {row["event"] for row in rows})
        self.assertEqual(len({row["session_id"] for row in rows}), 1)

    def test_entrypoint_check_temp_only_stdout(self):
        from gamehub import elevation
        output = io.StringIO()
        with mock.patch.object(logs, "setup_logging", side_effect=lambda app: None), \
             mock.patch.object(sys, "argv", [str(ROOT / "hub.pyw"), "--elevation-check"]), \
             mock.patch.object(elevation, "elevation_status", return_value={"admin": False, "would_elevate": True}), \
             contextlib.redirect_stdout(output):
            runpy.run_path(str(ROOT / "hub.pyw"), run_name="__main__")
        self.assertEqual(json.loads(output.getvalue()), {"admin": False, "would_elevate": True})
        self.assertFalse((ROOT / "logs").exists() and logs.current_log_path())


if __name__ == "__main__":
    unittest.main()
