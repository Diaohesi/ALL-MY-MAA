# -*- coding: utf-8 -*-
"""v0.10 异环启动游戏路径解析自测（不启动任何游戏）。"""
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


def make_file(path, size=150 * 1024):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(b"MZ" + b"0" * max(0, size - 2))


def make_nte_app(root):
    launcher = os.path.join(root, "NTELauncher.exe")
    make_file(launcher)
    return {"key": "nte", "game": "异环", "game_exe": launcher,
            "script_exe": os.path.join(root, "script", "MaaNTE.exe"),
            "game_procs": ["ntelauncher.exe"]}


def test_resolve():
    print("=== resolve_game_exe ===")
    tmp = tempfile.mkdtemp(prefix="gh_nte_")
    app = make_nte_app(tmp)
    body = os.path.join(tmp, *store.NTE_GAME_RELATIVE)
    make_file(body)
    resolved = store.resolve_game_exe(app)
    check("已知相对路径解析", resolved, os.path.normpath(body))
    check("写回 game_exe", app["game_exe"], os.path.normpath(body))
    check("game_procs 更新", [name.lower() for name in app["game_procs"]],
          ["htgame.exe"])

    # 已是 HTGame.exe -> 原样
    app2 = {"key": "nte", "game_exe": body}
    check("已是 HTGame 直接返回", store.resolve_game_exe(app2), body)

    # 深度限制内 glob
    tmp3 = tempfile.mkdtemp(prefix="gh_nte_glob_")
    app3 = make_nte_app(tmp3)
    globbed = os.path.join(tmp3, "Game", "Bin", "HTGame.exe")
    make_file(globbed)
    check("深度 glob 找到", store.resolve_game_exe(app3),
          os.path.normpath(globbed))

    # 找不到：保留原值
    tmp4 = tempfile.mkdtemp(prefix="gh_nte_none_")
    app4 = make_nte_app(tmp4)
    old = app4["game_exe"]
    check("找不到保留原值", store.resolve_game_exe(app4), old)
    check("app 未被改写", app4["game_exe"], old)

    # 其它游戏不受影响
    other = {"key": "wuwa", "game_exe": os.path.join(tmp4, "launcher.exe")}
    check("其它游戏原样返回", store.resolve_game_exe(other),
          other["game_exe"])


def test_candidate_score():
    print("\n=== 候选排序/评分 ===")
    tmp = tempfile.mkdtemp(prefix="gh_nte_score_")
    launcher = os.path.join(tmp, "NTELauncher.exe")
    body = os.path.join(tmp, "Client", "WindowsNoEditor", "HT", "Binaries",
                        "Win64", "HTGame.exe")
    make_file(launcher)
    make_file(body)
    keywords, hints = store.GAME_KEYWORDS["nte"], store.GAME_EXE_HINTS["nte"]
    check("HTGame 提示置顶", hints[0], "htgame.exe")
    hit_body = store._score_exe_path(body, 0, keywords, hints)
    hit_launcher = store._score_exe_path(launcher, 0, keywords, hints)
    check("HTGame 有评分", bool(hit_body), True)
    check("HTGame 分数高于启动器",
          hit_body["score"] > hit_launcher["score"], True)

    app = {"key": "nte", "game": "异环"}
    with mock.patch.object(store, "_iter_registry_entries",
                           return_value=[]), \
            mock.patch.object(store, "_fs_scan_roots",
                              return_value=[(tmp, "异环")]):
        candidates = store.find_game_candidates(app)
    check("候选非空", len(candidates) > 0, True)
    check("候选首位是 HTGame",
          os.path.basename(candidates[0]["path"]), "HTGame.exe")


def test_load_migration():
    print("\n=== load 自动纠正并保存 ===")
    tmp = tempfile.mkdtemp(prefix="gh_nte_cfg_")
    cfg = os.path.join(tmp, "config.json")
    body = os.path.join(tmp, *store.NTE_GAME_RELATIVE)
    make_file(body)
    launcher = os.path.join(tmp, "NTELauncher.exe")
    make_file(launcher)
    data = {"version": 4, "root": tmp,
            "apps": {"nte": {"game_exe": launcher, "daily": {}}}}
    with open(cfg, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
    with mock.patch.object(store, "CONFIG", cfg):
        apps, _clash, _root, _meta = store.load_state_full()
    nte = next(app for app in apps if app["key"] == "nte")
    check("load 后为 HTGame", os.path.basename(nte["game_exe"]), "HTGame.exe")
    check("load 后绝对路径", os.path.normpath(nte["game_exe"]),
          os.path.normpath(body))
    raw = json.load(open(cfg, encoding="utf-8"))
    saved = raw["apps"]["nte"]["game_exe"]
    check("已保存到 config", os.path.basename(saved), "HTGame.exe")

    # 找不到 HTGame 时不乱改
    tmp2 = tempfile.mkdtemp(prefix="gh_nte_cfg2_")
    cfg2 = os.path.join(tmp2, "config.json")
    launcher2 = os.path.join(tmp2, "NTELauncher.exe")
    make_file(launcher2)
    with open(cfg2, "w", encoding="utf-8") as fh:
        json.dump({"version": 4, "root": tmp2,
                   "apps": {"nte": {"game_exe": launcher2, "daily": {}}}},
                  fh, ensure_ascii=False)
    with mock.patch.object(store, "CONFIG", cfg2):
        apps2, _c, _r, _m = store.load_state_full()
    nte2 = next(app for app in apps2 if app["key"] == "nte")
    check("找不到时保留启动器", os.path.basename(nte2["game_exe"]),
          "NTELauncher.exe")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    test_resolve()
    test_candidate_score()
    test_load_migration()
    print("\nFAILURES:", failures if failures else "none")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
