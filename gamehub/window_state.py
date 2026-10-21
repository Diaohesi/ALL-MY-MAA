"""Taskbar minimization for Tk windows with a custom (override-redirect) frame.

Call on Tk's UI thread. ``restore_from_taskbar`` repairs a *mapped* window;
its name does not mean "show now". It never deiconifies a minimized window.
A UI may bind it with ``root.bind('<Map>', lambda e:
restore_from_taskbar(root, e), add='+')``. The Tk fallback also installs an
additive, one-shot binding itself. No helper withdraws the window, changes its
geometry, or steals focus. Failures return False and expose a diagnostic in
``root._gamehub_window_state_error``.
"""
import ctypes
import sys
from ctypes import wintypes

GWL_EXSTYLE = -20
WS_EX_APPWINDOW = 0x00040000
WS_EX_TOOLWINDOW = 0x00000080
GA_ROOT = 2
SW_MINIMIZE = 6
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020


def _native():
    """Load pointer-width-correct Win32 functions (also an isolated test seam)."""
    dll = ctypes.WinDLL('user32', use_last_error=True)
    pointer_sized = ctypes.sizeof(ctypes.c_void_p) == 8
    get_long = getattr(dll, 'GetWindowLongPtrW' if pointer_sized
                       else 'GetWindowLongW')
    set_long = getattr(dll, 'SetWindowLongPtrW' if pointer_sized
                       else 'SetWindowLongW')
    long_ptr = ctypes.c_ssize_t if pointer_sized else wintypes.LONG
    get_long.argtypes = [wintypes.HWND, ctypes.c_int]
    get_long.restype = long_ptr
    set_long.argtypes = [wintypes.HWND, ctypes.c_int, long_ptr]
    set_long.restype = long_ptr
    dll.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    dll.GetAncestor.restype = wintypes.HWND
    dll.IsWindow.argtypes = [wintypes.HWND]
    dll.IsWindow.restype = wintypes.BOOL
    dll.IsIconic.argtypes = [wintypes.HWND]
    dll.IsIconic.restype = wintypes.BOOL
    dll.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    dll.ShowWindow.restype = wintypes.BOOL
    dll.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                wintypes.UINT]
    dll.SetWindowPos.restype = wintypes.BOOL
    return dll, get_long, set_long


def _state(root):
    state = getattr(root, '_gamehub_window_state', None)
    if state is None:
        state = dict(busy=False, pending=False, binding=None, override=True)
        root._gamehub_window_state = state
    return state


def _error(root, exc):
    root._gamehub_window_state_error = str(exc)
    return False


def _handle(root, dll):
    # winfo_id is Tk's client HWND, not necessarily the outer WM wrapper.
    client = int(root.winfo_id())
    hwnd = dll.GetAncestor(client, GA_ROOT)
    if not hwnd or not dll.IsWindow(hwnd):
        raise OSError('Tk has no valid native top-level window')
    return hwnd


def _style(root, api):
    dll, get_long, set_long = api
    hwnd = _handle(root, dll)
    ctypes.set_last_error(0)
    old = get_long(hwnd, GWL_EXSTYLE)
    if not old and ctypes.get_last_error():
        raise ctypes.WinError(ctypes.get_last_error())
    new = (old | WS_EX_APPWINDOW) & ~WS_EX_TOOLWINDOW
    if new != old:
        ctypes.set_last_error(0)
        previous = set_long(hwnd, GWL_EXSTYLE, new)
        if not previous and ctypes.get_last_error():
            raise ctypes.WinError(ctypes.get_last_error())
        flags = (SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER |
                 SWP_NOACTIVATE | SWP_FRAMECHANGED)
        if not dll.SetWindowPos(hwnd, None, 0, 0, 0, 0, flags):
            raise OSError('SetWindowPos failed while updating taskbar style')
        ctypes.set_last_error(0)
        actual = get_long(hwnd, GWL_EXSTYLE)
        if ((not actual and ctypes.get_last_error()) or
                not actual & WS_EX_APPWINDOW or actual & WS_EX_TOOLWINDOW):
            raise OSError('Taskbar style update did not take effect')
    return hwnd


