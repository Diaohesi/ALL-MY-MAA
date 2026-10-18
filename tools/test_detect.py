# -*- coding: utf-8 -*-
"""游戏启动程序自动检测 · 命令行自测（不打开 GUI，可独立运行）。

用法：
    python tools/test_detect.py             # 依次检测四个内置游戏
    python tools/test_detect.py maa         # 只检测一个：maa/nte/wuwa/maaend
    python tools/test_detect.py 异环        # 也可以用游戏名称指定
    python tools/test_detect.py --all       # 不限定游戏，列出全部候选
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from gamehub import store  # noqa: E402

BUILTIN = [
    ("maa", "明日方舟"),
    ("nte", "异环"),
    ("wuwa", "鸣潮"),
    ("maaend", "明日方舟终末地"),
]


def _print_candidates(title, candidates, elapsed):
    print(f"== {title} ==")
    if not candidates:
        print("  未检测到候选（界面里会提示手动选择启动程序）")
    else:
        print(f"  共 {len(candidates)} 个候选，耗时 {elapsed * 1000:.0f} ms")
    for index, item in enumerate(candidates, 1):
        print(f"  {index}. [{item['source']} {item['score']}] {item['name']}")
        print(f"     {item['path']}")
    print()


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = [arg.strip() for arg in argv[1:] if arg.strip()]
    targets = []
    if not args:
        targets = [({"key": key, "game": game}, f"{game}（{key}）")
                   for key, game in BUILTIN]
    elif args[0] in ("--all", "-a"):
        targets = [(None, "全部游戏（不限关键词）")]
    else:
        for arg in args:
            low = arg.lower()
            matched = None
            for key, game in BUILTIN:
                if low == key or arg == game:
                    matched = ({"key": key, "game": game}, f"{game}（{key}）")
                    break
            targets.append(matched or ({"game": arg}, arg))

    for app, title in targets:
        started = time.monotonic()
        candidates = store.find_game_candidates(app)
        elapsed = time.monotonic() - started
        _print_candidates(title, candidates, elapsed)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
