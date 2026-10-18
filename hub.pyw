# -*- coding: utf-8 -*-
"""游戏脚本中心 · GameHub Lite v0.4.0 —— 程序入口。

双击「启动游戏中心.bat」运行；也可以直接 python hub.pyw。
依赖：Python 3.10+、tkinter、Pillow（pip install pillow）。

默认以管理员身份启动：源码模式会用 pythonw.exe + ShellExecuteW(runas)
重启自身；取消 UAC 则回退普通权限继续启动。
调试/测试可加 --no-elevate 或设置 GAMEHUB_NO_ELEVATE=1。
"""
import ctypes
import os
import sys

# 保证源码运行 / PyInstaller 打包运行都能找到 gamehub 包
APP_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False)
                                          else __file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# 提权决策必须发生在 Pillow 检查/导入 UI 之前
try:
    from gamehub.elevation import (elevation_status, is_admin,
                                  not_admin_message, relaunch_as_admin,
                                  should_elevate)
except Exception:  # 极端情况下（安装不完整）不阻塞普通启动
    elevation_status = is_admin = not_admin_message = relaunch_as_admin = None
    should_elevate = None

if should_elevate is None:
    pass
elif "--elevation-check" in sys.argv[1:]:
    import json
    print(json.dumps(elevation_status(), ensure_ascii=False))
    raise SystemExit(0)
elif should_elevate(is_admin(), sys.argv[1:], os.environ,
                    bool(getattr(sys, "frozen", False))):
    _result = relaunch_as_admin(__file__, APP_DIR)
    if _result > 32:
        raise SystemExit(0)
    not_admin_message()

try:
    import PIL  # noqa: F401
except Exception:
    ctypes.windll.user32.MessageBoxW(
        0,
        "缺少 Pillow 依赖，界面无法绘制。\n\n"
        "请先打开命令行运行：\n"
        "    python -m pip install pillow\n\n"
        "或使用打包好的 GameHub.exe。",
        "游戏脚本中心", 0x10)
    raise SystemExit(1)

from gamehub.ui import run  # noqa: E402


if __name__ == "__main__":
    run()
