"""Deterministic startup readiness tests; never launch apps or inject input."""
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gamehub import daily


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.debug = self.base / 'debug'
        self.debug.mkdir()
        self.path = self.debug / 'old.log'
        self.path.write_text('historical\n', encoding='utf-8')
        self.clock = 0
        self.events = []
        self.stop = threading.Event()
        self.tick = lambda: None
        self.plan = dict(key='nte', exe='never-launch.exe', cwd=str(self.base),
                         log_path=str(self.path), hotkey={'text': 'Ctrl+F10'},
                         timeout_min=1)
        self.watcher = daily.LogWatcher(str(self.path))
        self.now_patch = mock.patch.object(daily, '_now', lambda: self.clock)
        self.sleep_patch = mock.patch.object(daily, '_sleep', self.sleep)
        self.now_patch.start()
        self.sleep_patch.start()
        self.addCleanup(self.now_patch.stop)
        self.addCleanup(self.sleep_patch.stop)

    def sleep(self, seconds):
        self.clock += seconds
        self.tick()

    def append(self, text, path=None):
        with (path or self.path).open('a', encoding='utf-8', newline='') as fh:
            fh.write(text)

    def readiness(self):
        return daily._MxuStartupReadiness(self.plan, self.watcher)

    def test_delayed_both_markers_and_existing_offset(self):
        ready = self.readiness()
        def tick():
            if self.clock == 1:
                self.append('全局快捷键已注册\n')
            if self.clock == 3:
                self.append('加载完成\n')
        self.tick = tick
        self.assertEqual(ready.wait(self.stop, self.events.append), 'ready')
        self.assertEqual(self.clock, 3)
        self.append('tasks-completed\n')
        self.assertEqual(self.watcher.read(), 'tasks-completed\n')

    def test_old_markers_ignored_and_logged_fallback_bounded(self):
        self.append('全局快捷键已注册\n加载完成\n')
        self.watcher.reset()
        ready = self.readiness()
        self.assertEqual(ready.wait(self.stop, self.events.append), 'fallback')
        self.assertEqual(self.clock, 15)
        self.assertTrue(any('兼容宽限回退' in e.get('text', '') for e in self.events))

    def test_rotation_reads_new_file_from_zero(self):
        ready = self.readiness()
        new = self.debug / '2026-10-22-1.log'
        self.tick = lambda: new.write_text('全局快捷键已注册\n加载完成\n', encoding='utf-8')
        self.assertEqual(ready.wait(self.stop, self.events.append), 'ready')
        self.assertEqual(self.watcher.path, str(new))
        self.append('tasks-completed\n', new)
        self.assertEqual(self.watcher.read(), 'tasks-completed\n')

    def test_no_log_at_launch_then_created(self):
        self.plan['log_path'] = ''
        self.watcher = daily.LogWatcher('')
        ready = self.readiness()
        new = self.debug / 'new.log'
        self.tick = lambda: new.write_text('全局快捷键已注册\n加载完成\n', encoding='utf-8')
        self.assertEqual(ready.wait(self.stop, self.events.append), 'ready')
        self.assertEqual(self.watcher.path, str(new))

    def test_partial_marker_times_out_not_fallback(self):
        ready = self.readiness()
        self.append('全局快捷键已注册\n')
        self.assertEqual(ready.wait(self.stop, self.events.append), 'timeout')
        self.assertEqual(self.clock, 30)

    def test_truncated_log_reads_fresh_markers(self):
        self.append('old padding ' * 100)
        self.watcher.reset()
        ready = self.readiness()
        self.path.write_text('全局快捷键已注册\n加载完成\n', encoding='utf-8')
        self.assertTrue(ready.poll())

    def test_marker_split_across_polls(self):
        ready = self.readiness()
        self.append('全局快捷键')
        self.assertFalse(ready.poll())
        self.append('已注册\n加载')
        self.assertFalse(ready.poll())
        self.append('完成\n')
        self.assertTrue(ready.poll())

    def test_cancellation(self):
        ready = self.readiness()
        self.tick = self.stop.set
        self.assertEqual(ready.wait(self.stop, self.events.append), 'stopped')
        self.assertEqual(self.clock, .25)

    def test_ui_window_does_not_send_until_ready_and_sends_once(self):
        handle = mock.Mock(pid=123)
        sent_at = []
        def tick():
            if self.clock == 2:
                self.append('全局快捷键已注册\n')
            if self.clock == 4:
                self.append('加载完成\n')
        self.tick = tick
        with mock.patch.object(daily, '_mxu_ui_window', return_value={'hwnd': 1}), \
             mock.patch.object(daily.detector, 'focus_window'), \
             mock.patch.object(daily, 'send_hotkey', side_effect=lambda key: sent_at.append(self.clock) or True), \
             mock.patch.object(daily, 'mxu_http_state', return_value={'ok': True, 'status': 'succeeded'}):
            result = daily._run_mxu_ui(self.plan, self.stop, self.events.append, lambda *args: handle)
        self.assertEqual(result['state'], daily.FINISHED)
        self.assertEqual(sent_at, [4.4])
        handle.terminate.assert_not_called()

    def test_ui_cancellation_never_sends(self):
        handle = mock.Mock(pid=123)
        self.tick = self.stop.set
        with mock.patch.object(daily, '_mxu_ui_window', return_value={'hwnd': 1}), \
             mock.patch.object(daily, 'send_hotkey') as send:
            result = daily._run_mxu_ui(self.plan, self.stop, self.events.append, lambda *args: handle)
        self.assertEqual(result['state'], daily.STOPPED)
        send.assert_not_called()
        handle.terminate.assert_called_once()
        handle.close.assert_called_once()


if __name__ == '__main__':
    unittest.main(verbosity=2)
