"""Mock window-state regression tests; optional --smoke opens ONLY a Tk window.

Run: python tools/test_window_state.py [--smoke]
Smoke automatically restores the demo with Tk after a short delay. Actual
Windows taskbar-button clicking is NOT automated; manually minimize with the
button and click the taskbar entry to verify custom-frame restore visually.
"""
import ctypes
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from gamehub import window_state as ws


class FakeRoot:
    def __init__(self):
        self.override = True
        self.status = 'normal'
        self.mapped = True
        self.calls = []
        self.handlers = {'existing': lambda event: None}
        self.serial = 0
        self.size = '960x640+120+80'
        self.fail_iconify = False
        self.reenter = False

    def winfo_id(self):
        return 0x123456789

    def winfo_ismapped(self):
        return self.mapped

    def state(self):
        return self.status

    def overrideredirect(self, value=None):
        if value is None:
            return self.override
        self.calls.append(('override', value))
        self.override = value
        if self.reenter:
            self.emit()

    def iconify(self):
        self.calls.append(('iconify',))
        if self.fail_iconify:
            raise RuntimeError('iconify failed')
        self.status = 'iconic'
        self.mapped = False
        # A spurious Map during minimization must not undo the transition.
        self.emit()

    def bind(self, sequence, callback, add=None):
        assert sequence == '<Map>' and add == '+'
        self.serial += 1
        key = 'binding-{}'.format(self.serial)
        self.handlers[key] = callback
        return key

    def unbind(self, sequence, key):
        assert sequence == '<Map>'
        del self.handlers[key]

    def emit(self, widget=None):
        event = SimpleNamespace(widget=self if widget is None else widget)
        for callback in list(self.handlers.values()):
            callback(event)

    def map(self):
        self.status = 'normal'
        self.mapped = True
        self.emit()


class Native:
    def __init__(self, style=ws.WS_EX_TOOLWINDOW | 0x10000000):
        self.hwnd = 0xABCDEF012
        self.style = style
        self.iconic = False
        self.calls = []
        self.GetAncestor = Mock(return_value=self.hwnd)
        self.IsWindow = Mock(return_value=True)
        self.IsIconic = Mock(side_effect=lambda hwnd: self.iconic)
        self.SetWindowPos = Mock(return_value=True)
        self.ShowWindow = Mock(side_effect=self.show)
        self.get = Mock(side_effect=lambda hwnd, index: self.style)
        self.set = Mock(side_effect=self.set_style)

    def show(self, hwnd, command):
        self.calls.append((hwnd, command))
        self.iconic = True
        return 0  # A valid ShowWindow result, NOT failure.

    def set_style(self, hwnd, index, value):
        previous = self.style
        self.style = value
        return previous

    def api(self):
        return self, self.get, self.set


