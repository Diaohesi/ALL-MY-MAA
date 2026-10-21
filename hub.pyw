# -*- coding: utf-8 -*-
"""游戏脚本中心入口。默认提权，--no-elevate 可用于调试。"""
import ctypes
import os
import sys

APP_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False)
                                          else __file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# Logging precedes elevation and all UI/Pillow imports. Never writes stdout.
try:
    from gamehub.runtime_log import (setup_logging, log_event, get_logger,
                                     shutdown_logging)
    setup_logging(APP_DIR)
except Exception:
    def log_event(*args, **kwargs):
        pass
    def shutdown_logging():
        pass
    get_logger = None


def _log_exception(event):
    if get_logger is not None:
        get_logger("entrypoint").error(event, exc_info=True)


def _main():
    log_event("startup", frozen=bool(getattr(sys, "frozen", False)),
              pid=os.getpid(), elevation_check="--elevation-check" in sys.argv[1:])
    try:
        from gamehub.elevation import (elevation_status, is_admin,
                                      not_admin_message, relaunch_as_admin,
                                      should_elevate)
    except Exception:
        _log_exception("elevation_import_failed")
        elevation_status = is_admin = not_admin_message = relaunch_as_admin = None
        should_elevate = None

    if should_elevate is None:
        pass
    elif "--elevation-check" in sys.argv[1:]:
        import json
        print(json.dumps(elevation_status(), ensure_ascii=False))
        return
    elif should_elevate(is_admin(), sys.argv[1:], os.environ,
                        bool(getattr(sys, "frozen", False))):
        log_event("uac_requested")
        _result = relaunch_as_admin(__file__, APP_DIR)
        log_event("uac_result", code=_result, success=_result > 32)
        if _result > 32:
            return
        not_admin_message()
    else:
        log_event("uac_not_required", admin=is_admin())

    try:
        import PIL  # noqa: F401
    except Exception:
        _log_exception("pillow_import_failed")
        ctypes.windll.user32.MessageBoxW(
            0,
            "缺少 Pillow 依赖，界面无法绘制。\n\n"
            "请先打开命令行运行：\n"
            "    python -m pip install pillow\n\n"
            "或使用打包好的 GameHub.exe。",
            "游戏脚本中心", 0x10)
        raise SystemExit(1)
    try:
        from gamehub.ui import run
    except Exception:
        _log_exception("ui_import_failed")
        raise
    run()


if __name__ == "__main__":
    try:
        _main()
    except SystemExit as exc:
        log_event("exit", code=exc.code)
        raise
    except BaseException:
        _log_exception("entrypoint_exception")
        # Do not re-raise into the restored default hook (unredacted stderr).
        raise SystemExit(1)
    else:
        log_event("normal_exit")
    finally:
        shutdown_logging()
