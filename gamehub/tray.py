# -*- coding: utf-8 -*-
"""最小化到系统托盘：纯 ctypes Shell_NotifyIconW，不依赖第三方库。

TrayManager 不自动创建托盘；start() 失败时安全降级（返回 False），
不影响主程序。所有 UI 回调通过 root.after(0, ...) 回到 Tk 线程。
"""
import ctypes
import os
import sys
import threading
from ctypes import wintypes

_ENABLED = sys.platform == "win32"
WM_USER = 0x0400
WM_TRAYICON = WM_USER + 20
WM_COMMAND = 0x0111
WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
WM_NULL = 0x0000
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_CONTEXTMENU = 0x007B
NIM_ADD = 0
NIM_MODIFY = 1
NIM_DELETE = 2
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_SHOWTIP = 0x00000080
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x00000010
LR_DEFAULTSIZE = 0x00000040
MF_STRING = 0x00000000
TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100
MENU_SHOW = 1
MENU_EXIT = 2
IDI_APPLICATION = 32512
HWND_MESSAGE = -3
TRAY_UID = 1
CLASS_NAME = "GameHubTrayWindow"


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", GUID),
    ]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", ctypes.c_void_p),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND,
                             wintypes.UINT, wintypes.WPARAM,
                             wintypes.LPARAM)