def apply_taskbar_style(root):
    """Set APPWINDOW and clear TOOLWINDOW without changing size/visibility.

    Returns False on non-Windows (native taskbar styling is unsupported there).
    Call after the initial mapping, when Tk has created its WM wrapper.
    """
    if sys.platform != 'win32':
        return _error(root, 'Native taskbar style is Windows-only')
    try:
        _style(root, _native())
        return True
    except Exception as exc:
        return _error(root, exc)


def _unbind(root, state):
    if state['binding'] is not None:
        root.unbind('<Map>', state['binding'])
        state['binding'] = None


def minimize_to_taskbar(root):
    """Minimize, retaining a taskbar entry; never immediately restore/show.

    Prefer Win32 SW_MINIMIZE with override-redirect left intact. If unavailable
    or unsuccessful, temporarily allow the Tk WM to iconify. The fallback's
    Map callback restores the original override flag only after a real restore.
    A native failure followed by successful fallback returns True, retaining
    the native diagnostic; failure of both paths returns False.
    """
    state = _state(root)
    if state['busy']:
        return _error(root, 'Window-state transition already in progress')
    state['busy'] = True
    root._gamehub_window_state_error = ''
    try:
        if sys.platform == 'win32':
            try:
                api = _native()
                hwnd = _style(root, api)
                dll = api[0]
                if not dll.IsIconic(hwnd):
                    # ShowWindow returns *previous visibility*, not success.
                    dll.ShowWindow(hwnd, SW_MINIMIZE)
                if not dll.IsIconic(hwnd):
                    raise OSError('SW_MINIMIZE did not iconify the window')
                return True
            except Exception as exc:
                _error(root, exc)
        if state['pending'] and root.state() == 'iconic':
            return True
        if not state['pending']:
            state['override'] = bool(root.overrideredirect())
        if state['binding'] is None:
            state['binding'] = root.bind(
                '<Map>', lambda event: restore_from_taskbar(root, event), add='+')
            if not state['binding']:
                raise RuntimeError('Could not install Map restoration binding')
        state['pending'] = True
        root.overrideredirect(False)
        root.iconify()
        if root.state() != 'iconic':
            raise RuntimeError('Tk iconify did not minimize the window')
        return True
    except Exception as exc:
        _error(root, exc)
        # Roll back failed fallback only if it did not actually iconify.
        try:
            if state['pending'] and root.state() != 'iconic':
                root.overrideredirect(state['override'])
                state['pending'] = False
                _unbind(root, state)
        except Exception as rollback_exc:
            _error(root, '{}; rollback failed: {}'.format(exc, rollback_exc))
        return False
    finally:
        state['busy'] = False


def restore_from_taskbar(root, event=None):
    """Repair borderless/taskbar style on Map; do not unminimize a window.

    Child Map events, reentrant events, and events while iconic are no-ops.
    On Windows IsIconic is authoritative because Tk's WM state can lag native
    ShowWindow calls. Safe to call repeatedly from an existing UI Map handler.
    """
    state = _state(root)
    if event is not None and getattr(event, 'widget', None) is not root:
        return True
    if state['busy']:
        return True
    state['busy'] = True
    try:
        if sys.platform == 'win32':
            try:
                dll = _native()[0]
                if dll.IsIconic(_handle(root, dll)):
                    return True
            except Exception as exc:
                # Native unavailability must not prevent Tk fallback repair.
                _error(root, exc)
        if root.state() in ('iconic', 'withdrawn') or not root.winfo_ismapped():
            return True
        if state['pending']:
            root.overrideredirect(state['override'])
            _unbind(root, state)
            state['pending'] = False
        if sys.platform == 'win32':
            return apply_taskbar_style(root)
        return True
    except Exception as exc:
        return _error(root, exc)
    finally:
        state['busy'] = False
