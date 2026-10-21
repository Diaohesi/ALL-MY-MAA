"""Offline close/minimize routing tests; no GUI or processes started."""
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gamehub import ui

class ClosePromptTests(unittest.TestCase):
    def hub(self, action='cancel', busy=False):
        root=mock.Mock()
        manager=mock.Mock()
        manager.snapshot.return_value={'busy':busy}
        hub=SimpleNamespace(root=root, daily_manager=manager, tray=mock.Mock(),
                            settings={'close_action':'exit'}, _closing=False,
                            _choose_close_action=mock.Mock(return_value=action),
                            _hide_to_tray=mock.Mock(return_value=True),
                            _minimize_to_taskbar=mock.Mock(return_value=True), _toast=mock.Mock())
        return hub

    def test_cancel_always_prompts_and_keeps_window(self):
        h=self.hub()
        ui.GameHub._on_close(h)
        h._choose_close_action.assert_called_once()
        h.root.destroy.assert_not_called()
        self.assertFalse(h._closing)

    def test_explicit_taskbar_is_not_overridden_by_tray_preference(self):
        h=self.hub('taskbar'); h.settings['minimize_to_tray']=True
        ui.GameHub._on_close(h)
        h._minimize_to_taskbar.assert_called_once()
        h._hide_to_tray.assert_not_called()
        h.root.destroy.assert_not_called()

    def test_tray_unavailable_falls_back_to_taskbar(self):
        h=self.hub('tray'); h._hide_to_tray.return_value=False
        ui.GameHub._on_close(h)
        h._hide_to_tray.assert_called_once_with(force=True)
        h._minimize_to_taskbar.assert_called_once()
        h.root.destroy.assert_not_called()

    def test_exit_stops_busy_task_before_destroy(self):
        h=self.hub('exit',True)
        ui.GameHub._on_close(h)
        h.daily_manager.stop_all.assert_called_once()
        h.root.destroy.assert_not_called()
        self.assertTrue(h._exit_waiting)
        h.root.after.assert_called_once()
        h.daily_manager.snapshot.return_value={'busy':False}
        ui.GameHub._on_close(h,force=True)
        h.root.destroy.assert_called_once()
        h.tray.stop.assert_called_once()

    def test_stop_timeout_allows_cancel_or_explicit_exit(self):
        for abandon in (False, True):
            h=self.hub('exit',True)
            h._exit_waiting=True; h._exit_wait_started=0
            with mock.patch.object(ui.time,'monotonic',return_value=16), mock.patch.object(ui.messagebox,'askyesno',return_value=abandon) as prompt:
                ui.GameHub._on_close(h,force=True)
            prompt.assert_called_once()
            self.assertEqual(h.root.destroy.called,abandon)
            h.root.after.assert_not_called()

    def test_daily_state_does_not_collect_external_tails(self):
        import queue
        h=SimpleNamespace(daily_events=queue.Queue())
        with mock.patch.object(ui.runtime_log,'log_event') as log:
            ui.GameHub._daily_manager_event(h,{'type':'state','key':'oknte','state':{
                'state':'failed','log_tail':'PRIVATE_EXTERNAL_LOG',
                'command':'PRIVATE_COMMAND','reason':'PRIVATE_REASON'}})
        fields=log.call_args.kwargs
        self.assertEqual(fields['state'],'failed')
        self.assertNotIn('PRIVATE',str(fields))

    def test_minimize_native_failure_visible_and_logged(self):
        h=self.hub(); h.root._gamehub_window_state_error='mock native failure'
        with mock.patch.object(ui.window_state,'minimize_to_taskbar',return_value=False):
            self.assertFalse(ui.GameHub._minimize_to_taskbar(h))
        h._toast.assert_called_once()
        h.root.withdraw.assert_not_called()

if __name__=='__main__':
    unittest.main(verbosity=2)
