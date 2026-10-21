# -*- coding: utf-8 -*-
"""Offline SendInput ABI and hotkey tests; never sends real input.

Run on Windows: python tools/test_hotkey.py
"""
import ctypes
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from gamehub import daily  # noqa: E402


class HotkeyTests(unittest.TestCase):
    def setUp(self):
        # Replace the entire API object: no test can fall through to user32.
        self.api = mock.Mock()
        self.api.SendInput.side_effect = AssertionError("unconfigured mock call")
        self.patch_api = mock.patch.object(daily, "user32", self.api)
        self.patch_api.start()
        self.addCleanup(self.patch_api.stop)
        self.patch_log = mock.patch.object(daily, "log_event")
        self.log = self.patch_log.start()
        self.addCleanup(self.patch_log.stop)
        ctypes.set_last_error(0)
        self.addCleanup(ctypes.set_last_error, 0)

    def test_native_layout(self):
        wide = ctypes.sizeof(ctypes.c_void_p) == 8
        self.assertEqual(ctypes.sizeof(daily.INPUT), 40 if wide else 28)
        self.assertEqual(daily.INPUT.u.offset, 8 if wide else 4)
        self.assertEqual(ctypes.sizeof(daily.MOUSEINPUT), 32 if wide else 24)
        self.assertEqual(ctypes.sizeof(daily.KEYBDINPUT), 24 if wide else 16)
        self.assertEqual(ctypes.sizeof(daily.HARDWAREINPUT), 8)
        self.assertEqual(daily.KEYBDINPUT.dwExtraInfo.offset, 16 if wide else 12)
        self.assertEqual(daily.MOUSEINPUT.dwExtraInfo.offset, 24 if wide else 20)
        self.assertEqual(ctypes.sizeof(daily.ULONG_PTR), ctypes.sizeof(ctypes.c_void_p))
        self.assertEqual(daily.KEYBDINPUT().dwExtraInfo, 0)
        self.assertEqual(daily.MOUSEINPUT().dwExtraInfo, 0)
        self.assertEqual([name for name, _ in daily._INPUTUNION._fields_], ["mi", "ki", "hi"])
        for name in ("mi", "ki", "hi"):
            self.assertEqual(getattr(daily._INPUTUNION, name).offset, 0)

    def test_both_pointer_width_layouts(self):
        # Reuse production fields, substituting only ULONG_PTR to model both ABIs.
        for pointer_type, size, union_offset, extra_offset in (
                (ctypes.c_uint32, 28, 4, 12), (ctypes.c_uint64, 40, 8, 16)):
            with self.subTest(pointer_bytes=ctypes.sizeof(pointer_type)):
                def fields(cls):
                    return [(name, pointer_type if name == "dwExtraInfo" else typ)
                            for name, typ in cls._fields_]
                mouse = type("Mouse", (ctypes.Structure,), {"_fields_": fields(daily.MOUSEINPUT)})
                keyboard = type("Keyboard", (ctypes.Structure,), {"_fields_": fields(daily.KEYBDINPUT)})
                union = type("Union", (ctypes.Union,), {"_fields_": [
                    ("mi", mouse), ("ki", keyboard), ("hi", daily.HARDWAREINPUT)]})
                inp = type("Input", (ctypes.Structure,), {"_fields_": [
                    ("type", ctypes.c_uint32), ("u", union)]})
                self.assertEqual(ctypes.sizeof(inp), size)
                self.assertEqual(inp.u.offset, union_offset)
                self.assertEqual(keyboard.dwExtraInfo.offset, extra_offset)

    def test_success_event_order_and_key_order(self):
        order = []
        def send(count, array, size):
            order.append("send")
            self.assertEqual(ctypes.get_last_error(), 0)
            self.assertEqual(size, ctypes.sizeof(daily.INPUT))
            self.assertEqual(count, 6)
            self.assertEqual([(item.u.ki.wVk, item.u.ki.dwFlags) for item in array],
                             [(0x11, 0), (0x10, 0), (0x79, 0),
                              (0x79, 2), (0x10, 2), (0x11, 2)])
            for item in array:
                self.assertEqual(item.type, daily.INPUT_KEYBOARD)
                self.assertEqual((item.u.ki.wScan, item.u.ki.time, item.u.ki.dwExtraInfo), (0, 0, 0))
            ctypes.set_last_error(123)
            return count
        def log(event, **fields):
            order.append(event)
            self.assertEqual(fields, dict(sent=6, expected=6,
                struct_size=ctypes.sizeof(daily.INPUT), last_error=123))
            ctypes.set_last_error(999)
        self.api.SendInput.side_effect = send
        self.log.side_effect = log
        ctypes.set_last_error(777)
        self.assertIs(daily.send_hotkey({"key": "F10", "modifiers": ["Ctrl", "Shift"]}), True)
        self.assertEqual(order, ["send", "hotkey_send"])
        self.api.SendInput.assert_called_once()

    def test_partial_and_zero_send(self):
        for sent in (0, 1):
            with self.subTest(sent=sent):
                order = []
                def send(*args):
                    order.append("send")
                    ctypes.set_last_error(5)
                    return sent
                def log(event, **fields):
                    order.append(event)
                    # Logging deliberately clobbers last error; both events retain it.
                    self.assertEqual(fields["last_error"], 5)
                    self.assertEqual(fields["sent"], sent)
                    self.assertEqual(fields["expected"], 2)
                    ctypes.set_last_error(999)
                self.api.SendInput.side_effect = send
                self.log.side_effect = log
                self.assertIs(daily.send_hotkey({"key": "A"}), False)
                self.assertEqual(order, ["send", "hotkey_send", "hotkey_send_error"])
                self.assertEqual(self.log.call_args.kwargs["error_type"], "incomplete_send")

    def test_exception_is_false_and_logs_metadata_only(self):
        order = []
        def send(*args):
            order.append("send")
            ctypes.set_last_error(87)
            raise OSError("do not include arbitrary exception text or config")
        self.api.SendInput.side_effect = send
        self.log.side_effect = lambda event, **fields: order.append(event)
        self.assertIs(daily.send_hotkey({"key": "F10", "modifiers": ["Ctrl"]}), False)
        self.assertEqual(order, ["send", "hotkey_send_error"])
        self.log.assert_called_once_with("hotkey_send_error", sent=0, expected=4,
            struct_size=ctypes.sizeof(daily.INPUT), last_error=87, error_type="OSError")

    def test_invalid_input_never_calls_api(self):
        for value in (None, [], "Ctrl+F10", {}, {"key": "unsupported"}):
            self.assertIs(daily.send_hotkey(value), False)
        self.api.SendInput.assert_not_called()
        self.log.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
