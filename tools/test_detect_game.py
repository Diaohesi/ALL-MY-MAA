# -*- coding: utf-8 -*-
"""只读检测四款游戏的运行状态与检测规则（不启动游戏、不打开 GUI）。

用法：
    python tools/test_detect_game.py
    python tools/test_detect_game.py --json     # 机器可读输出

说明：本脚本读取真实 config.json / 脚本 interface.json 与当前桌面窗口、进程快照，
不会启动/关闭任何游戏，也不会写入任何文件。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from gamehub import detector, store  # noqa: E402

BUILTIN = [
    ("maa", "明日方舟"),
    ("nte", "异环"),
    ("wuwa", "鸣潮"),
    ("maaend", "明日方舟终末地"),
]


def _fields_text(rules):
    fields = detector.rules_to_fields(rules)
    lines = []
    if fields["win_class"]:
        lines.append(f"窗口类  : {fields['win_class']}")
    if fields["win_title"]:
        lines.append(f"窗口标题: {fields['win_title']}")
    if fields["detect_procs"]:
        lines.append(f"进程名  : {fields['detect_procs']}")
    if fields["adb_pkg"]:
        lines.append(f"ADB 包名: {fields['adb_pkg']}")
    checks = rules.get("proc_class_check") or []
    if checks:
        for check in checks:
            lines.append(f"窗口+进程校验: {check.get('name')} @ "
                         f"{check.get('win_class_re')}")
    return lines


def collect():
    apps, _clash, _root = store.load_state()
    by_key = {app["key"]: app for app in apps}
    windows = detector.snapshot_windows(force=True)
    processes = store.snapshot_processes()
    rows = []
    for key, label in BUILTIN:
        app = by_key.get(key) or {"key": key, "game": label}
        rules = detector.read_game_rules(app)
        state = detector.detect_game_state(app, windows=windows,
                                          processes=processes)
        rows.append({
            "key": key,
            "label": label,
            "running": bool(state["running"]),
            "reason": state["reason"],
            "state": state["label"],
            "hwnd": state["hwnd"],
            "source": rules.get("source", "none"),
            "rules": detector.rules_to_fields(rules),
            "fields": _fields_text(rules),
            "launcher_on": state.get("reason") == "launcher",
            "cloud_on": state.get("reason") == "cloud",
        })
    return rows, windows, processes


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    rows, windows, processes = collect()
    if "--json" in argv[1:]:
        print(json.dumps({"windows": len(windows), "processes": len(processes),
                          "adb_enabled": detector.ADB_ENABLED, "apps": rows},
                         ensure_ascii=False, indent=2))
        return 0
    print(f"窗口快照: {len(windows)} 个顶层窗口；进程快照: {len(processes)} 个进程")
    print(f"ADB 检测: {'开启' if detector.ADB_ENABLED else '关闭（默认）'}\n")
    for row in rows:
        hwnd = f"，hwnd={row['hwnd']}" if row["hwnd"] else ""
        print(f"== {row['label']}（{row['key']}）==")
        print(f"  规则来源: {row['source']}；当前状态: {row['state']}{hwnd}")
        for line in row["fields"]:
            print(f"  {line}")
        if row["launcher_on"]:
            print("  附注    : 检测到启动器窗口/进程（不计入游戏运行）")
        if row["cloud_on"]:
            print("  附注    : 检测到云游戏窗口")
        print()
    running = [row["label"] for row in rows if row["running"]]
    print("本机正在运行的游戏: " + ("、".join(running) if running else "无"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