if _ENABLED:
    _user32 = ctypes.windll.user32
    _user32.DefWindowProcW.argtypes = [
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    _user32.DefWindowProcW.restype = ctypes.c_ssize_t
    _user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR,
                                   wintypes.UINT, ctypes.c_int,
                                   ctypes.c_int, wintypes.UINT]
    _user32.LoadImageW.restype = wintypes.HANDLE
    _user32.LoadIconW.restype = wintypes.HANDLE
    _user32.CreateWindowExW.argtypes = [
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
        wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, wintypes.HWND, wintypes.HANDLE,
        wintypes.HINSTANCE, wintypes.LPVOID]
    _user32.CreateWindowExW.restype = wintypes.HWND
    _user32.DestroyWindow.argtypes = [wintypes.HWND]
    _user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                     wintypes.WPARAM, wintypes.LPARAM]
    _user32.PostQuitMessage.argtypes = [ctypes.c_int]
    _user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG),
                                    wintypes.HWND, wintypes.UINT,
                                    wintypes.UINT]
    _user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
    _user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
    _user32.DispatchMessageW.restype = ctypes.c_ssize_t
    _user32.CreatePopupMenu.restype = wintypes.HANDLE
    _user32.AppendMenuW.argtypes = [wintypes.HANDLE, wintypes.UINT,
                                    wintypes.UINT, wintypes.LPCWSTR]
    _user32.TrackPopupMenu.argtypes = [wintypes.HANDLE, wintypes.UINT,
                                      ctypes.c_int, ctypes.c_int,
                                      ctypes.c_int, wintypes.HWND,
                                      wintypes.LPVOID]
    _user32.TrackPopupMenu.restype = wintypes.UINT
    _user32.DestroyMenu.argtypes = [wintypes.HANDLE]
    _user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
    _user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    ctypes.windll.kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
    ctypes.windll.shell32.Shell_NotifyIconW.argtypes = [
        wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
    ctypes.windll.shell32.Shell_NotifyIconW.restype = wintypes.BOOL


def is_supported():
    return bool(_ENABLED)


class TrayManager:
    """托盘图标封装：start()/stop() 幂等；失败安全降级。"""

    def __init__(self, root, on_show=None, on_exit=None, icon_path="",
                 tooltip="All-My-Maa"):
        self.root = root
        self.on_show = on_show
        self.on_exit = on_exit
        self.icon_path = icon_path or ""
        self.tooltip = str(tooltip or "All-My-Maa")[:127]
        self.started = False
        self.failed = False
        self.last_error = ""
        self._thread = None
        self._hwnd = None
        self._nid = None
        self._wndproc = None
        self._stop_event = threading.Event()
        self._ready = threading.Event()
        self._lock = threading.Lock()

    # -------------------------------------------------- 公共 API
    def start(self):
        if self.started:
            return True
        if not _ENABLED:
            self.failed = True
            self.last_error = "当前平台不支持系统托盘"
            return False
        try:
            self._start_native()
            self.started = True
            self.failed = False
            return True
        except Exception as exc:
            self.last_error = str(exc)
            self.failed = True
            self.started = False
            self._stop_event.set()
            try:
                self._stop_native()
            except Exception:
                pass
            self._cleanup_quiet()
            return False

    def stop(self):
        if not self.started and self._thread is None:
            return True
        try:
            self._stop_native()
        except Exception as exc:
            self.last_error = str(exc)
        finally:
            self.started = False
            self._thread = None
            self._hwnd = None
        return True

    def update_tooltip(self, text):
        self.tooltip = str(text or "All-My-Maa")[:127]
        if not self.started:
            return False
        try:
            self._modify_native()
            return True
        except Exception as exc:
            self.last_error = str(exc)
            return False

    def available(self):
        return _ENABLED

    # -------------------------------------------------- Tk 线程调度
    def _schedule(self, callback):
        if callback is None:
            return
        try:
            self.root.after(0, callback)
        except Exception:
            pass

    def _handle_menu_command(self, command):
        if command == MENU_SHOW:
            self._schedule(self.on_show)
        elif command == MENU_EXIT:
            self._schedule(self.on_exit)

    # -------------------------------------------------- Win32 实现
    def _load_icon(self):
        user32 = ctypes.windll.user32
        if self.icon_path and os.path.isfile(self.icon_path):
            icon = user32.LoadImageW(None, self.icon_path, IMAGE_ICON, 0, 0,
                                     LR_LOADFROMFILE | LR_DEFAULTSIZE)
            if icon:
                return icon
        return user32.LoadIconW(None, IDI_APPLICATION)

    def _start_native(self):
        self._stop_event.clear()
        self._ready.clear()
        self._thread = threading.Thread(target=self._thread_main,
                                        name="GameHubTray", daemon=True)
        self._thread.start()
        if not self._ready.wait(2.0):
            raise RuntimeError("托盘窗口初始化超时")
        if self.last_error:
            raise RuntimeError(self.last_error)

    def _thread_main(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        hinstance = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW()
        wc.style = 0
        wc.lpfnWndProc = ctypes.cast(self._make_wndproc(), ctypes.c_void_p)
        wc.cbClsExtra = 0
        wc.cbWndExtra = 0
        wc.hInstance = hinstance
        wc.hIcon = 0
        wc.hCursor = 0
        wc.hbrBackground = 0
        wc.lpszMenuName = None
        wc.lpszClassName = CLASS_NAME
        try:
            atom = user32.RegisterClassW(ctypes.byref(wc))
        except Exception:
            atom = 0
        hwnd = user32.CreateWindowExW(
            0, CLASS_NAME, "GameHubTray", 0, 0, 0, 0, 0,
            wintypes.HWND(HWND_MESSAGE), None, hinstance, None)
        if not hwnd:
            self.last_error = "创建托盘窗口失败"
            self._ready.set()
            return
        self._hwnd = hwnd
        try:
            nid = NOTIFYICONDATAW()
            nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
            nid.hWnd = hwnd
            nid.uID = TRAY_UID
            nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP | NIF_SHOWTIP
            nid.uCallbackMessage = WM_TRAYICON
            nid.hIcon = self._load_icon()
            nid.szTip = self.tooltip
            nid.uVersion = 4
            if not ctypes.windll.shell32.Shell_NotifyIconW(
                    NIM_ADD, ctypes.byref(nid)):
                self.last_error = "Shell_NotifyIcon 添加失败"
                user32.DestroyWindow(hwnd)
                self._hwnd = None
                self._ready.set()
                return
            self._nid = nid
            self._ready.set()
            msg = wintypes.MSG()
            while not self._stop_event.is_set():
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret <= 0:
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            try:
                if self._nid is not None:
                    ctypes.windll.shell32.Shell_NotifyIconW(
                        NIM_DELETE, ctypes.byref(self._nid))
            except Exception:
                pass
            try:
                if hwnd:
                    user32.DestroyWindow(hwnd)
            except Exception:
                pass
            self._nid = None
            self._hwnd = None

    def _make_wndproc(self):
        def _proc(hwnd, msg, wparam, lparam):
            if msg == WM_TRAYICON:
                event = int(lparam) & 0xFFFF
                if event in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                    self._schedule(self.on_show)
                elif event in (WM_RBUTTONUP, WM_CONTEXTMENU):
                    self._show_menu(hwnd)
                return 0
            if msg == WM_COMMAND:
                self._handle_menu_command(int(wparam) & 0xFFFF)
                return 0
            if msg == WM_CLOSE:
                ctypes.windll.user32.DestroyWindow(hwnd)
                return 0
            if msg == WM_DESTROY:
                ctypes.windll.user32.PostQuitMessage(0)
                return 0
            return ctypes.windll.user32.DefWindowProcW(
                hwnd, msg, wparam, lparam)

        self._wndproc = WNDPROC(_proc)
        return self._wndproc

    def _show_menu(self, hwnd):
        user32 = ctypes.windll.user32
        menu = user32.CreatePopupMenu()
        if not menu:
            return
        try:
            user32.AppendMenuW(menu, MF_STRING, MENU_SHOW, "打开主界面")
            user32.AppendMenuW(menu, MF_STRING, MENU_EXIT, "退出")
            point = POINT()
            user32.GetCursorPos(ctypes.byref(point))
            user32.SetForegroundWindow(hwnd)
            command = user32.TrackPopupMenu(
                menu, TPM_RIGHTBUTTON | TPM_RETURNCMD,
                point.x, point.y, 0, hwnd, None)
            user32.PostMessageW(hwnd, WM_NULL, 0, 0)
            if command:
                self._handle_menu_command(int(command))
        finally:
            user32.DestroyMenu(menu)

    def _modify_native(self):
        nid = self._nid
        if nid is None:
            return
        nid.uFlags = NIF_TIP | NIF_SHOWTIP
        nid.szTip = self.tooltip
        ctypes.windll.shell32.Shell_NotifyIconW(
            NIM_MODIFY, ctypes.byref(nid))

    def _stop_native(self):
        self._stop_event.set()
        hwnd = self._hwnd
        if hwnd:
            try:
                ctypes.windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
            except Exception:
                pass
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(2.0)
        self._cleanup_quiet()

    def _cleanup_quiet(self):
        try:
            if self._hwnd:
                ctypes.windll.user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
        except Exception:
            pass
        self._hwnd = None
        self._nid = None