class WindowStateTests(unittest.TestCase):
    def setUp(self):
        self.root = FakeRoot()
        # Win32 last-error functions are absent on non-Windows CPython.
        for name, value in (('set_last_error', lambda value: None),
                            ('get_last_error', lambda: 0)):
            if not hasattr(ctypes, name):
                temporary = patch.object(ctypes, name, value, create=True)
                temporary.start()
                self.addCleanup(temporary.stop)

    def native_context(self, native):
        return patch.object(ws, '_native', return_value=native.api())

    def test_native_minimize_preserves_frame_size_and_taskbar(self):
        native = Native()
        with patch.object(ws.sys, 'platform', 'win32'), self.native_context(native):
            self.assertTrue(ws.minimize_to_taskbar(self.root))
        self.assertEqual(native.calls, [(native.hwnd, ws.SW_MINIMIZE)])
        self.assertEqual(native.GetAncestor.call_args.args,
                         (0x123456789, ws.GA_ROOT))
        self.assertTrue(native.style & ws.WS_EX_APPWINDOW)
        self.assertFalse(native.style & ws.WS_EX_TOOLWINDOW)
        self.assertTrue(native.style & 0x10000000)
        self.assertEqual(self.root.calls, [])
        self.assertTrue(self.root.override)
        self.assertEqual(self.root.size, '960x640+120+80')
        args = native.SetWindowPos.call_args.args
        self.assertEqual(args[:6], (native.hwnd, None, 0, 0, 0, 0))
        self.assertEqual(args[6], ws.SWP_NOSIZE | ws.SWP_NOMOVE |
                         ws.SWP_NOZORDER | ws.SWP_NOACTIVATE | ws.SWP_FRAMECHANGED)

    def test_native_style_idempotent_and_minimize_already_iconic(self):
        native = Native(ws.WS_EX_APPWINDOW)
        native.iconic = True
        with patch.object(ws.sys, 'platform', 'win32'), self.native_context(native):
            self.assertTrue(ws.minimize_to_taskbar(self.root))
            self.assertTrue(ws.apply_taskbar_style(self.root))
            self.assertTrue(ws.restore_from_taskbar(self.root))
        native.ShowWindow.assert_not_called()
        native.set.assert_not_called()
        native.SetWindowPos.assert_not_called()
        self.assertEqual(self.root.calls, [])

    def test_fallback_restore_and_repeated_cycles_no_binding_leak(self):
        with patch.object(ws.sys, 'platform', 'linux'):
            for _ in range(4):
                self.assertTrue(ws.minimize_to_taskbar(self.root))
                self.assertFalse(self.root.override)
                self.assertEqual(self.root.status, 'iconic')
                self.assertEqual(len(self.root.handlers), 2)
                self.assertTrue(ws.minimize_to_taskbar(self.root))
                self.assertEqual(len(self.root.handlers), 2)
                self.root.emit()  # Remains iconic: do NOT repair yet.
                self.assertFalse(self.root.override)
                self.root.emit(widget=object())
                self.assertFalse(self.root.override)
                self.root.reenter = True
                self.root.map()
                self.assertTrue(self.root.override)
                self.assertEqual(set(self.root.handlers), {'existing'})
                self.assertFalse(self.root._gamehub_window_state['pending'])
            self.assertTrue(ws.restore_from_taskbar(self.root))
        self.assertEqual(self.root.size, '960x640+120+80')

    def test_fallback_preserves_original_non_borderless_window(self):
        self.root.override = False
        with patch.object(ws.sys, 'platform', 'linux'):
            self.assertTrue(ws.minimize_to_taskbar(self.root))
            self.root.map()
        self.assertFalse(self.root.override)

    def test_fallback_failure_reports_and_rolls_back(self):
        self.root.fail_iconify = True
        with patch.object(ws.sys, 'platform', 'linux'):
            self.assertFalse(ws.minimize_to_taskbar(self.root))
        self.assertTrue(self.root.override)
        self.assertEqual(set(self.root.handlers), {'existing'})
        self.assertIn('iconify failed', self.root._gamehub_window_state_error)

    def test_native_failure_uses_fallback_and_restore_repairs_frame(self):
        with patch.object(ws.sys, 'platform', 'win32'), patch.object(
                ws, '_native', side_effect=OSError('no native API')):
            self.assertTrue(ws.minimize_to_taskbar(self.root))
            self.assertIn('no native API', self.root._gamehub_window_state_error)
            self.root.map()
        self.assertTrue(self.root.override)
        self.assertEqual(set(self.root.handlers), {'existing'})

    def test_native_show_failure_uses_fallback(self):
        native = Native()
        native.ShowWindow = Mock(return_value=1)  # Does not iconify.
        with patch.object(ws.sys, 'platform', 'win32'), self.native_context(native):
            self.assertTrue(ws.minimize_to_taskbar(self.root))
        self.assertEqual(self.root.status, 'iconic')
        self.assertIn('SW_MINIMIZE', self.root._gamehub_window_state_error)

    def test_native_restore_reapplies_style_without_showing(self):
        native = Native()
        with patch.object(ws.sys, 'platform', 'win32'), self.native_context(native):
            self.assertTrue(ws.restore_from_taskbar(self.root))
            self.assertTrue(ws.restore_from_taskbar(self.root))
        native.ShowWindow.assert_not_called()
        self.assertEqual(native.set.call_count, 1)
        self.assertTrue(self.root.override)

    def test_native_style_errors_reported(self):
        native = Native()
        native.SetWindowPos.return_value = False
        with patch.object(ws.sys, 'platform', 'win32'), self.native_context(native):
            self.assertFalse(ws.apply_taskbar_style(self.root))
        self.assertIn('SetWindowPos', self.root._gamehub_window_state_error)
        with patch.object(ws.sys, 'platform', 'linux'):
            self.assertFalse(ws.apply_taskbar_style(self.root))

    def test_invalid_handle_and_style_failure_are_detected(self):
        native = Native()
        native.IsWindow.return_value = False
        with patch.object(ws.sys, 'platform', 'win32'), self.native_context(native):
            self.assertFalse(ws.apply_taskbar_style(self.root))
        native.set.assert_not_called()
        native.IsWindow.return_value = True
        native.set = Mock(return_value=0)  # No last error but fails readback.
        with patch.object(ws.sys, 'platform', 'win32'), self.native_context(native):
            self.assertFalse(ws.apply_taskbar_style(self.root))

    def test_prototypes_are_handle_safe(self):
        dll = SimpleNamespace(**{name: Mock() for name in (
            'GetWindowLongPtrW', 'SetWindowLongPtrW', 'GetWindowLongW',
            'SetWindowLongW', 'GetAncestor', 'IsWindow', 'IsIconic',
            'ShowWindow', 'SetWindowPos')})
        with patch.object(ctypes, 'WinDLL', return_value=dll, create=True):
            loaded, get, set_ = ws._native()
        self.assertIs(loaded, dll)
        self.assertEqual(dll.GetAncestor.restype, ws.wintypes.HWND)
        self.assertEqual(dll.ShowWindow.argtypes, [ws.wintypes.HWND, ctypes.c_int])
        self.assertEqual(set_.argtypes[0], ws.wintypes.HWND)
        self.assertEqual(ctypes.sizeof(get.restype), ctypes.sizeof(ctypes.c_void_p))
        self.assertEqual(ctypes.sizeof(set_.argtypes[2]), ctypes.sizeof(ctypes.c_void_p))


def smoke():
    import tkinter as tk
    root = tk.Tk()
    root.geometry('480x180+120+120')
    root.overrideredirect(True)
    tk.Label(root, text='Window-state smoke (no apps/games launched)').pack(pady=20)
    tk.Button(root, text='Minimize to taskbar',
              command=lambda: ws.minimize_to_taskbar(root)).pack()
    root.bind('<Map>', lambda event: ws.restore_from_taskbar(root, event), add='+')
    root.after(200, lambda: ws.apply_taskbar_style(root)
               if sys.platform == 'win32' else None)
    root.after(500, lambda: ws.minimize_to_taskbar(root))
    root.after(1300, root.deiconify)  # Smoke driver, NEVER the helper.
    root.after(2400, root.destroy)
    root.mainloop()
    print('Smoke completed. Manual taskbar-button click is NOT automated.')


if __name__ == '__main__':
    run_smoke = '--smoke' in sys.argv
    if run_smoke:
        sys.argv.remove('--smoke')
    result = unittest.main(exit=False)
    if not result.result.wasSuccessful():
        raise SystemExit(1)
    if run_smoke:
        smoke()
