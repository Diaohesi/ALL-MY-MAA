# -*- coding: utf-8 -*-
"""v0.10 game_launch 策略/等待/回退自测（不启动任何游戏）。"""
import json
import os
import sys
import tempfile
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from gamehub import store  # noqa: E402

failures = []


def check(label, got, expected):
    ok = got == expected
    print(("OK   " if ok else "FAIL ") + f"{label}: {got!r}")
    if not ok:
        failures.append(f"{label}: got {got!r}, expect {expected!r}")


def make_file(path, size=200 * 1024):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(b"MZ" + b"0" * max(0, size - 2))


def app(key, root, game_exe="", script_exe=""):
    return {"key": key, "game": key, "game_exe": game_exe,
            "script_exe": script_exe, "game_procs": []}


def test_wuwa():
    print("=== 鸣潮：直启游戏本体 ===")
    tmp = tempfile.mkdtemp(prefix="gl_wuwa_")
    body = os.path.join(tmp, "Wuthering Waves Game",
                        "Wuthering Waves.exe")
    launcher = os.path.join(tmp, "launcher.exe")
    make_file(body)
    make_file(launcher)
    spec = store.build_game_launch(app("wuwa", tmp, game_exe=launcher))
    check("strategy", spec["strategy"], "exe")
    check("优先游戏本体", spec["exe"], os.path.normpath(body))
    check("args", spec["args"], ["-krqlv=hd"])
    check("cwd", spec["cwd"], os.path.dirname(os.path.normpath(body)))
    check("不提权", spec["elevated"], False)
    check("等待超时", spec["wait"]["timeout_s"], 120)
    check("等待窗口规则",
          spec["wait"]["any_of"][0]["class_re"], "^UnrealWindow$")
    check("回退启动器",
          spec["fallback"][0]["exe"], os.path.normpath(launcher))

    # devices.json 候选
    tmp2 = tempfile.mkdtemp(prefix="gl_wuwa_dev_")
    pc_exe = os.path.join(tmp2, "Game", "Wuthering Waves.exe")
    make_file(pc_exe)
    script = os.path.join(tmp2, "ok-ww", "working", "main.py")
    make_file(script, 10)
    configs = os.path.join(tmp2, "ok-ww", "configs")
    os.makedirs(configs, exist_ok=True)
    with open(os.path.join(configs, "devices.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"devices": [{"pc_full_path": pc_exe}]}, fh)
    spec2 = store.build_game_launch(app("wuwa", tmp2,
                                        script_exe=script))
    check("devices.json 解析", spec2["exe"], os.path.normpath(pc_exe))


def test_nte():
    print("\n=== 异环：HTGame 优先 ===")
    tmp = tempfile.mkdtemp(prefix="gl_nte_")
    launcher = os.path.join(tmp, "NTELauncher.exe")
    body = os.path.join(tmp, *store.NTE_GAME_RELATIVE)
    make_file(launcher)
    make_file(body)
    spec = store.build_game_launch(app("nte", tmp, game_exe=launcher))
    check("HTGame 优先", spec["exe"], os.path.normpath(body))
    check("timeout 180", spec["wait"]["timeout_s"], 180)
    check("回退启动器", spec["fallback"][0]["exe"],
          os.path.normpath(launcher))
    check("无 args", spec["args"], [])


def test_maaend():
    print("\n=== 终末地：默认启动器 ===")
    tmp = tempfile.mkdtemp(prefix="gl_end_")
    launcher = os.path.join(tmp, "Launcher.exe")
    endfield = os.path.join(tmp, "games", "Endfield Game", "Endfield.exe")
    make_file(launcher)
    make_file(endfield)
    spec = store.build_game_launch(app("maaend", tmp, game_exe=launcher))
    check("strategy launcher", spec["strategy"], "launcher")
    check("exe 启动器", spec["exe"], os.path.normpath(launcher))
    check("cwd 安装根", spec["cwd"], os.path.normpath(tmp))
    check("直启仅作回退", spec["fallback"][0]["exe"],
          os.path.normpath(endfield))
    check("等待 Endfield 窗口",
          spec["wait"]["any_of"][0]["title_re"], "Endfield")


def test_maa():
    print("\n=== 明日方舟：PC / 模拟器分支 ===")
    tmp = tempfile.mkdtemp(prefix="gl_maa_")
    arknights = os.path.join(tmp, "games", "Arknights Game",
                             "Arknights.exe")
    make_file(arknights)
    gui = {
        "Configurations": {
            "Default": {
                "Gui": {
                    "StartUpSettings": {
                        "PcClientPath": arknights,
                        "PcClientWaitSeconds": 90,
                    },
                    "ConnectSettings": {"Config": "PC"},
                }
            }
        }
    }
    with open(os.path.join(tmp, "gui.new.json"), "w",
              encoding="utf-8") as fh:
        json.dump(gui, fh, ensure_ascii=False)
    spec = store.build_game_launch(app("maa", tmp,
                                       script_exe=os.path.join(tmp, "MAA.exe")))
    check("PC 策略", spec["strategy"], "maa_pc")
    check("PcClientPath", spec["exe"], os.path.normpath(arknights))
    check("PC 等待", spec["wait"]["any_of"][0]["title_re"], "明日方舟")
    check("PC 等待秒数", spec["wait"]["timeout_s"], 90)

    emu = os.path.join(tmp, "MuMu", "MuMuPlayer.exe")
    adb = os.path.join(tmp, "adb.exe")
    make_file(emu)
    make_file(adb)
    gui2 = {
        "Gui": {
            "StartUpSettings": {
                "EmulatorPath": emu,
                "EmulatorWaitSeconds": 45,
                "AdbPath": adb,
                "AdbSerial": "127.0.0.1:16384",
            },
            "ConnectSettings": {"Config": "MuMuEmulator12"},
        }
    }
    with open(os.path.join(tmp, "gui.new.json"), "w",
              encoding="utf-8") as fh:
        json.dump(gui2, fh, ensure_ascii=False)
    spec2 = store.build_game_launch(app("maa", tmp,
                                        script_exe=os.path.join(tmp, "MAA.exe")))
    check("模拟器策略", spec2["strategy"], "maa_adb")
    check("模拟器 exe", spec2["exe"], os.path.normpath(emu))
    check("ADB serial", spec2["adb"]["serial"], "127.0.0.1:16384")
    check("等待 45s", spec2["wait"]["timeout_s"], 45)
    check("包名默认", spec2["adb"]["package"], "com.hypergryph.arknights")


class FakeProc:
    def __init__(self, pid=1234, exit_code=None):
        self.pid = pid
        self._exit = exit_code

    def poll(self):
        return self._exit


def test_wait():
    print("\n=== 等待器/超时/提前退出 ===")
    spec = {"strategy": "exe", "exe": "x", "wait": {
        "timeout_s": 5, "poll_ms": 100}}
    times = iter([0.0, 0.1, 0.2, 0.3])
    states = iter([False, True])
    ok, reason = store.wait_game_launched(
        {"key": "wuwa"}, spec,
        state_fn=lambda: next(states, True),
        sleep_fn=lambda seconds: None,
        clock_fn=lambda: next(times, 10.0))
    check("等待成功", ok, True)
    check("成功原因", reason, "")

    spec2 = {"strategy": "exe", "exe": "x",
             "wait": {"timeout_s": 0.2, "poll_ms": 50}}
    times2 = iter([0.0, 0.1, 0.2, 0.3])
    ok2, reason2 = store.wait_game_launched(
        {"key": "wuwa"}, spec2, state_fn=lambda: False,
        sleep_fn=lambda s: None, clock_fn=lambda: next(times2, 1.0))
    check("超时失败", ok2, False)
    check("超时提示", "超时" in reason2, True)
    ok3, reason3 = store.wait_game_launched(
        {"key": "wuwa"}, spec2, state_fn=lambda: False,
        sleep_fn=lambda s: None,
        clock_fn=lambda: next(iter([0.0, 0.1, 0.2, 0.3]), 1.0),
        process=FakeProc(exit_code=1))
    check("进程提前退出", ok3, False)
    check("退出原因", "提前退出" in reason3, True)


def test_launch_with_wait():
    print("\n=== 启动/等待/回退（mock spawn） ===")
    tmp = tempfile.mkdtemp(prefix="gl_launch_")
    body = os.path.join(tmp, "Wuthering Waves Game",
                        "Wuthering Waves.exe")
    launcher = os.path.join(tmp, "launcher.exe")
    make_file(body)
    make_file(launcher)
    spec = store.build_game_launch(app("wuwa", tmp, game_exe=launcher))
    calls = []

    def spawn(exe, args=None, cwd=""):
        calls.append((exe, list(args or []), cwd))
        return FakeProc(), ""

    result = store.launch_game_with_wait(
        app("wuwa", tmp, game_exe=launcher), spec, spawn_fn=spawn,
        state_fn=lambda: True, sleep_fn=lambda s: None,
        clock_fn=lambda: 0.0)
    check("启动成功", result["ok"], True)
    check("spawn 参数", calls[0][0], spec["exe"])
    check("spawn args", calls[0][1], ["-krqlv=hd"])
    check("spawn cwd", calls[0][2], spec["cwd"])

    calls.clear()
    times = iter([0.0, 0.1, 0.2, 0.3, 0.4, 0.5])
    spec2 = dict(spec)
    spec2["wait"] = {"timeout_s": 0.2, "poll_ms": 50}
    result2 = store.launch_game_with_wait(
        app("wuwa", tmp, game_exe=launcher), spec2, spawn_fn=spawn,
        state_fn=lambda: False, sleep_fn=lambda s: None,
        clock_fn=lambda: next(times, 10.0))
    check("超时返回失败", result2["ok"], False)
    check("执行回退", calls[-1][0], spec2["fallback"][0]["exe"])
    check("回退提示", bool(result2["fallback"].get("hint")), True)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    test_wuwa()
    test_nte()
    test_maaend()
    test_maa()
    test_wait()
    test_launch_with_wait()
    print("\nFAILURES:", failures if failures else "none")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
