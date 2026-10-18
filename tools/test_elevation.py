# -*- coding: utf-8 -*-
"""v0.10.3：默认管理员启动的提权决策/打包 manifest 自测（不弹 UAC/GUI）。"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from gamehub import elevation  # noqa: E402

failures = []


def check(label, got, expected):
    ok = got == expected
    print(("OK   " if ok else "FAIL ") + f"{label}: {got!r}")
    if not ok:
        failures.append(f"{label}: got {got!r}, expect {expected!r}")


def test_should_elevate():
    print("=== should_elevate ===")
    check("普通权限默认提权", elevation.should_elevate(False, [], {}, False),
          True)
    check("已是管理员不提权", elevation.should_elevate(True, [], {}, False),
          False)
    check("--no-elevate 跳过",
          elevation.should_elevate(False, ["--no-elevate"], {}, False), False)
    check("环境变量跳过",
          elevation.should_elevate(False, [],
                                   {"GAMEHUB_NO_ELEVATE": "1"}, False), False)
    check("环境变量 true 跳过",
          elevation.should_elevate(False, [],
                                   {"GAMEHUB_NO_ELEVATE": "true"}, False),
          False)
    check("子进程标记跳过",
          elevation.should_elevate(False, ["--elevated"], {}, False), False)
    check("frozen 由 manifest 负责",
          elevation.should_elevate(False, [], {}, True), False)
    check("其它参数仍提权",
          elevation.should_elevate(False, ["--some-arg"], {}, False), True)


def test_relaunch_spec():
    print("\n=== 自提权重启命令 ===")
    hub = os.path.join(ROOT, "hub.pyw")
    spec = elevation.build_relaunch(hub, ROOT, pythonw=sys.executable)
    check("verb runas", spec["verb"], "runas")
    check("优先 pythonw", os.path.basename(spec["file"]).lower(),
          "pythonw.exe")
    check("参数含 hub 绝对路径",
          '"' + os.path.abspath(hub) + '"' in spec["params"], True)
    check("参数含 --elevated", "--elevated" in spec["params"], True)
    check("cwd", spec["cwd"], os.path.abspath(ROOT))
    check("show 正常窗口", spec["show"], 1)

    # 已是 pythonw 时原样使用
    pw = r"C:\Python313\pythonw.exe"
    check("pythonw 原样", elevation.pythonw_path(pw), pw)


def test_entry_check():
    print("\n=== hub.pyw --elevation-check 短进程 ===")
    env = dict(os.environ)
    env.pop("GAMEHUB_NO_ELEVATE", None)
    proc = subprocess.run(
        [sys.executable, os.path.join(ROOT, "hub.pyw"),
         "--elevation-check"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
    check("check 退出码", proc.returncode, 0)
    try:
        data = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        data = {}
    check("check 输出 admin", isinstance(data.get("admin"), bool), True)
    check("check 输出 would_elevate", data.get("would_elevate"), True)
    check("check 不启动 GUI", "Traceback" not in proc.stderr, True)

    env["GAMEHUB_NO_ELEVATE"] = "1"
    proc2 = subprocess.run(
        [sys.executable, os.path.join(ROOT, "hub.pyw"),
         "--elevation-check"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
    data2 = json.loads(proc2.stdout.strip().splitlines()[-1])
    check("环境变量 check 跳过", data2.get("would_elevate"), False)

    proc3 = subprocess.run(
        [sys.executable, os.path.join(ROOT, "hub.pyw"),
         "--elevation-check", "--no-elevate"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
    data3 = json.loads(proc3.stdout.strip().splitlines()[-1])
    check("--no-elevate check 跳过", data3.get("would_elevate"), False)


def test_manifest_flags():
    print("\n=== 打包 --uac-admin ===")
    bat = os.path.join(ROOT, "tools", "build_exe.bat")
    yml = os.path.join(ROOT, ".github", "workflows", "build-exe.yml")
    bat_text = open(bat, encoding="utf-8", errors="replace").read()
    yml_text = open(yml, encoding="utf-8", errors="replace").read()
    check("build_exe.bat --uac-admin", "--uac-admin" in bat_text, True)
    check("workflow --uac-admin", "--uac-admin" in yml_text, True)
    check("bat 保留 onefile/windowed",
          "--onefile" in bat_text and "--windowed" in bat_text, True)
    check("workflow 保留 onefile/windowed",
          "--onefile" in yml_text and "--windowed" in yml_text, True)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    test_should_elevate()
    test_relaunch_spec()
    test_entry_check()
    test_manifest_flags()
    print("\nFAILURES:", failures if failures else "none")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
