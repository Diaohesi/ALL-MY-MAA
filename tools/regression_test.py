# -*- coding: utf-8 -*-
"""GameHub 回归测试（标准库 unittest，无需第三方测试框架）。

运行方式（在仓库任意位置均可）：
    python tools/regression_test.py          # 退出码 0 = 全部通过
    python tools/regression_test.py -v       # 详细输出
    python tools/regression_test.py VersionTests   # 只跑某个测试类

约定：
* 本脚本只 import gamehub 包并做纯内存操作，不启动 tkinter / GUI mainloop。
* 所有涉及配置读写的用例都用 mock.patch 把 store.CONFIG / store.SEARCH_ROOT
  指向临时目录，绝不会碰仓库里真实的 config.json。
* 不依赖网络：http_get / check_latest / GitHub release 等联网函数均用 mock
  模拟，测试不会发起真实网络请求。
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

# 保证从任意 CWD 运行都能 import gamehub
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from gamehub import daily, detector, elevation, render, store, theme, ui  # noqa: E402

ASSETS = os.path.join(REPO_ROOT, "assets")


# ---------------------------------------------------------------- 测试基类
class TempDirTest(unittest.TestCase):
    """每个用例一个独立临时目录，自动清理。"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="gamehub_qa_")
        self.tmp = self._tmpdir.name
        self.addCleanup(self._tmpdir.cleanup)

    def touch(self, *parts, content=b"stub"):
        path = os.path.join(self.tmp, *parts)
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(content)
        return path

    def dump_json(self, path, data, encoding="utf-8"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding=encoding) as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        return path


# ---------------------------------------------------------------- 版本号
class VersionTests(unittest.TestCase):
    def test_version_key(self):
        self.assertEqual(store.version_key("v6.19.0"), (6, 19, 0))
        self.assertEqual(store.version_key("MaaNTE v2.33.0"), (2, 33, 0))
        self.assertEqual(store.version_key("1.2.3.4.5"), (1, 2, 3, 4))
        self.assertEqual(store.version_key("v1.10"), (1, 10))  # 数字比较而非字典序
        # QA-04 已修复：-rc/+build 等后缀不参与版本比较
        self.assertEqual(store.version_key("v1.0.0-rc1"), (1, 0, 0))
        self.assertEqual(store.version_key("v2.0.0+build7"), (2, 0, 0))
        self.assertEqual(store.version_key(""), ())
        self.assertEqual(store.version_key(None), ())
        self.assertEqual(store.version_key("无版本号"), ())

    def test_is_newer(self):
        cases = [
            ("v6.19.1", "v6.19.0", True),
            ("v6.20.0", "v6.19.9", True),
            ("v6.19.0", "v6.19.0", False),
            ("v6.19.0", "v6.19.1", False),
            ("", "v1.0", False),           # 拿不到 latest 不提示更新
            ("v1.0", "", False),           # 拿不到 current 不提示更新
        ]
        for latest, current, expected in cases:
            with self.subTest(latest=latest, current=current):
                self.assertIs(store.is_newer(latest, current), expected)

    def test_is_newer_prerelease_and_zero_padding(self):
        # QA-04 已修复：预发布后缀不参与比较；数字段数不同按零补齐
        self.assertIs(store.is_newer("v1.0.0-rc1", "v1.0.0"), False)
        self.assertIs(store.is_newer("v1.0.0", "v1.0.0-rc1"), False)  # 数字段相同
        self.assertIs(store.is_newer("v6.19", "v6.19.0"), False)      # 零补齐后相等
        self.assertIs(store.is_newer("v6.19.1", "v6.19"), True)
        self.assertIs(store.is_newer("v1.10", "v1.9"), True)


# ---------------------------------------------------------------- 路径 / 进程名
class PathHelperTests(TempDirTest):
    def test_portable_inside_root_uses_forward_slash(self):
        exe = self.touch("root", "MaaNTE", "MaaNTE.exe")
        root = os.path.join(self.tmp, "root")
        self.assertEqual(store._portable(exe, root), "MaaNTE/MaaNTE.exe")

    def test_portable_outside_root_keeps_absolute(self):
        other = self.touch("outside", "a.exe")
        root = os.path.join(self.tmp, "root")
        os.makedirs(root, exist_ok=True)
        self.assertEqual(store._portable(other, root), other)

    def test_portable_and_absolute_roundtrip(self):
        root = os.path.join(self.tmp, "root")
        exe = self.touch("root", "deep", "dir", "x.exe")
        portable = store._portable(exe, root)
        self.assertFalse(os.path.isabs(portable))
        self.assertEqual(os.path.normpath(store._absolute(portable, root)),
                         os.path.normpath(exe))

    def test_absolute_empty_and_missing(self):
        root = os.path.join(self.tmp, "root")
        os.makedirs(root, exist_ok=True)
        self.assertIsNone(store._absolute("", root))
        self.assertIsNone(store._absolute(None, root))
        self.assertIsNone(store._absolute("nope/missing.exe", root))
        self.assertIsNone(store._absolute(os.path.join(root, "missing.exe"), root))

    def test_absolute_absolute_path(self):
        root = os.path.join(self.tmp, "root")
        outside = self.touch("abs", "tool.exe")
        os.makedirs(root, exist_ok=True)
        self.assertEqual(store._absolute(outside, root), outside)


class CleanProcsTests(unittest.TestCase):
    def test_string_input(self):
        self.assertEqual(
            store._clean_procs("maa.exe, MaaEnd.exe;ok-ww.exe"),
            ["MAA.EXE", "MAAEND.EXE", "OK-WW.EXE"])

    def test_chinese_separators_and_whitespace(self):
        self.assertEqual(
            store._clean_procs("maa.exe，MaaEnd.exe；ok-ww.exe  other.exe"),
            ["MAA.EXE", "MAAEND.EXE", "OK-WW.EXE", "OTHER.EXE"])

    def test_list_and_tuple_input(self):
        self.assertEqual(store._clean_procs([" maa.exe ", "", "MaaEnd.exe"]),
                         ["MAA.EXE", "MAAEND.EXE"])
        self.assertEqual(store._clean_procs(("ok-ww.exe",)), ["OK-WW.EXE"])

    def test_empty_and_fallback(self):
        self.assertEqual(store._clean_procs(None), [])
        self.assertEqual(store._clean_procs([], ""), [])
        self.assertEqual(store._clean_procs(None, r"D:\Games\MaaNTE.exe"),
                         ["MAANTE.EXE"])
        self.assertEqual(store._clean_procs("  ", r"D:\Games\MaaNTE.exe"),
                         ["MAANTE.EXE"])

    def test_clean_procs_skips_non_str_items(self):
        # QA-05 已修复：None/数字等非 str 项被跳过，不再变成 "NONE"
        self.assertEqual(store._clean_procs([None]), [])
        self.assertEqual(store._clean_procs([None, 3, ["x"], " ok-ww.exe "]),
                         ["OK-WW.EXE"])
        # 全部被过滤时仍按 fallback_exe 兜底
        self.assertEqual(store._clean_procs([None], r"D:\Games\MaaNTE.exe"),
                         ["MAANTE.EXE"])


class ProcNameTests(unittest.TestCase):
    def test_proc_names_for_exe(self):
        self.assertEqual(store.proc_names_for_exe(r"D:\Games\MaaNTE.exe"),
                         ["MAANTE.EXE"])
        self.assertEqual(store.proc_names_for_exe(""), [])
        self.assertEqual(store.proc_names_for_exe(None), [])


# ---------------------------------------------------------------- 配置读写
class ConfigStateTests(TempDirTest):
    def setUp(self):
        super().setUp()
        self.search_root = os.path.join(self.tmp, "search")
        os.makedirs(self.search_root, exist_ok=True)
        self.user_root = os.path.join(self.tmp, "userroot")
        os.makedirs(self.user_root, exist_ok=True)
        self.cfg = os.path.join(self.tmp, "config.json")
        self.script_exe = self.touch("userroot", "MyScript", "myscript.exe")
        self.game_exe = self.touch("userroot", "MyGame", "mygame.exe")
        self.icon = self.touch("userroot", "MyScript", "icon.png", content=b"png")
        self.clash = self.touch("tools", "clash-verge.exe")

    def _ctx(self):
        return mock.patch.object(store, "CONFIG", self.cfg), \
            mock.patch.object(store, "SEARCH_ROOT", self.search_root)

    def _custom_app(self):
        return dict(
            key="qa_custom", game="测试游戏", script="测试脚本", builtin=False,
            script_exe=self.script_exe, script_procs=["myscript.exe"],
            game_exe=self.game_exe, game_procs=["mygame.exe"],
            accent="#ff8fc7", fallback_version="v9.9.9",
            site="https://example.com", github="https://github.com/x/y",
            release="https://github.com/x/y/releases/latest",
            download="https://example.com/download",
            icon_path=self.icon)

    def test_custom_app_roundtrip(self):
        app = self._custom_app()
        cfg_patch, root_patch = self._ctx()
        with cfg_patch, root_patch:
            ok = store.save_state([app], clash=self.clash, root=self.user_root)
            self.assertTrue(ok, "save_state 成功时现在应返回 True")
            self.assertTrue(os.path.isfile(self.cfg), "save_state 未写出配置文件")

            raw = json.load(open(self.cfg, "r", encoding="utf-8"))
            self.assertEqual(raw.get("version"), 4, "v0.6 起 config 版本为 4")
            self.assertEqual(len(raw.get("custom_apps") or []), 1)
            saved = raw["custom_apps"][0]
            self.assertFalse(os.path.isabs(saved["script_exe"]),
                             "root 内的 exe 应写成相对路径")
            self.assertEqual(saved["script_exe"].replace("\\", "/"),
                             "MyScript/myscript.exe")

            apps, clash, root = store.load_state()

        self.assertEqual(os.path.normpath(root), os.path.normpath(self.user_root))
        self.assertEqual(os.path.normpath(clash), os.path.normpath(self.clash),
                         "显式保存的 Clash 路径未往返")
        custom = [a for a in apps if not a.get("builtin")]
        self.assertEqual(len(custom), 1, "自定义卡片数量不一致")
        a = custom[0]
        self.assertEqual(a["key"], "qa_custom")
        self.assertEqual(a["game"], "测试游戏")
        self.assertEqual(a["script"], "测试脚本")
        self.assertEqual(a["accent"], "#ff8fc7")
        self.assertEqual(os.path.normpath(a["script_exe"]),
                         os.path.normpath(self.script_exe))
        self.assertEqual(os.path.normpath(a["game_exe"]),
                         os.path.normpath(self.game_exe))
        self.assertEqual(a["script_procs"], ["MYSCRIPT.EXE"])
        self.assertEqual(a["game_procs"], ["MYGAME.EXE"])
        self.assertEqual(a["download"], "https://example.com/download")
        self.assertEqual(a["fallback_version"], "v9.9.9")
        self.assertEqual(os.path.normpath(a["icon_path"]),
                         os.path.normpath(self.icon))
        # 内置 4 张卡始终存在
        self.assertEqual(len(apps), len(store.DEFAULT_APPS) + 1)

    def test_builtin_fields_roundtrip(self):
        maa = store.make_builtin("maa", self.user_root)
        maa["accent"] = "#ff0000"
        maa["download"] = "https://example.com/maa-download"
        cfg_patch, root_patch = self._ctx()
        with cfg_patch, root_patch:
            store.save_state([maa], clash="", root=self.user_root)
            apps, _clash, _root = store.load_state()
        got = next(a for a in apps if a["key"] == "maa")
        self.assertEqual(got["accent"], "#ff0000")
        self.assertEqual(got["download"], "https://example.com/maa-download")
        self.assertTrue(os.path.isfile(got["icon_path"]),
                        f"内置图标路径不存在: {got.get('icon_path')}")

    def test_legacy_plain_path_format(self):
        # v1/v2 的 {"apps": {"maa": "C:\\...\\MAA.exe"}} 兼容
        self.dump_json(self.cfg, {"apps": {"maa": self.script_exe}})
        cfg_patch, root_patch = self._ctx()
        with cfg_patch, root_patch:
            apps, _clash, root = store.load_state()
        maa = next(a for a in apps if a["key"] == "maa")
        self.assertEqual(os.path.normpath(maa["script_exe"]),
                         os.path.normpath(self.script_exe))
        self.assertEqual(os.path.normpath(root),
                         os.path.normpath(self.search_root))

    def test_utf8_bom_config_compatible(self):
        data = {"version": 3, "root": self.user_root,
                "apps": {"maa": {"accent": "#ff0000",
                                 "download": "https://example.com/maa"}}}
        self.dump_json(self.cfg, data, encoding="utf-8-sig")
        with open(self.cfg, "rb") as fh:
            self.assertTrue(fh.read(3) == b"\xef\xbb\xbf", "测试前提：文件应为 UTF-8 BOM")
        cfg_patch, root_patch = self._ctx()
        with cfg_patch, root_patch:
            apps, _clash, _root = store.load_state()
        maa = next(a for a in apps if a["key"] == "maa")
        self.assertEqual(maa["accent"], "#ff0000")
        self.assertEqual(maa["download"], "https://example.com/maa")

    def test_broken_config_falls_back_to_defaults(self):
        with open(self.cfg, "w", encoding="utf-8") as fh:
            fh.write("{ 这不是合法 JSON")
        cfg_patch, root_patch = self._ctx()
        with cfg_patch, root_patch:
            apps, clash, root = store.load_state()
        self.assertEqual(len(apps), len(store.DEFAULT_APPS))
        self.assertTrue(all(a.get("builtin") for a in apps))
        self.assertEqual(os.path.normpath(root), os.path.normpath(self.search_root))

    def test_clash_autodetect_from_candidates(self):
        # 配置里没有 Clash 时，load_state 会从 CLASH_CANDIDATES 自动探测
        self.dump_json(self.cfg, {"version": 3, "root": self.user_root})
        cfg_patch, root_patch = self._ctx()
        with cfg_patch, root_patch, \
                mock.patch.object(store, "CLASH_CANDIDATES", [self.clash]):
            _apps, clash, _root = store.load_state()
        self.assertEqual(os.path.normpath(clash), os.path.normpath(self.clash))

    def test_save_state_reports_write_failure(self):
        # QA-03 已修复：写失败不再静默，返回 False 供 UI 提示用户
        bad_cfg = os.path.join(self.tmp, "no_such_dir", "config.json")
        with mock.patch.object(store, "CONFIG", bad_cfg):
            ok = store.save_state([self._custom_app()], clash="",
                                  root=self.user_root)
        self.assertIs(ok, False, "写失败时 save_state 应返回 False")
        self.assertFalse(os.path.exists(bad_cfg))

    # ---------------------------------------------------------- config v4
    def _detect_sample(self):
        return {
            "any_of": [
                {"type": "win", "class_re": "^UnrealWindow$", "title_re": "异环",
                 "title_optional": True, "min_client_size": [200, 120]},
                {"type": "proc", "names": ["HTGame.exe"],
                 "path_re": "HTGame\\.exe$"},
            ],
            "proc_class_check": [{"name": "HTGame.exe",
                                 "win_class_re": "UnrealWindow"}],
            "launcher": {"any_of": [
                {"type": "proc", "names": ["NTELauncher.exe"]}]},
            "cloud": {"any_of": [
                {"type": "win", "class_re": "^Qt.*$", "title_re": "云"}]},
        }

    def test_v4_custom_detect_roundtrip(self):
        app = self._custom_app()
        app["detect"] = self._detect_sample()
        app["detect_custom"] = True
        cfg_patch, root_patch = self._ctx()
        with cfg_patch, root_patch:
            self.assertTrue(store.save_state([app], clash="", root=self.user_root))
            raw = json.load(open(self.cfg, "r", encoding="utf-8"))
            self.assertEqual(raw.get("version"), 4)
            saved = raw["custom_apps"][0]
            self.assertTrue(saved.get("detect_custom"))
            self.assertIn("detect", saved)
            apps, _clash, _root = store.load_state()

        custom = [a for a in apps if not a.get("builtin")][0]
        self.assertTrue(custom.get("detect_custom"))
        self.assertEqual(custom.get("detect"), store._clean_detect(app["detect"]))
        self.assertEqual(detector.read_game_rules(custom)["source"], "user")

    def test_v3_migration_only_for_legacy_procs(self):
        # QA-10 修复：只迁移「空值 / 全部是旧启动器误配」的内置 game_procs
        data = {
            "version": 3, "root": self.user_root,
            "apps": {
                "nte": {"game_procs": ["NTELAUNCHER.EXE", "LAUNCHER.EXE"]},
                "maa": {"game_procs": ["LAUNCHER.EXE"]},
                "wuwa": {"game_procs": ["MUMUPLAYER.EXE"]},
            },
            "custom_apps": [{
                "key": "custom_1", "game": "G", "script": "S",
                "script_exe": self.script_exe, "script_procs": [],
                "game_procs": ["MYGAME.EXE"], "game_exe": "",
                "accent": "#4fc3ff",
            }],
        }
        self.dump_json(self.cfg, data)
        cfg_patch, root_patch = self._ctx()
        with cfg_patch, root_patch:
            apps, _clash, _root = store.load_state()
        by_key = {a["key"]: a for a in apps}
        # 旧启动器误配 → 迁移为游戏本体进程
        self.assertEqual(by_key["nte"]["game_procs"], ["HTGAME.EXE"])
        self.assertEqual(by_key["maa"]["game_procs"], ["ARKNIGHTS.EXE"])
        # 用户自定义的非启动器进程名（如模拟器）必须保留（QA-10 修复验证）
        self.assertEqual(by_key["wuwa"]["game_procs"], ["MUMUPLAYER.EXE"])
        # 自定义卡片不受迁移影响；内置卡片不注入 detect（仍走自动规则）
        self.assertEqual(by_key["custom_1"]["game_procs"], ["MYGAME.EXE"])
        self.assertFalse(by_key["maa"].get("detect"))

    def test_v3_custom_procs_preserved_and_empty_filled(self):
        # QA-10：多进程自定义保留；空/缺失才填默认游戏本体进程
        data = {
            "version": 3, "root": self.user_root,
            "apps": {
                "maa": {"game_procs": ["MUMUPLAYER.EXE", "EMULATOR.EXE"]},
                "nte": {"game_procs": []},
                "wuwa": {},
            },
        }
        self.dump_json(self.cfg, data)
        cfg_patch, root_patch = self._ctx()
        with cfg_patch, root_patch:
            apps, _clash, _root = store.load_state()
        by_key = {a["key"]: a for a in apps}
        self.assertEqual(by_key["maa"]["game_procs"],
                         ["MUMUPLAYER.EXE", "EMULATOR.EXE"])
        self.assertEqual(by_key["nte"]["game_procs"], ["HTGAME.EXE"])
        self.assertEqual(by_key["wuwa"]["game_procs"],
                         ["CLIENT-WIN64-SHIPPING.EXE"])

    def test_v3_mixed_legacy_and_custom_procs_kept(self):
        # 记录迁移语义：只有「全部为旧启动器」才迁移；混合列表整体保留
        self.dump_json(self.cfg, {
            "version": 3, "root": self.user_root,
            "apps": {"maa": {"game_procs": ["LAUNCHER.EXE",
                                            "MUMUPLAYER.EXE"]}}})
        cfg_patch, root_patch = self._ctx()
        with cfg_patch, root_patch:
            apps, _clash, _root = store.load_state()
        maa = next(a for a in apps if a["key"] == "maa")
        self.assertEqual(maa["game_procs"],
                         ["LAUNCHER.EXE", "MUMUPLAYER.EXE"])

    def test_builtin_custom_detect_survives_migration(self):
        maa = store.make_builtin("maa", self.user_root)
        maa["detect"] = {"any_of": [
            {"type": "proc", "names": ["CUSTOM.EXE"]}]}
        maa["detect_custom"] = True
        maa["game_procs"] = ["CUSTOM.EXE"]
        cfg_patch, root_patch = self._ctx()
        with cfg_patch, root_patch:
            self.assertTrue(store.save_state([maa], clash="", root=self.user_root))
            apps, _clash, _root = store.load_state()
        got = next(a for a in apps if a["key"] == "maa")
        self.assertTrue(got.get("detect_custom"))
        self.assertEqual(got["game_procs"], ["CUSTOM.EXE"])
        self.assertEqual(got["detect"]["any_of"][0]["names"], ["CUSTOM.EXE"])

    def test_builtin_without_detect_is_migrated(self):
        maa = store.make_builtin("maa", self.user_root)
        maa["game_procs"] = ["LAUNCHER.EXE"]
        cfg_patch, root_patch = self._ctx()
        with cfg_patch, root_patch:
            store.save_state([maa], clash="", root=self.user_root)
            apps, _clash, _root = store.load_state()
        got = next(a for a in apps if a["key"] == "maa")
        self.assertEqual(got["game_procs"], ["ARKNIGHTS.EXE"])


# ---------------------------------------------------------------- exe 扫描
class FindAppExeTests(TempDirTest):
    def test_recursive_and_case_insensitive(self):
        a = self.touch("root", "A", "MAA.exe")
        b = self.touch("root", "B", "deep", "maa.EXE")
        self.touch("root", "C", "other.exe")
        root = os.path.join(self.tmp, "root")
        hits = store.find_app_exe(root, "MAA.exe")
        self.assertEqual(sorted(os.path.normpath(h) for h in hits),
                         sorted([os.path.normpath(a), os.path.normpath(b)]))

    def test_skip_dirs_and_hidden_dirs(self):
        ok = self.touch("root", "ok", "MAA.exe")
        self.touch("root", "config", "MAA.exe")        # SEARCH_SKIP
        self.touch("root", "resources", "MAA.exe")     # SEARCH_SKIP
        self.touch("root", "tools", "MAA.exe")         # SEARCH_SKIP
        self.touch("root", ".hidden", "MAA.exe")       # 点目录
        root = os.path.join(self.tmp, "root")
        hits = store.find_app_exe(root, "MAA.exe")
        self.assertEqual([os.path.normpath(h) for h in hits],
                         [os.path.normpath(ok)])

    def test_max_depth(self):
        d1 = self.touch("root", "A", "MAA.exe")
        d2 = self.touch("root", "A", "B", "MAA.exe")
        self.touch("root", "A", "B", "C", "MAA.exe")
        root = os.path.join(self.tmp, "root")
        self.assertEqual([os.path.normpath(h) for h in
                          store.find_app_exe(root, "MAA.exe", max_depth=1)],
                         [os.path.normpath(d1)])
        self.assertEqual(sorted(os.path.normpath(h) for h in
                                store.find_app_exe(root, "MAA.exe", max_depth=2)),
                         sorted([os.path.normpath(d1), os.path.normpath(d2)]))

    def test_missing_root_or_no_match(self):
        self.assertEqual(store.find_app_exe("", "MAA.exe"), [])
        self.assertEqual(store.find_app_exe(None, "MAA.exe"), [])
        self.assertEqual(store.find_app_exe(
            os.path.join(self.tmp, "not_here"), "MAA.exe"), [])
        os.makedirs(os.path.join(self.tmp, "empty"), exist_ok=True)
        self.assertEqual(store.find_app_exe(
            os.path.join(self.tmp, "empty"), "MAA.exe"), [])


class PickBestExeTests(TempDirTest):
    def test_pick_newest_folder_version(self):
        old = self.touch("MAA-v5.0.0", "MAA.exe")
        new = self.touch("MAA-v5.1.0", "MAA.exe")
        self.assertEqual(os.path.normpath(store.pick_best_exe([old, new])),
                         os.path.normpath(new))

    def test_pick_by_mtime_when_version_equal(self):
        first = self.touch("a-v1.2", "MAA.exe")
        second = self.touch("b-v1.2", "MAA.exe")
        os.utime(first, (1_600_000_000, 1_600_000_000))
        os.utime(second, (1_700_000_000, 1_700_000_000))
        self.assertEqual(os.path.normpath(store.pick_best_exe([first, second])),
                         os.path.normpath(second))

    def test_empty_and_unreadable(self):
        self.assertIsNone(store.pick_best_exe([]))
        self.assertIsNone(store.pick_best_exe(None))
        missing = os.path.join(self.tmp, "gone", "MAA.exe")
        self.assertEqual(store.pick_best_exe([missing]), missing)


# ---------------------------------------------------------------- 版本读取
class ReadVersionTests(TempDirTest):
    def _app(self, key, exe, fallback="v0.0.1"):
        return {"key": key, "script_exe": exe, "fallback_version": fallback}

    def test_nte_interface_json(self):
        exe = self.touch("MaaNTE", "MaaNTE.exe")
        self.dump_json(os.path.join(self.tmp, "MaaNTE", "interface.json"),
                       {"version": "1.6.0"})
        self.assertEqual(store.read_version(self._app("nte", exe)), "v1.6.0")

    def test_maaend_interface_json_keeps_v_prefix(self):
        exe = self.touch("MaaEnd", "MaaEnd.exe")
        self.dump_json(os.path.join(self.tmp, "MaaEnd", "interface.json"),
                       {"version": "v2.33.0"})
        self.assertEqual(store.read_version(self._app("maaend", exe)), "v2.33.0")

    def test_maa_cache_summary(self):
        exe = self.touch("MAA", "MAA.exe")
        self.dump_json(
            os.path.join(self.tmp, "MAA", "cache", "version", "summary.json"),
            {"stable": {"version": "6.19.0"}})
        self.assertEqual(store.read_version(self._app("maa", exe)), "v6.19.0")

    def test_wuwa_app_json(self):
        exe = self.touch("WuwaMAA", "ok-ww", "ok-ww.exe")
        self.dump_json(
            os.path.join(self.tmp, "WuwaMAA", "ok-ww", "data", "apps",
                         "ok-ww", "app.json"),
            {"current_version": "v3.7.4"})
        self.assertEqual(store.read_version(self._app("wuwa", exe)), "v3.7.4")

    def test_fallback_when_files_missing(self):
        app = self._app("nte", os.path.join(self.tmp, "nope", "MaaNTE.exe"),
                        fallback="v1.6.0")
        self.assertEqual(store.read_version(app), "v1.6.0")

    def test_fallback_when_json_broken(self):
        exe = self.touch("MaaNTE", "MaaNTE.exe")
        with open(os.path.join(self.tmp, "MaaNTE", "interface.json"),
                  "w", encoding="utf-8") as fh:
            fh.write("{broken")
        self.assertEqual(store.read_version(self._app("nte", exe, "v9.9.9")),
                         "v9.9.9")

    def test_wuwa_missing_current_version_falls_back(self):
        # QA-01 已修复：字段缺失时回退 fallback_version（不再返回 ""）
        exe = self.touch("WuwaMAA", "ok-ww", "ok-ww.exe")
        self.dump_json(
            os.path.join(self.tmp, "WuwaMAA", "ok-ww", "data", "apps",
                         "ok-ww", "app.json"), {})
        self.assertEqual(store.read_version(self._app("wuwa", exe, "v0.0.1")),
                         "v0.0.1")

    def test_non_string_version_falls_back(self):
        # QA-02 已修复：version 为 null/数组/布尔等非版本类型时回退 fallback_version
        exe = self.touch("MaaNTE", "MaaNTE.exe")
        interface = os.path.join(self.tmp, "MaaNTE", "interface.json")
        for payload in ({"version": None}, {"version": []}, {"version": True}):
            with self.subTest(payload=payload):
                self.dump_json(interface, payload)
                self.assertEqual(
                    store.read_version(self._app("nte", exe, "v1.6.0")),
                    "v1.6.0")


# ---------------------------------------------------------------- 进程
class ProcessTests(unittest.TestCase):
    def test_snapshot_processes_contains_current(self):
        names = store.snapshot_processes()
        self.assertIsInstance(names, set)
        self.assertTrue(names, "进程快照为空，ctypes 调用可能失败")
        self.assertTrue(all(isinstance(n, str) and n for n in names))
        current = os.path.basename(sys.executable).upper()
        self.assertIn(current, names,
                      f"当前进程 {current} 不在进程快照中")

    def test_pids_for_procs_contains_self(self):
        current = os.path.basename(sys.executable).upper()
        self.assertIn(os.getpid(), store.pids_for_procs({current}))

    def test_pids_for_unknown_proc_empty(self):
        self.assertEqual(store.pids_for_procs({"__NO_SUCH_PROC_QA__"}), set())


# ---------------------------------------------------------------- 渲染冒烟
class RenderSmokeTests(unittest.TestCase):
    def _card(self, key, game, accent, icon):
        return {"key": key, "game": game, "accent": accent,
                "icon_path": os.path.join(ASSETS, icon)}

    def test_render_window_size_full_page(self):
        apps = [
            self._card("maa", "明日方舟", "#4fc3ff", "maa.png"),
            self._card("nte", "异环", "#b98bff", "nte.png"),
            self._card("wuwa", "鸣潮", "#5ee7c7", "wuwa.png"),
            self._card("maaend", "明日方舟终末地", "#ffe066", "maaend.png"),
        ]
        img = render.render_window(apps, hover_index=2, icons=None, total=4)
        self.assertEqual(img.size, (1200, 560))
        self.assertEqual(img.size, (theme.W, theme.H))
        self.assertEqual(img.mode, "RGB")
        self.assertIsNotNone(img.getbbox(), "渲染结果为全透明 / 空图")

    def test_render_window_empty_page(self):
        img = render.render_window([], hover_index=-1, icons=[], total=0)
        self.assertEqual(img.size, (theme.W, theme.H))

    def test_script_button_sizes(self):
        for state in ("normal", "hover", "off"):
            with self.subTest(state=state):
                img = render.render_script_button("#4fc3ff", state)
                self.assertEqual(img.size, (theme.BTN_W, theme.BTN_H))
                self.assertEqual(img.size, (99, 44))
                self.assertEqual(img.mode, "RGBA")

    def test_game_button_sizes(self):
        for state in ("normal", "hover"):
            with self.subTest(state=state):
                img = render.render_game_button(state)
                self.assertEqual(img.size, (theme.BTN_W, theme.BTN_H))

    def test_dot_sizes(self):
        self.assertEqual(render.render_dot().size, (22, 22))
        self.assertEqual(render.render_dot(on=False).size, (22, 22))
        self.assertEqual(render.render_dot(on=True, size=8).size, (28, 28))
        self.assertEqual(render.render_dot(on=True, color=(255, 0, 0)).mode,
                         "RGBA")

    def test_page_arrow_sizes(self):
        for direction in ("left", "right"):
            for hovered in (False, True):
                with self.subTest(direction=direction, hovered=hovered):
                    img = render.render_page_arrow(direction, hovered)
                    self.assertEqual(img.size, (32, 32))

    def test_render_hub_icon(self):
        self.assertEqual(render.render_hub_icon().size, (256, 256))

    def test_helpers(self):
        self.assertEqual(render.hex2rgb("#4fc3ff"), (79, 195, 255))
        self.assertEqual(render.accent_rgba("#4fc3ff", 22), (79, 195, 255, 22))


# ---------------------------------------------------------------- 包导入
class ImportSmokeTests(unittest.TestCase):
    """v0.5 验收要求 `import gamehub.ui` 通过（只 import，不创建窗口）。"""

    def test_ui_import(self):
        import importlib
        ui = importlib.import_module("gamehub.ui")
        self.assertTrue(callable(getattr(ui, "run", None)), "ui.run 不存在或不可调用")
        self.assertTrue(hasattr(ui, "GameHub"), "主窗口类 GameHub 不存在")

    def test_version_is_semver(self):
        import re
        from gamehub import VERSION
        self.assertRegex(VERSION, r"^\d+\.\d+\.\d+$",
                         f"VERSION 格式异常：{VERSION!r}")


# ---------------------------------------------------------------- v0.5 自动检测
@unittest.skipUnless(hasattr(store, "find_game_candidates"),
                     "store.find_game_candidates 尚未实现（feature-dev 开发中）")
class GameCandidatesTests(TempDirTest):
    """v0.5「游戏启动程序自动检测」测试。

    find_game_candidates 正常会扫描真实注册表/磁盘，因此这里通过 mock 把
    注册表和常见目录数据源限制在临时目录，结果确定、不依赖本机安装。
    内部私有函数（_find_game_exes 等）若被重命名/重构，用例自动 skip 并提示。
    """

    def _big_exe(self, *parts):
        # >120KB，避免 _score_exe_path 把文件当成辅助程序扣分
        return self.touch(*parts, content=b"\0" * 130_000)

    def _require(self, *names):
        missing = [name for name in names if not hasattr(store, name)]
        if missing:
            self.skipTest(f"store 缺少内部实现 {missing}（feature-dev 结构可能调整）")

    def _call(self, app, **kwargs):
        self._require("find_game_candidates", "_iter_registry_entries",
                      "_fs_scan_roots")
        try:
            return store.find_game_candidates(app, **kwargs)
        except TypeError as exc:   # 签名变化时不要误报功能缺陷
            self.skipTest(f"find_game_candidates 调用签名不匹配：{exc}")

    def test_kw_hit_word_boundary(self):
        self._require("_kw_hit")
        self.assertFalse(store._kw_hit("center.exe", "nte"))   # 短缩写不命中 center
        self.assertTrue(store._kw_hit("NTE.exe", "nte"))
        self.assertTrue(store._kw_hit("MuMu Player", "mumu"))
        self.assertTrue(store._kw_hit("明日方舟", "明日方舟"))
        self.assertFalse(store._kw_hit("", "mumu"))
        self.assertFalse(store._kw_hit("mumu", ""))

    def test_game_profile(self):
        self._require("_game_profile", "GAME_KEYWORDS", "GAME_EXE_HINTS")
        key, words, hints = store._game_profile({"key": "maa", "game": "明日方舟"})
        self.assertEqual(key, "maa")
        self.assertIn("arknights", [word.lower() for word in words])
        self.assertIn("mumuplayer.exe", hints)
        key2, _words2, _hints2 = store._game_profile({"key": "x", "game": "鸣潮"})
        self.assertEqual(key2, "wuwa")            # 按游戏名反查 profile
        _key3, words3, hints3 = store._game_profile(None)
        self.assertGreater(len(words3), 4)        # None = 全部游戏合集
        self.assertIn("mumuplayer.exe", hints3)

    def test_score_exe_path(self):
        self._require("_score_exe_path")
        exe = self._big_exe("GameA", "mumuplayer.exe")
        hit = store._score_exe_path(exe, 1, ("mumuplayer", "mumu"),
                                    ("mumuplayer.exe",))
        self.assertIsNotNone(hit)
        self.assertEqual(os.path.normpath(hit["path"]), os.path.normpath(exe))
        self.assertGreater(hit["score"], 0)
        # 与关键词无关的 exe 不产生候选
        self.assertIsNone(store._score_exe_path(
            exe, 1, ("__unrelated_keyword__",), ()))
        # 卸载/更新类噪声 exe 被排除
        noise = self._big_exe("GameA", "unins000.exe")
        self.assertIsNone(store._score_exe_path(
            noise, 1, ("mumuplayer",), ("mumuplayer.exe",)))

    def test_clean_icon_path_quoted_index(self):
        # QA-09 已修复：注册表常见 `"C:\x\game.exe",0` / `C:\x\game.exe,0` 能解析
        self._require("_clean_icon_path")
        exe = self._big_exe("MuMu", "mumuplayer.exe")
        self.assertEqual(store._clean_icon_path('"' + exe + '",0'), exe)
        self.assertEqual(store._clean_icon_path(exe + ",0"), exe)
        self.assertEqual(store._clean_icon_path('"' + exe + '"'), exe)
        self.assertEqual(store._clean_icon_path(exe), exe)
        self.assertEqual(store._clean_icon_path(""), "")
        # 非 exe（图标文件）不返回路径
        self.assertEqual(store._clean_icon_path(
            os.path.join(self.tmp, "MuMu", "icon.ico")), "")

    def test_find_game_exes_temp_tree(self):
        self._require("_find_game_exes")
        import time as _time
        root = os.path.join(self.tmp, "root")
        exe = self._big_exe("root", "MuMu Player", "mumuplayer.exe")
        skipped = self._big_exe("root", "cache", "mumuplayer.exe")
        noise = self._big_exe("root", "MuMu Player", "unins000.exe")
        hits = store._find_game_exes(root, ("mumuplayer", "mumu"),
                                     ("mumuplayer.exe",),
                                     _time.monotonic() + 10)
        paths = [os.path.normpath(hit["path"]) for hit in hits]
        self.assertIn(os.path.normpath(exe), paths)
        self.assertNotIn(os.path.normpath(skipped), paths)   # GAME_SCAN_SKIP
        self.assertNotIn(os.path.normpath(noise), paths)     # exe 噪声词
        for path in paths:                                   # 只来自临时目录
            self.assertTrue(os.path.normpath(path).startswith(
                os.path.normpath(root)))

    def test_find_game_candidates_temp_scan_only(self):
        root = os.path.join(self.tmp, "root")
        exe = self._big_exe("root", "MuMu Player", "mumuplayer.exe")
        with mock.patch.object(store, "_iter_registry_entries",
                               return_value=[]), \
                mock.patch.object(store, "_fs_scan_roots",
                                  return_value=[(root, "MuMu Player")]):
            result = self._call({"key": "maa", "game": "明日方舟"}, limit=5)
        self.assertIsInstance(result, list)
        self.assertTrue(result, "临时目录中的 mumuplayer.exe 应被检测到")
        self.assertEqual(os.path.normpath(result[0]["path"]),
                         os.path.normpath(exe))
        for item in result:
            self.assertEqual(set(item), {"path", "name", "source", "score"})
            self.assertEqual(item["source"], "常见目录")
            self.assertGreater(item["score"], 0)
        scores = [item["score"] for item in result]
        self.assertEqual(scores, sorted(scores, reverse=True),
                         "候选应按 score 降序")

    def test_find_game_candidates_registry_source(self):
        install = os.path.join(self.tmp, "MuMu")
        os.makedirs(install, exist_ok=True)
        exe = self._big_exe("MuMu", "mumuplayer.exe")
        entry = {"name": "MuMu模拟器", "install": install,
                 "icon": '"' + exe + '",0'}
        with mock.patch.object(store, "_iter_registry_entries",
                               return_value=[entry]), \
                mock.patch.object(store, "_fs_scan_roots", return_value=[]):
            result = self._call({"key": "maa"}, limit=3)
        self.assertTrue(result, "注册表 InstallLocation 中的启动程序应被检测到")
        self.assertEqual(result[0]["source"], "注册表")
        self.assertEqual(os.path.normpath(result[0]["path"]),
                         os.path.normpath(exe))

    def test_find_game_candidates_limit(self):
        root = os.path.join(self.tmp, "root")
        for index in range(3):
            self._big_exe("root", f"MuMu{index}", "mumuplayer.exe")
        with mock.patch.object(store, "_iter_registry_entries",
                               return_value=[]), \
                mock.patch.object(store, "_fs_scan_roots",
                                  return_value=[(root, "Root")]):
            one = self._call({"key": "maa"}, limit=1)
            all_hits = self._call({"key": "maa"}, limit=9)
        self.assertEqual(len(one), 1)
        self.assertEqual(len(all_hits), 3)


# ---------------------------------------------------------------- v0.6 检测规则
def _win(class_name="", title="", width=800, height=600, pid=1,
         iconic=False, visible=True, hwnd=1):
    """构造 snapshot_windows() 风格的窗口字典，供纯函数匹配测试。"""
    return {"hwnd": hwnd, "class_name": class_name, "title": title,
            "width": width, "height": height, "pid": pid,
            "iconic": iconic, "visible": visible}


def _clear_detector_caches():
    detector.reset_cache()
    detector._AUTO_RULES_CACHE.clear()


class DetectRuleCleanTests(unittest.TestCase):
    """store._clean_detect*：config v4 检测规则 schema 解析/清洗。"""

    def test_win_rule_full_schema(self):
        cleaned = store._clean_detect_rule({
            "type": "window", "class_re": " ^UnrealWindow$ ",
            "title_re": " 异环 ", "title_optional": True, "match": "any",
            "require_visible": True, "min_client_size": [200.0, 120.0],
            "proc_names": "HTGame.exe, other.exe",
            "proc_path_re": r"HTGame\.exe$", "junk": 1,
        })
        self.assertEqual(cleaned, {
            "type": "win", "class_re": "^UnrealWindow$", "title_re": "异环",
            "proc_path_re": r"HTGame\.exe$", "title_optional": True,
            "match": "any", "require_visible": True,
            "min_client_size": [200, 120],
            "proc_names": ["HTGame.exe", "other.exe"],
        })

    def test_type_aliases_and_invalid_rules(self):
        self.assertEqual(
            store._clean_detect_rule({"type": "window", "class_re": "X"})["type"],
            "win")
        self.assertEqual(
            store._clean_detect_rule({"type": "process",
                                      "names": ["A.exe"]}), 
            {"type": "proc", "names": ["A.exe"]})
        for bad in (None, "win", 3, [], {"type": "bogus"}, {"type": "win"},
                    {"type": "proc"}, {"type": "adb"}, {}):
            with self.subTest(bad=bad):
                self.assertIsNone(store._clean_detect_rule(bad))

    def test_text_helpers(self):
        # _detect_texts 为历史兼容 helper（仍按空白拆分，供旧调用/测试）
        self.assertEqual(store._detect_texts("a.exe, b.exe；c.exe d.exe"),
                         ["a.exe", "b.exe", "c.exe", "d.exe"])
        self.assertEqual(store._detect_texts([" a ", "", None, 3]), ["a"])
        self.assertEqual(store._detect_texts(None), [])
        self.assertEqual(store._detect_texts({"x": 1}), [])
        self.assertEqual(store._detect_text(None), "")
        self.assertEqual(store._detect_text("  x  "), "x")
        # _detect_names 用于进程名/包名：只按逗号/分号/换行拆分
        self.assertEqual(store._detect_names("A.exe, B B.exe；C.exe"),
                         ["A.exe", "B B.exe", "C.exe"])
        self.assertEqual(store._detect_names([" A ", 3, None]), ["A"])

    def test_proc_name_with_space_not_split(self):
        # QA-12 修复：字符串进程名不再按空白拆成两个
        cleaned = store._clean_detect_rule({
            "type": "proc", "names": "Wuthering Waves.exe"})
        self.assertEqual(cleaned["names"], ["Wuthering Waves.exe"])
        self.assertEqual(store._clean_detect_rule({
            "type": "proc", "names": "A.exe, Wuthering Waves.exe"})["names"],
            ["A.exe", "Wuthering Waves.exe"])
        win = store._clean_detect_rule({
            "type": "win", "class_re": "X",
            "proc_names": "Client-Win64-Shipping.exe, Wuthering Waves.exe"})
        self.assertEqual(win["proc_names"],
                         ["Client-Win64-Shipping.exe", "Wuthering Waves.exe"])
        adb = store._clean_detect_rule({
            "type": "adb", "pkg": "com.a.b, com.c.d"})
        self.assertEqual(adb["pkg"], ["com.a.b", "com.c.d"])

    def test_proc_class_check_dict_and_list(self):
        group = store._clean_detect_group({
            "proc_class_check": {"name": "HTGame.exe",
                                 "win_class_re": "UnrealWindow",
                                 "path_re": "x"}})
        self.assertEqual(group["proc_class_check"][0]["name"], "HTGame.exe")
        self.assertEqual(group["proc_class_check"][0]["path_re"], "x")
        group2 = store._clean_detect_group({
            "proc_class_check": [{"name": "A.exe", "win_class_re": "C"},
                                 {"name": "", "win_class_re": "C"},
                                 "junk"]})
        self.assertEqual(len(group2["proc_class_check"]), 1)
        self.assertIsNone(store._clean_detect_group({}))

    def test_full_detect_groups_and_invalid(self):
        cleaned = store._clean_detect({
            "any_of": [{"type": "win", "class_re": "X"},
                       {"type": "bogus"}],
            "launcher": {"any_of": [{"type": "proc",
                                     "names": ["L.exe"]}]},
            "cloud": {"any_of": [{"type": "win", "title_re": "云"}]},
        })
        self.assertEqual(len(cleaned["any_of"]), 1)
        self.assertIn("launcher", cleaned)
        self.assertIn("cloud", cleaned)
        self.assertNotIn("source", cleaned)
        self.assertIsNone(store._clean_detect({}))
        self.assertIsNone(store._clean_detect(None))
        self.assertIsNone(store._clean_detect(
            {"any_of": [{"type": "bogus"}]}))

    def test_min_size_and_flag_edges(self):
        rule = store._clean_detect_rule({
            "type": "win", "class_re": "X", "min_client_size": [1],
            "match": "ANY", "title_optional": False, "require_visible": False})
        self.assertNotIn("min_client_size", rule)
        self.assertNotIn("match", rule)          # 只接受小写 any/all
        self.assertNotIn("title_optional", rule)
        self.assertNotIn("require_visible", rule)
        rule2 = store._clean_detect_rule({
            "type": "win", "class_re": "X",
            "min_client_size": [200.0, 120.0]})
        self.assertEqual(rule2["min_client_size"], [200, 120])


class DetectorInterfaceRulesTests(TempDirTest):
    """detector 自动规则：interface.json 解析 / 内置表回退 / 名称反查。"""

    def setUp(self):
        super().setUp()
        _clear_detector_caches()
        self.addCleanup(_clear_detector_caches)

    def _script_dir(self, exe_name="MaaNTE.exe", interface=None,
                    folder="MaaNTE"):
        script_dir = os.path.join(self.tmp, folder)
        os.makedirs(script_dir, exist_ok=True)
        exe = os.path.join(script_dir, exe_name)
        with open(exe, "wb") as fh:
            fh.write(b"stub")
        if interface is not None:
            self.dump_json(os.path.join(script_dir, "interface.json"),
                           interface)
        return script_dir, exe

    def test_extract_win32_controllers_and_cloud(self):
        interface = {"controller": [
            {"type": "win32", "name": "PC",
             "win32": {"class_regex": "UnrealWindow",
                       "window_regex": "^异环$"}},
            {"type": "win32", "name": "PC-2",
             "win32": {"class_regex": "^Qt.*$", "window_regex": "^异环$"}},
            {"type": "win32", "name": "PC-dup",
             "win32": {"class_regex": "UnrealWindow",
                       "window_regex": "^异环$"}},
            {"type": "win32", "name": "云·异环",
             "win32": {"class_regex": "^Qt.*$",
                       "window_regex": r"^\s*云.*?异环\s*$"}},
            {"type": "adb", "name": "Android",
             "adb": {"package_name": "com.x"}},
        ]}
        script_dir, _exe = self._script_dir(interface=interface)
        rules = detector._rules_from_interface("nte", script_dir)
        win_rules = [rule for rule in rules["any_of"]
                     if detector._rule_kind(rule) == "window"]
        self.assertEqual([rule["class_re"] for rule in win_rules],
                         ["UnrealWindow", "^Qt.*$"], "去重且按 controller 顺序")
        for rule in win_rules:
            self.assertEqual(rule["min_client_size"], [200, 120])
            self.assertEqual(rule["type"], "win")
        # 内置表的非窗口规则（进程）保留在 any_of
        self.assertTrue(any(detector._rule_kind(rule) == "proc"
                            and "HTGame.exe" in (rule.get("names") or [])
                            for rule in rules["any_of"]))
        self.assertEqual(rules["launcher"],
                         detector.BUILTIN_RULES["nte"]["launcher"])
        cloud = rules["cloud"]["any_of"]
        self.assertEqual(len(cloud), 1)
        self.assertEqual(cloud[0]["class_re"], "^Qt.*$")

    def test_missing_invalid_or_no_win32(self):
        self.assertIsNone(detector._rules_from_interface("nte", ""))
        self.assertIsNone(detector._rules_from_interface(
            "nte", os.path.join(self.tmp, "not_here")))
        bad_dir, _exe = self._script_dir(folder="bad")
        with open(os.path.join(bad_dir, "interface.json"), "w",
                  encoding="utf-8") as fh:
            fh.write("{broken")
        self.assertIsNone(detector._rules_from_interface("nte", bad_dir))
        adb_dir, _exe = self._script_dir(
            folder="adbonly", interface={"controller": [
                {"type": "adb", "adb": {"package_name": "com.x"}}]})
        self.assertIsNone(detector._rules_from_interface("nte", adb_dir))
        empty_dir, _exe = self._script_dir(
            folder="emptywin", interface={"controller": [
                {"type": "win32", "win32": {}}]})
        self.assertIsNone(detector._rules_from_interface("nte", empty_dir))

    def test_read_auto_rules_builtin_fallback_and_deepcopy(self):
        script_dir, exe = self._script_dir(interface=None)
        rules = detector.read_auto_rules({"key": "nte", "script_exe": exe})
        self.assertEqual(rules, detector.BUILTIN_RULES["nte"])
        rules["any_of"].append({"type": "proc", "names": ["INJECTED.EXE"]})
        again = detector.read_auto_rules({"key": "nte", "script_exe": exe})
        self.assertNotIn(["INJECTED.EXE"],
                         [rule.get("names") for rule in again["any_of"]])
        # 内置表本身未被污染
        self.assertNotIn(["INJECTED.EXE"],
                         [rule.get("names") for rule in
                          detector.BUILTIN_RULES["nte"]["any_of"]])

    def test_read_auto_rules_infers_by_game_name(self):
        cases = {"鸣潮": "wuwa", "异环": "nte", "明日方舟": "maa",
                 "明日方舟终末地": "maaend",
                 "明日方舟：终末地": "maaend"}   # QA-11 修复：最长/精确匹配
        for game, expected in cases.items():
            with self.subTest(game=game):
                rules = detector.read_auto_rules({"game": game})
                self.assertEqual(rules, detector.BUILTIN_RULES[expected])

    def test_game_profile_longest_name_match(self):
        # QA-11 修复：更长的「明日方舟终末地」优先于较短的「明日方舟」
        self.assertEqual(
            store._game_profile({"game": "明日方舟终末地"})[0], "maaend")
        self.assertEqual(
            store._game_profile({"game": "明日方舟：终末地"})[0], "maaend")
        self.assertEqual(store._game_profile({"game": "明日方舟"})[0], "maa")
        self.assertEqual(store._game_profile({"game": "异环"})[0], "nte")

    def test_auto_rules_cache_reuses_and_invalidates_on_mtime(self):
        script_dir, exe = self._script_dir(interface={"controller": [
            {"type": "win32", "name": "PC",
             "win32": {"class_regex": "Before", "window_regex": "X"}}]})
        app = {"key": "nte", "script_exe": exe}
        first = detector.read_auto_rules(app)
        second = detector.read_auto_rules(app)
        self.assertEqual(first, second)
        self.assertIsNot(first, second)          # 返回深拷贝，调用方可放心改
        self.dump_json(os.path.join(script_dir, "interface.json"),
                       {"controller": [{"type": "win32", "name": "PC",
                                        "win32": {"class_regex": "After",
                                                  "window_regex": "Y"}}]})
        stamp = time.time() + 10
        os.utime(os.path.join(script_dir, "interface.json"), (stamp, stamp))
        third = detector.read_auto_rules(app)
        classes = [rule.get("class_re") for rule in third["any_of"]
                   if detector._rule_kind(rule) == "window"]
        self.assertIn("After", classes)
        self.assertNotIn("Before", classes)


class BuiltinRuleTableTests(unittest.TestCase):
    """内置规则表结构校验（四款内置游戏）。"""

    KEYS = ("maa", "nte", "wuwa", "maaend")

    def _assert_rule(self, rule, where):
        kind = detector._rule_kind(rule)
        self.assertIn(kind, ("window", "proc", "adb"), f"{where}: {rule}")
        if kind == "window":
            self.assertTrue(rule.get("class_re") or rule.get("title_re"),
                            f"{where}: 窗口规则缺少类/标题正则")
        elif kind == "proc":
            self.assertTrue(rule.get("names"), f"{where}: 进程规则缺少进程名")
        else:
            self.assertTrue(rule.get("pkg"), f"{where}: ADB 规则缺少包名")

    def _assert_group(self, group, where):
        self.assertIsInstance(group, dict, where)
        self.assertTrue(group.get("any_of"), where)
        for rule in group["any_of"]:
            self._assert_rule(rule, where)

    def test_builtin_rules_schema(self):
        for key in self.KEYS:
            with self.subTest(key=key):
                rules = detector.BUILTIN_RULES[key]
                self.assertTrue(rules.get("any_of"), f"{key}: any_of 为空")
                for rule in rules["any_of"]:
                    self._assert_rule(rule, key)
                for field in ("launcher", "cloud"):
                    if rules.get(field):
                        self._assert_group(rules[field], f"{key}.{field}")

    def test_builtin_expected_targets(self):
        nte_launcher = detector.BUILTIN_RULES["nte"]["launcher"]["any_of"]
        self.assertTrue(any(rule.get("names") == ["NTELauncher.exe"]
                            for rule in nte_launcher))
        wuwa_win = next(rule for rule in detector.BUILTIN_RULES["wuwa"]["any_of"]
                        if detector._rule_kind(rule) == "window")
        self.assertTrue(wuwa_win.get("title_optional"))
        self.assertIn("Client-Win64-Shipping.exe",
                      wuwa_win.get("proc_names") or [])
        maa_adb = next(rule for rule in detector.BUILTIN_RULES["maa"]["any_of"]
                       if detector._rule_kind(rule) == "adb")
        self.assertIn("com.hypergryph.arknights", maa_adb["pkg"])
        maaend_proc = next(rule for rule in detector.BUILTIN_RULES["maaend"]["any_of"]
                           if detector._rule_kind(rule) == "proc")
        self.assertIn("Endfield.exe", maaend_proc["names"])


class WindowMatchTests(unittest.TestCase):
    """detector 窗口规则纯函数匹配（不枚举真实窗口）。"""

    def test_case_insensitive_class_and_title(self):
        rule = {"type": "win", "class_re": "^UnityWndClass$",
                "title_re": r"^\s*(明日方舟|Arknights)"}
        match = detector._match_win_rule(rule, [_win("unitywndclass", " 明日方舟")])
        self.assertIsNotNone(match)
        self.assertEqual(match["hwnd"], 1)
        self.assertIsNotNone(detector._match_win_rule(
            rule, [_win("UnityWndClass", "Arknights")]))

    def test_title_optional(self):
        rule = {"type": "win", "class_re": "^UnrealWindow$",
                "title_re": "NOMATCH", "title_optional": True}
        self.assertIsNotNone(detector._match_win_rule(
            rule, [_win("UnrealWindow", "whatever")]))
        strict = {"type": "win", "class_re": "^UnrealWindow$",
                  "title_re": "NOMATCH"}
        self.assertIsNone(detector._match_win_rule(
            strict, [_win("UnrealWindow", "whatever")]))

    def test_match_any_vs_all(self):
        window = [_win("UnityWndClass", "other")]
        all_rule = {"type": "win", "class_re": "^UnityWndClass$",
                    "title_re": "明日方舟"}
        self.assertIsNone(detector._match_win_rule(all_rule, window))
        any_rule = dict(all_rule, match="any")
        self.assertIsNotNone(detector._match_win_rule(any_rule, window))

    def test_empty_or_invalid_rule(self):
        self.assertIsNone(detector._match_win_rule({"type": "win"},
                                                   [_win("X", "X")]))
        self.assertIsNone(detector._match_win_rule(
            {"type": "win", "class_re": "X"}, []))
        # 非法正则 + 无标题正则 → 无法匹配
        self.assertIsNone(detector._match_win_rule(
            {"type": "win", "class_re": "["}, [_win("[", "")]))

    def test_min_client_size_and_iconic(self):
        rule = {"type": "win", "class_re": "X", "min_client_size": [200, 120]}
        self.assertIsNone(detector._match_win_rule(
            rule, [_win("X", "", width=199, height=600)]))
        self.assertIsNotNone(detector._match_win_rule(
            rule, [_win("X", "", width=200, height=120)]))
        # 最小化窗口不做尺寸过滤（避免最小化被判为关闭）
        self.assertIsNotNone(detector._match_win_rule(
            rule, [_win("X", "", width=10, height=10, iconic=True)]))

    def test_require_visible(self):
        rule = {"type": "win", "class_re": "X", "require_visible": True}
        self.assertIsNone(detector._match_win_rule(
            rule, [_win("X", "", visible=False)]))
        self.assertIsNotNone(detector._match_win_rule(
            rule, [_win("X", "")]))
        self.assertIsNotNone(detector._match_win_rule(
            {"type": "win", "class_re": "X"},
            [_win("X", "", visible=False)]))

    def test_multiple_controllers_union(self):
        rules = {"any_of": [
            {"type": "win", "class_re": "^ClassA$"},
            {"type": "win", "class_re": "^ClassB$"},
        ]}
        match = detector._match_detect(
            rules, [_win("ClassB", "", hwnd=5)], set(), [])
        self.assertIsNotNone(match)
        self.assertEqual(match["reason"], "window")
        self.assertEqual(match["hwnd"], 5)

    def test_window_proc_double_check(self):
        rule = {"type": "win", "class_re": "UnrealWindow",
                "proc_names": ["Client-Win64-Shipping.exe"],
                "proc_path_re": r"Wuthering Waves\\Wuthering Waves Game\\Client"
                                 r"\\Binaries\\Win64\\Client-Win64-Shipping\.exe$"}
        window = [_win("UnrealWindow", "", pid=42)]
        good = r"E:\Wuthering Waves\Wuthering Waves Game\Client\Binaries\Win64" \
               r"\Client-Win64-Shipping.exe"
        with mock.patch.object(detector, "_pid_path", return_value=good):
            self.assertIsNotNone(detector._match_win_rule(rule, window))
        with mock.patch.object(detector, "_pid_path",
                               return_value=r"E:\Other\foo.exe"):
            self.assertIsNone(detector._match_win_rule(rule, window))
        # 路径取不到 → 用同名进程 pid 集合核对；仍取不到 → 放行
        with mock.patch.object(detector, "_pid_path", return_value=""), \
                mock.patch.object(store, "pids_for_procs", return_value={42}):
            self.assertIsNotNone(detector._match_win_rule(rule, window))
        with mock.patch.object(detector, "_pid_path", return_value=""), \
                mock.patch.object(store, "pids_for_procs", return_value={99}):
            self.assertIsNone(detector._match_win_rule(rule, window))
        with mock.patch.object(detector, "_pid_path", return_value=""), \
                mock.patch.object(store, "pids_for_procs", return_value=set()):
            self.assertIsNotNone(detector._match_win_rule(rule, window))


class ProcMatchTests(unittest.TestCase):
    """detector 进程规则匹配与路径读取降级。"""

    def test_names_case_insensitive_and_empty(self):
        rule = {"type": "proc", "names": ["htgame.exe"]}
        self.assertTrue(detector._match_proc_rule(rule, {"HTGAME.EXE"}))
        self.assertFalse(detector._match_proc_rule(rule, {"OTHER.EXE"}))
        self.assertFalse(detector._match_proc_rule(rule, set()))
        self.assertFalse(detector._match_proc_rule(
            {"type": "proc", "names": []}, {"HTGAME.EXE"}))

    def test_path_re_match_and_mismatch(self):
        rule = {"type": "proc", "names": ["HTGame.exe"],
                "path_re": r"\\Binaries\\Win64\\HTGame\.exe$"}
        with mock.patch.object(store, "pids_for_procs", return_value={7}), \
                mock.patch.object(detector, "_pid_path", return_value=r"D:\Game"
                                  r"\Client\WindowsNoEditor\HT\Binaries\Win64"
                                  r"\HTGame.exe"):
            self.assertTrue(detector._match_proc_rule(rule, {"HTGAME.EXE"}))
        with mock.patch.object(store, "pids_for_procs", return_value={7}), \
                mock.patch.object(detector, "_pid_path",
                                  return_value=r"D:\Game\other.exe"):
            self.assertFalse(detector._match_proc_rule(rule, {"HTGAME.EXE"}))

    def test_path_unavailable_degrades_to_name_only(self):
        rule = {"type": "proc", "names": ["HTGame.exe"],
                "path_re": r"HTGame\.exe$"}
        with mock.patch.object(store, "pids_for_procs", return_value=set()):
            self.assertTrue(detector._match_proc_rule(rule, {"HTGAME.EXE"}))
        with mock.patch.object(store, "pids_for_procs", return_value={7}), \
                mock.patch.object(detector, "_pid_path", return_value=""):
            self.assertTrue(detector._match_proc_rule(rule, {"HTGAME.EXE"}))


class GameRulesSourceTests(TempDirTest):
    """read_game_rules 优先级：用户自定义 > interface/内置自动 > 旧 game_procs。"""

    def setUp(self):
        super().setUp()
        _clear_detector_caches()
        self.addCleanup(_clear_detector_caches)

    def test_user_rules_priority(self):
        user = {"any_of": [{"type": "win", "class_re": "^UnrealWindow$",
                            "title_re": "异环"}]}
        rules = detector.read_game_rules({"key": "nte", "detect": user})
        self.assertEqual(rules["source"], "user")
        self.assertEqual(rules["any_of"], store._clean_detect(user)["any_of"])

    def test_invalid_user_rules_fall_back_to_auto(self):
        app = {"key": "maa",
               "detect": {"any_of": [{"type": "bogus"},
                                     {"type": "win"}]}}
        rules = detector.read_game_rules(app)
        self.assertEqual(rules["source"], "auto")
        self.assertEqual(detector._schema_only(rules),
                         detector._schema_only(detector.BUILTIN_RULES["maa"]))

    def test_legacy_game_procs_fallback(self):
        app = {"key": "custom_qa_1", "game": "__qa_custom_game__",
               "game_procs": ["CUSTOM.EXE"]}
        rules = detector.read_game_rules(app)
        self.assertEqual(rules["source"], "legacy")
        proc_rules = [rule for rule in rules["any_of"]
                      if detector._rule_kind(rule) == "proc"]
        self.assertEqual(proc_rules[0]["names"], ["CUSTOM.EXE"])

    def test_no_rules(self):
        app = {"key": "custom_qa_2", "game": "__qa_custom_game__"}
        rules = detector.read_game_rules(app)
        self.assertEqual(rules["source"], "none")
        self.assertEqual(rules["any_of"], [])

    def test_rules_to_fields(self):
        wuwa = detector.rules_to_fields(detector.BUILTIN_RULES["wuwa"])
        self.assertEqual(wuwa["win_class"], "^UnrealWindow$")
        self.assertIn("Wuthering Waves", wuwa["win_title"])
        self.assertIn("Client-Win64-Shipping.exe", wuwa["detect_procs"])
        self.assertIn("Wuthering Waves.exe", wuwa["detect_procs"])
        self.assertEqual(wuwa["adb_pkg"], "")
        maa = detector.rules_to_fields(detector.BUILTIN_RULES["maa"])
        self.assertEqual(maa["win_class"], "^UnityWndClass$")
        self.assertIn("com.hypergryph.arknights", maa["adb_pkg"])

    def test_rules_from_fields_roundtrip(self):
        fields = {"win_class": "^UnityWndClass$", "win_title": "异环",
                  "detect_procs": "HTGame.exe, NTEGame.exe",
                  "adb_pkg": "com.x.y, com.z"}
        rules = detector.rules_from_fields(**fields)
        self.assertEqual([detector._rule_kind(rule) for rule in rules["any_of"]],
                         ["window", "proc", "adb"])
        self.assertEqual(detector.rules_to_fields(rules), fields)
        with_base = detector.rules_from_fields(
            **fields, base=detector.BUILTIN_RULES["nte"])
        self.assertEqual(with_base["launcher"],
                         detector.BUILTIN_RULES["nte"]["launcher"])
        self.assertIn("cloud", with_base)

    def test_rules_equal_ignores_source(self):
        self.assertTrue(detector.rules_equal(
            {"any_of": [], "source": "user"}, {"any_of": []}))
        self.assertFalse(detector.rules_equal(
            {"any_of": [{"type": "win", "class_re": "A"}]},
            {"any_of": [{"type": "win", "class_re": "B"}]}))


class DetectGameStateTests(unittest.TestCase):
    """detect_game_state / detect_game 的 running/reason 分支（mock 快照）。"""

    def test_unconfigured(self):
        state = detector.detect_game_state({"game": "__qa__"},
                                           windows=[], processes=set())
        self.assertFalse(state["running"])
        self.assertEqual(state["reason"], "")
        self.assertEqual(state["label"], "未配置")
        self.assertFalse(state["configured"])
        self.assertEqual(state["source"], "none")

    def test_window_running(self):
        rules = {"any_of": [{"type": "win", "class_re": "^UnityWndClass$",
                             "title_re": "明日方舟"}]}
        state = detector.detect_game_state(
            {"game_exe": "x"}, windows=[_win("UnityWndClass", "明日方舟",
                                             hwnd=77)],
            processes=set(), rules=rules)
        self.assertTrue(state["running"])
        self.assertEqual(state["reason"], "window")
        self.assertEqual(state["label"], "运行中（窗口）")
        self.assertEqual(state["hwnd"], 77)
        self.assertTrue(state["configured"])

    def test_proc_running(self):
        rules = {"any_of": [{"type": "proc", "names": ["HTGame.exe"]}]}
        state = detector.detect_game_state(
            {"game": "__qa__"}, windows=[], processes={"HTGAME.EXE"},
            rules=rules)
        self.assertTrue(state["running"])
        self.assertEqual(state["reason"], "proc")
        self.assertEqual(state["label"], "运行中（进程）")

    def test_launcher_reason_only(self):
        rules = {"any_of": [{"type": "win", "class_re": "NOMATCH"}],
                 "launcher": {"any_of": [
                     {"type": "proc", "names": ["NTELauncher.exe"]}]}}
        state = detector.detect_game_state(
            {"game": "__qa__"}, windows=[], processes={"NTELAUNCHER.EXE"},
            rules=rules)
        self.assertFalse(state["running"])
        self.assertEqual(state["reason"], "launcher")
        self.assertEqual(state["label"], "启动器已开")

    def test_cloud_reason_only(self):
        rules = {"any_of": [{"type": "win", "class_re": "NOMATCH"}],
                 "cloud": {"any_of": [
                     {"type": "win", "class_re": "^Qt.*$",
                      "title_re": r"^\s*云.*?异环\s*$"}]}}
        state = detector.detect_game_state(
            {"game": "__qa__"},
            windows=[_win("Qt5152QWindowIcon", "云·异环")],
            processes=set(), rules=rules)
        self.assertFalse(state["running"])
        self.assertEqual(state["reason"], "cloud")
        self.assertEqual(state["label"], "云游戏运行中")

    def test_not_running(self):
        rules = {"any_of": [{"type": "win", "class_re": "^UnityWndClass$"}]}
        state = detector.detect_game_state(
            {"game": "__qa__"}, windows=[], processes=set(), rules=rules)
        self.assertFalse(state["running"])
        self.assertEqual(state["reason"], "")
        self.assertEqual(state["label"], "未运行")
        self.assertTrue(state["configured"])

    def test_adb_running_when_enabled(self):
        rules = {"any_of": [{
            "type": "adb", "pkg": ["com.hypergryph.arknights"],
            "activity": "com.u8.sdk.U8UnityContext", "serial_re": ".*"}]}
        devices = [{"serial": "emulator-5554",
                    "focus": "com.hypergryph.arknights/com.u8.sdk.U8UnityContext"}]
        with mock.patch.object(detector, "adb_snapshot",
                               return_value=devices) as snap:
            state = detector.detect_game_state(
                {"game": "__qa__"}, windows=[], processes=set(),
                adb_enabled=True, rules=rules)
        self.assertTrue(state["running"])
        self.assertEqual(state["reason"], "adb")
        self.assertEqual(state["label"], "运行中（ADB）")
        snap.assert_called_once()

    def test_adb_disabled_skips_snapshot(self):
        rules = {"any_of": [{"type": "adb",
                             "pkg": ["com.hypergryph.arknights"]}]}
        with mock.patch.object(detector, "adb_snapshot",
                               return_value=[]) as snap:
            state = detector.detect_game_state(
                {"game": "__qa__"}, windows=[], processes=set(),
                adb_enabled=False, rules=rules)
        self.assertFalse(state["running"])
        snap.assert_not_called()

    def test_proc_class_check(self):
        rules = {"any_of": [], "proc_class_check": [
            {"name": "HTGame.exe", "win_class_re": "UnrealWindow"}]}
        with mock.patch.object(detector, "_pid_path",
                               return_value=r"D:\Game\HTGame.exe"):
            state = detector.detect_game_state(
                {"game": "__qa__"},
                windows=[_win("UnrealWindow", "anything", pid=42)],
                processes=set(), rules=rules)
        self.assertTrue(state["running"])
        self.assertEqual(state["reason"], "window")
        self.assertTrue(state["configured"])

    def test_detect_game_compat_tuple(self):
        app = {"game": "__qa__", "detect": {
            "any_of": [{"type": "proc", "names": ["HTGame.exe"]}]}}
        self.assertEqual(detector.detect_game(
            app, windows=[], processes={"HTGAME.EXE"}), (True, "proc"))
        self.assertEqual(detector.detect_game(
            app, windows=[], processes=set()), (False, ""))

    def test_configured_by_game_exe_only(self):
        app = {"key": "custom_qa_3", "game": "__qa_custom_game__",
               "game_exe": r"D:\Game\x.exe"}
        state = detector.detect_game_state(app, windows=[], processes=set())
        self.assertTrue(state["configured"])
        self.assertEqual(state["label"], "未运行")


class DetectorSnapshotSmokeTests(unittest.TestCase):
    """真实窗口/进程快照 smoke：只断言类型/字段，不依赖具体游戏是否运行。"""

    def setUp(self):
        _clear_detector_caches()
        self.addCleanup(_clear_detector_caches)

    def test_snapshot_windows_contract(self):
        windows = detector.snapshot_windows(force=True)
        self.assertIsInstance(windows, list)
        self.assertLessEqual(len(windows), detector.MAX_WINDOWS)
        for win in windows:
            self.assertEqual(set(win), {"hwnd", "class_name", "title", "width",
                                        "height", "pid", "iconic", "visible"})
            self.assertIsInstance(win["hwnd"], int)
            self.assertIsInstance(win["class_name"], str)
            self.assertIsInstance(win["title"], str)
            self.assertIsInstance(win["pid"], int)
            self.assertGreaterEqual(win["width"], 0)
            self.assertGreaterEqual(win["height"], 0)
            self.assertIsInstance(win["iconic"], bool)
            self.assertIsInstance(win["visible"], bool)

    def test_snapshot_window_cache_ttl(self):
        first = detector.snapshot_windows(force=True)
        second = detector.snapshot_windows()
        self.assertIs(second, first, "TTL 内应复用同一份窗口快照")

    def test_process_path_self(self):
        path = detector.process_path(os.getpid())
        self.assertIsInstance(path, str)
        if path:
            self.assertTrue(path.lower().endswith(".exe"))
            self.assertTrue(os.path.isfile(path))

    def test_real_detect_state_contract(self):
        state = detector.detect_game_state({"key": "maa", "game": "明日方舟"})
        for field in ("running", "reason", "label", "hwnd", "source",
                      "configured", "adb_enabled", "rules"):
            self.assertIn(field, state)
        self.assertIsInstance(state["running"], bool)
        self.assertIn(state["reason"], {"", "window", "proc", "adb",
                                        "launcher", "cloud"})
        self.assertIsInstance(state["label"], str)
        self.assertTrue(state["label"])
        self.assertEqual(state["source"], "auto")
        self.assertTrue(state["configured"])
        running, reason = detector.detect_game({"key": "maa", "game": "明日方舟"})
        self.assertIsInstance(running, bool)
        self.assertIsInstance(reason, str)


# ---------------------------------------------------------------- v0.7 启动规格
def _touch(path, content=b"stub"):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(content)
    return path


def _write_json(path, data, encoding="utf-8"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding=encoding) as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    return path


def _append_text(path, text):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(text)


def _make_okww_install(tmp_dir, with_script=True, with_app_json=True):
    """临时目录拼 ok-ww 安装布局；返回 (app, paths)。"""
    root = os.path.join(tmp_dir, "WuwaMAA", "ok-ww")
    launcher = _touch(os.path.join(root, "ok-ww.exe"))
    app_dir = os.path.join(root, "data", "apps", "ok-ww")
    pythonw = _touch(os.path.join(app_dir, "python", "pythonw.exe"))
    working = os.path.join(app_dir, "working")
    os.makedirs(working, exist_ok=True)
    script = os.path.join(working, "main.py")
    if with_script:
        _touch(script, b"print('stub')\n")
    if with_app_json:
        _write_json(os.path.join(app_dir, "app.json"),
                    {"current_version": "v9.9.9", "current_profile": "China"})
    app = {"key": "wuwa", "game": "鸣潮", "script_exe": launcher,
           "script_procs": ["OK-WW.EXE"]}
    return app, {"launcher": launcher, "pythonw": pythonw,
                 "working": working, "script": script, "app_dir": app_dir}


class LaunchSpecTests(TempDirTest):
    """v0.7 启动规格：birded pythonw + working\\main.py / 环境清理 / 回退 / 进程判定。"""

    def test_build_okww_launch_full(self):
        app, paths = _make_okww_install(self.tmp)
        spec = store.build_okww_launch(app)
        self.assertEqual(spec["type"], "python")
        self.assertEqual(os.path.normpath(spec["exe"]),
                         os.path.normpath(paths["pythonw"]))
        self.assertEqual(os.path.normpath(spec["script"]),
                         os.path.normpath(paths["script"]))
        self.assertEqual(os.path.normpath(spec["cwd"]),
                         os.path.normpath(paths["working"]))
        self.assertEqual(os.path.normpath(spec["launcher_exe"]),
                         os.path.normpath(paths["launcher"]))
        self.assertEqual(spec["fallback"], "launcher")
        self.assertEqual(spec["process_exe_names"],
                         ["pythonw.exe", "python.exe"])
        self.assertEqual(spec["process_exe_dirs"],
                         [os.path.dirname(paths["pythonw"])])
        for key, value in store.LAUNCH_ENV_SET.items():
            self.assertEqual(spec["env"].get(key), value)
        self.assertEqual(spec["env"].get("PYAPPIFY_APP_VERSION"), "v9.9.9")
        self.assertEqual(spec["env"].get("PYAPPIFY_APP_PROFILE"), "China")
        self.assertEqual(spec["env"].get("PYAPPIFY_EXECUTABLE"),
                         paths["launcher"])
        self.assertIn("PYAPPIFY_APP_JSON_PATH", spec["env"])
        for name in ("PYTHONHOME", "PYTHONPATH", "PYAPPIFY_PID"):
            self.assertIn(name, spec["clear_env"])

    def test_build_okww_launch_missing_layout(self):
        app, paths = _make_okww_install(self.tmp, with_script=False,
                                        with_app_json=False)
        spec = store.build_okww_launch(app)
        self.assertIsNotNone(spec)
        self.assertEqual(os.path.normpath(spec["exe"]),
                         os.path.normpath(paths["pythonw"]))
        self.assertNotIn("PYAPPIFY_APP_VERSION", spec["env"])
        self.assertNotIn("PYAPPIFY_APP_JSON_PATH", spec["env"])
        self.assertFalse(store.build_okww_launch({"script_exe": ""}))

    def test_launch_env_cleans_and_injects(self):
        app, _paths = _make_okww_install(self.tmp)
        spec = store.build_okww_launch(app)
        with mock.patch.dict(os.environ, {
                "PYTHONHOME": r"C:\bad\python", "PYTHONPATH": r"C:\bad\path",
                "PYAPPIFY_PID": "123", "QA_KEEP_ME": "yes"}, clear=False):
            env = store._launch_env(spec)
        self.assertNotIn("PYTHONHOME", env)
        self.assertNotIn("PYTHONPATH", env)
        self.assertNotIn("PYAPPIFY_PID", env)
        self.assertEqual(env.get("QA_KEEP_ME"), "yes")
        self.assertEqual(env.get("PATH"), store._wrapper_path())
        for key, value in store.LAUNCH_ENV_SET.items():
            self.assertEqual(env.get(key), value)

    def test_launch_app_runs_bundled_python(self):
        app, paths = _make_okww_install(self.tmp)
        spec = dict(store.build_okww_launch(app))
        spec["args"] = ["--extra"]
        app["launch"] = spec
        with mock.patch.object(store.subprocess, "Popen") as popen:
            ok, error, mode = store.launch_app(app)
        self.assertEqual((ok, mode), (True, "script"))
        self.assertEqual(error, "")
        command = popen.call_args.args[0]
        self.assertEqual([os.path.normpath(item) for item in command], [
            os.path.normpath(paths["pythonw"]),
            os.path.normpath(paths["script"]), "--extra"])
        kwargs = popen.call_args.kwargs
        self.assertEqual(os.path.normpath(kwargs["cwd"]),
                         os.path.normpath(paths["working"]))
        env = kwargs.get("env") or {}
        self.assertEqual(env.get("PYTHONNOUSERSITE"), "1")
        self.assertNotIn("PYTHONHOME", env)

    def test_launch_app_falls_back_to_launcher(self):
        app, paths = _make_okww_install(self.tmp, with_script=False)
        app["launch"] = store.build_okww_launch(app)
        launched = []
        with mock.patch.object(store, "launch_exe",
                               side_effect=lambda exe: (launched.append(exe),
                                                        (True, ""))[1]) as fake:
            ok, error, mode = store.launch_app(app)
        self.assertEqual((ok, error, mode), (True, "", "launcher"))
        self.assertEqual([os.path.normpath(item) for item in launched],
                         [os.path.normpath(paths["launcher"])])
        # 回退也失败时返回回退错误
        with mock.patch.object(store, "launch_exe",
                               return_value=(False, "回退失败")):
            ok2, error2, mode2 = store.launch_app(app)
        self.assertEqual((ok2, error2, mode2), (False, "回退失败", "launcher"))

    def test_launch_app_no_fallback(self):
        app, _paths = _make_okww_install(self.tmp, with_script=False)
        spec = dict(store.build_okww_launch(app))
        spec["fallback"] = "none"
        app["launch"] = spec
        with mock.patch.object(store, "launch_exe") as fake:
            ok, error, mode = store.launch_app(app)
        self.assertFalse(ok)
        self.assertEqual(mode, "none")
        self.assertTrue(error)
        fake.assert_not_called()

    def test_launch_app_plain_exe(self):
        app = {"key": "maa", "script_exe": _touch(os.path.join(self.tmp, "MAA",
                                                               "MAA.exe"))}
        with mock.patch.object(store, "launch_exe",
                               return_value=(True, "")) as fake:
            ok, error, mode = store.launch_app(app)
        self.assertEqual((ok, error, mode), (True, "", "exe"))
        fake.assert_called_once_with(app["script_exe"])

    def test_launch_running_pids_path_based(self):
        app, paths = _make_okww_install(self.tmp)
        app["launch"] = store.build_okww_launch(app)
        pythonw = paths["pythonw"]
        user_python = os.path.join(self.tmp, "Python313", "pythonw.exe")
        _touch(user_python)
        launcher = paths["launcher"]
        with mock.patch.object(store, "pids_for_procs",
                               return_value={111, 222, 333}) as fake, \
                mock.patch.object(store, "process_path",
                                  side_effect={111: pythonw, 222: user_python,
                                               333: launcher}.get):
            pids = store.launch_running_pids(app)
            running = store.launch_spec_running(app)
        self.assertEqual(pids, {111}, "只认 ok-ww pythonw 目录内的进程")
        self.assertTrue(running)
        self.assertIn("PYTHONW.EXE", fake.call_args.args[0])
        # 路径读不到 -> 不判定运行（避免误判用户其它 python）
        with mock.patch.object(store, "pids_for_procs", return_value={333}), \
                mock.patch.object(store, "process_path", return_value=""):
            self.assertEqual(store.launch_running_pids(app), set())
            self.assertFalse(store.launch_spec_running(app))
        self.assertEqual(store.launch_running_pids({}), set())

    def test_launch_updater_uses_launcher(self):
        app, paths = _make_okww_install(self.tmp)
        app["launch"] = store.build_okww_launch(app)
        with mock.patch.object(store, "launch_exe",
                               return_value=(True, "")) as fake:
            ok, error = store.launch_updater(app)
        self.assertEqual((ok, error), (True, ""))
        fake.assert_called_once_with(paths["launcher"])

    def test_launch_spec_persistence_and_legacy_fill(self):
        app, paths = _make_okww_install(self.tmp)
        app["launch"] = store.build_okww_launch(app)
        app["builtin"] = True
        cfg = os.path.join(self.tmp, "config.json")
        search_root = os.path.join(self.tmp, "search_root")
        os.makedirs(search_root, exist_ok=True)
        with mock.patch.object(store, "CONFIG", cfg), \
                mock.patch.object(store, "SEARCH_ROOT", search_root):
            self.assertTrue(store.save_state([app], clash="", root=self.tmp,
                                             daily_order=["wuwa"]))
            raw = json.load(open(cfg, "r", encoding="utf-8"))
            self.assertEqual(raw.get("version"), 4)
            saved = raw["apps"]["wuwa"]["launch"]
            self.assertFalse(os.path.isabs(saved["exe"]))
            self.assertIn("/", saved["exe"])
            apps, _clash, _root, meta = store.load_state_full()
            got = next(item for item in apps
                       if item["key"] == "wuwa")["launch"]
            self.assertEqual(os.path.normpath(got["exe"]),
                             os.path.normpath(paths["pythonw"]))
            self.assertEqual(os.path.normpath(got["script"]),
                             os.path.normpath(paths["script"]))
            self.assertEqual(os.path.normpath(got["cwd"]),
                             os.path.normpath(paths["working"]))
            self.assertEqual(meta["daily_order"][0], "wuwa")
            self.assertEqual(sorted(meta["daily_order"]),
                             sorted(store.DEFAULT_DAILY_ORDER))
            # 旧配置没有 launch 字段 -> 内置鸣潮自动补齐
            for item in raw["apps"].values():
                item.pop("launch", None)
            raw["version"] = 3
            _write_json(cfg, raw)
            apps2, _c, _r, _m = store.load_state_full()
            got2 = next(item for item in apps2
                        if item["key"] == "wuwa")["launch"]
            self.assertEqual(os.path.normpath(got2["exe"]),
                             os.path.normpath(paths["pythonw"]))

    def test_clean_launch_and_refresh(self):
        app, paths = _make_okww_install(self.tmp)
        spec = store._clean_launch({
            "type": "python", "exe": "a/pythonw.exe", "script": "b/main.py",
            "cwd": "b", "process_exe_dirs": ["a"],
            "env": {"QA": 1, "BOOL": True}, "clear_env": "PYTHONHOME",
            "fallback": "launcher"}, root=self.tmp)
        self.assertTrue(spec["exe"].startswith(self.tmp))
        self.assertEqual(spec["env"], {"QA": "1"})
        self.assertEqual(spec["clear_env"], ["PYTHONHOME"])
        self.assertIsNone(store._clean_launch({}, root=self.tmp))
        self.assertIsNone(store._clean_launch(
            {"type": "python", "exe": "x.exe"}, root=self.tmp))
        self.assertTrue(store.refresh_launch_spec(app))
        self.assertEqual(os.path.normpath(app["launch"]["exe"]),
                         os.path.normpath(paths["pythonw"]))
        self.assertFalse(store.refresh_launch_spec({"key": "custom"}))


# ---------------------------------------------------------------- v0.7 清日常夹具
def _make_okww_daily(tmp_dir, settings=None):
    app, paths = _make_okww_install(tmp_dir)
    _touch(os.path.join(paths["working"], "configs", "DailyTask.json"), b"{}")
    log = _touch(os.path.join(paths["working"], "logs", "ok-script.log"), b"")
    app["launch"] = store.build_okww_launch(app)
    app["daily"] = store._clean_daily(settings or {}, "wuwa")
    return app, log


def _make_mxu_daily(tmp_dir, key="nte", instances=None):
    script = "MaaNTE" if key == "nte" else "MaaEnd"
    exe = _touch(os.path.join(tmp_dir, script, f"{script}.exe"))
    if key == "nte" and instances is None:
        # v0.10.4：异环与终末地同用 MXU --autostart（不再热键/UI）
        instances = [{"name": "挂机任务", "tasks": [
            {"taskName": "FishNew", "enabled": True},
            {"taskName": "DailyTask", "enabled": False}]}]
        config = {"instances": instances}
    elif instances is None:
        config = {"instances": [
            {"name": "全套日常", "tasks": [
                {"taskName": "__MXU_PRETASK__LaunchGamePC",
                 "enabled": True},
                {"taskName": "DailyTask", "enabled": True}]},
            {"name": "快速日常", "tasks": [
                {"taskName": "DailyTask", "enabled": True}]}]}
    else:
        config = {"instances": instances}
    _write_json(os.path.join(tmp_dir, script, "config",
                             f"mxu-{script}.json"), config)
    _touch(os.path.join(tmp_dir, script, "debug", "mxu-tauri.log"), b"")
    return {"key": key,
            "game": "异环" if key == "nte" else "明日方舟终末地",
            "script": script, "script_exe": exe,
            "daily": store._clean_daily({}, key)}


def _make_maa_daily(tmp_dir, hotkey=True, tasks=("开始唤醒", "自动公招"),
                    config_name="Default"):
    exe = _touch(os.path.join(tmp_dir, "MAA", "MAA.exe"))
    gui = {"Current": config_name, "Gui": {"HotKeys": {}},
           "Configurations": {config_name: {"TaskQueue": [
               {"Name": name, "TaskType": name, "IsEnable": True}
               for name in tasks]}}}
    if hotkey:
        gui["Gui"]["HotKeys"]["LinkStart"] = {
            "Key": "L", "Modifiers": "Alt, Control, Shift"}
    _write_json(os.path.join(tmp_dir, "MAA", "config", "gui.new.json"), gui)
    log = _touch(os.path.join(tmp_dir, "MAA", "debug", "gui.log"), b"")
    app = {"key": "maa", "game": "明日方舟", "script": "MAA",
           "script_exe": exe, "daily": store._clean_daily({}, "maa")}
    return app, log, gui


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.t += max(0.0, float(seconds))


class FakeHandle:
    def __init__(self, clock, exit_calls=None):
        self.pid = 4321
        self.clock = clock
        self.calls = 0
        self.exit_calls = exit_calls
        self.on_wait = None
        self.terminated = False
        self.closed = False

    def alive(self):
        return not self.terminated and not self._exited()

    def _exited(self):
        return bool(self.exit_calls and self.calls >= self.exit_calls)

    def wait(self, timeout_ms=500):
        self.calls += 1
        if self.on_wait:
            self.on_wait(self)
        self.clock.sleep(0.4)
        return self.terminated or self._exited()

    def terminate(self):
        self.terminated = True
        return True

    def close(self):
        self.closed = True


class DailyPlanTests(TempDirTest):
    """dry-run 命令拼装：ok-ww / MAA / MXU(MaaNTE/MaaEnd)。"""

    def _apps(self):
        wuwa, _log = _make_okww_daily(self.tmp)
        maa, _mlog, _gui = _make_maa_daily(self.tmp)
        nte = _make_mxu_daily(self.tmp, "nte")
        maaend = _make_mxu_daily(self.tmp, "maaend")
        return [wuwa, maa, nte, maaend]

    def _patches(self, game_running=True, script_running=False):
        return (
            mock.patch.object(daily, "_script_running",
                              return_value=script_running),
            mock.patch.object(daily, "_game_running",
                              return_value=game_running),
            mock.patch.object(store, "snapshot_processes",
                              return_value=set()))

    def test_dry_run_four_commands(self):
        apps = self._apps()
        p1, p2, p3 = self._patches()
        with p1, p2, p3, mock.patch.object(
                daily, "launch_elevated",
                side_effect=AssertionError("dry-run 不应启动进程")):
            plans = daily.dry_run(apps)
        by_key = {plan["key"]: plan for plan in plans}
        self.assertEqual([plan["key"] for plan in plans],
                         store.DEFAULT_DAILY_ORDER)
        self.assertTrue(all(plan["ok"] for plan in plans),
                        [(p["key"], p["errors"]) for p in plans])
        wuwa = by_key["wuwa"]
        self.assertEqual(wuwa["mode"], "okww")
        self.assertIn("main.py", wuwa["params"])
        self.assertIn("-t DailyTask", wuwa["params"])
        self.assertTrue(wuwa["params"].rstrip().endswith("-e"))
        self.assertEqual(os.path.basename(wuwa["cwd"]), "working")
        self.assertEqual(wuwa["timeout_min"], 90)
        maa = by_key["maa"]
        self.assertEqual(maa["mode"], "maa")
        self.assertIn("--skip-startup-auto-run", maa["params"])
        self.assertEqual(maa["hotkey"]["text"], "Alt, Control, Shift + L")
        self.assertEqual(maa["enabled_tasks"], ["开始唤醒", "自动公招"])
        nte = by_key["nte"]
        self.assertEqual(nte["mode"], "mxu")
        self.assertIn("MaaNTE.exe", nte["command_text"])
        self.assertIn('--instance "挂机任务"', nte["params"])
        self.assertIn("--quit-after-run", nte["params"])
        self.assertEqual(nte["errors"], [])
        maaend = by_key["maaend"]
        self.assertIn('--instance "全套日常"', maaend["params"])
        text = daily.describe_plan(wuwa)
        self.assertIn("命令:", text)
        self.assertIn("超时:", text)

    def test_okww_plan_task_extra_args_timeout(self):
        app, _log = _make_okww_daily(self.tmp, {
            "task": "DailyTask", "extra_args": ["--debug"], "timeout_min": 30})
        p1, p2, p3 = self._patches()
        with p1, p2, p3:
            plan = daily.plan_for(app)
        self.assertTrue(plan["params"].endswith("-e --debug"))
        self.assertEqual(plan["timeout_min"], 30)
        self.assertTrue(plan["close_after"])

    def test_maa_plan_config_args_and_hotkey(self):
        app, _log, _gui = _make_maa_daily(self.tmp)
        app["daily"] = store._clean_daily(
            {"config": "Default", "extra_args": ["--foo"], "timeout_min": 45},
            "maa")
        p1, p2, p3 = self._patches()
        with p1, p2, p3:
            plan = daily.plan_for(app)
        self.assertEqual(plan["params"],
                         '--skip-startup-auto-run --config "Default" --foo')
        self.assertEqual(plan["hotkey"]["text"], "Alt, Control, Shift + L")
        self.assertEqual(plan["timeout_min"], 45)
        self.assertFalse(plan["close_after"])

    def test_mxu_plan_instance_auto_and_override(self):
        nte = _make_mxu_daily(self.tmp, "nte")
        maaend = _make_mxu_daily(self.tmp, "maaend")
        p1, p2, p3 = self._patches()
        with p1, p2, p3:
            nte_plan = daily.plan_for(nte)
            maaend_plan = daily.plan_for(maaend)
            override = dict(maaend)
            override["daily"] = store._clean_daily(
                {"instance": "快速日常"}, "maaend")
            override_plan = daily.plan_for(override)
        # 异环/终末地共用 MXU --autostart --instance ... --quit-after-run
        self.assertEqual(nte_plan["mode"], "mxu")
        self.assertIn('--instance "挂机任务"', nte_plan["params"])
        self.assertIn("--autostart", nte_plan["params"])
        self.assertTrue(nte_plan["params"].endswith("--quit-after-run"))
        self.assertIn('--instance "全套日常"', maaend_plan["params"])
        self.assertIn('--instance "快速日常"', override_plan["params"])
        self.assertIn("--autostart", override_plan["params"])
        self.assertTrue(override_plan["params"].endswith("--quit-after-run"))

    def test_nte_and_maaend_command_shape_consistent(self):
        """异环与终末地命令形状一致：--autostart/--instance/--quit-after-run。"""
        nte = _make_mxu_daily(self.tmp, "nte")
        maaend = _make_mxu_daily(self.tmp, "maaend")
        p1, p2, p3 = self._patches()
        with p1, p2, p3:
            nte_plan = daily.plan_for(nte)
            maaend_plan = daily.plan_for(maaend)
        for plan in (nte_plan, maaend_plan):
            self.assertEqual(plan["mode"], "mxu")
            self.assertEqual(plan["args"][:1], ["--autostart"])
            self.assertEqual(plan["args"][-1], "--quit-after-run")
            self.assertIn("--instance", plan["args"])
            self.assertEqual(plan["argv"][1:4],
                             ["--autostart", "--instance",
                              plan["settings"]["instance"]])
        self.assertEqual(nte_plan["timeout_min"], 120)
        self.assertEqual(maaend_plan["timeout_min"], 150)

    def test_plan_settings_override(self):
        app, _log, _gui = _make_maa_daily(self.tmp)
        p1, p2, p3 = self._patches()
        with p1, p2, p3:
            plan = daily.plan_for(app, {"timeout_min": 5, "enabled": False})
        self.assertEqual(plan["timeout_min"], 5)
        self.assertFalse(plan["settings"]["enabled"])

    def test_plan_unsupported_and_describe_errors(self):
        plan = daily.plan_for({"key": "custom_qa", "game": "自定义"})
        self.assertFalse(plan["ok"])
        self.assertTrue(any("不支持" in error for error in plan["errors"]))
        app, _log, _gui = _make_maa_daily(self.tmp, hotkey=False)
        p1, p2, p3 = self._patches()
        with p1, p2, p3:
            bad = daily.plan_for(app)
        self.assertFalse(bad["ok"])
        text = daily.describe_plan(bad)
        self.assertIn("✗", text)
        self.assertIn("热键", text)


class DailyPreconditionTests(TempDirTest):
    """前置检查：缺布局/缺热键/无任务/实例问题/游戏未运行/脚本已运行。"""

    def _patch(self, game_running=True, script_running=False):
        return (
            mock.patch.object(daily, "_script_running",
                              return_value=script_running),
            mock.patch.object(daily, "_game_running",
                              return_value=game_running),
            mock.patch.object(store, "snapshot_processes",
                              return_value=set()))

    def test_okww_missing_layout_and_daily_config(self):
        app = {"key": "wuwa", "game": "鸣潮",
               "script_exe": os.path.join(self.tmp, "nope", "ok-ww.exe")}
        p1, p2, p3 = self._patch()
        with p1, p2, p3:
            plan = daily.plan_for(app)
        joined = " ".join(plan["errors"])
        self.assertIn("pythonw.exe", joined)
        self.assertIn("main.py", joined)
        # DailyTask.json 缺失只是警告
        app2, _log = _make_okww_daily(self.tmp)
        os.remove(os.path.join(daily.okww_paths(app2)["daily_config"]))
        with p1, p2, p3:
            plan2 = daily.plan_for(app2)
        self.assertTrue(any("DailyTask.json" in w for w in plan2["warnings"]))
        self.assertTrue(plan2["ok"])

    def test_script_already_running(self):
        app, _log = _make_okww_daily(self.tmp)
        p1, p2, p3 = self._patch(script_running=True)
        with p1, p2, p3:
            plan = daily.plan_for(app)
        self.assertTrue(any("已在运行" in error for error in plan["errors"]))
        # 异环 v0.10.4 与终末地一致：脚本已运行 -> 报错，不 attach
        nte = _make_mxu_daily(self.tmp, "nte")
        with p1, p2, p3:
            plan2 = daily.plan_for(nte)
        self.assertTrue(any("已在运行" in error
                            for error in plan2["errors"]))
        self.assertFalse(plan2.get("attach"))

    def test_maa_missing_hotkey_and_empty_tasks(self):
        app, _log, _gui = _make_maa_daily(self.tmp, hotkey=False, tasks=())
        p1, p2, p3 = self._patch()
        with p1, p2, p3:
            plan = daily.plan_for(app)
        joined = " ".join(plan["errors"])
        self.assertIn("热键", joined)
        self.assertIn("任务队列", joined)

    def test_maa_attach_when_running(self):
        app, _log, _gui = _make_maa_daily(self.tmp)
        p1, p2, p3 = self._patch(script_running=True)
        with p1, p2, p3:
            plan = daily.plan_for(app)
        self.assertTrue(plan["ok"])
        self.assertTrue(plan.get("attach"))
        self.assertTrue(any("已在运行" in note for note in plan["notes"]))

    def test_mxu_missing_config_bad_instance_and_zero_tasks(self):
        # 异环与终末地同一条 MXU 路径：缺配置/实例不存在/0 启用任务均报错
        for key in ("nte", "maaend"):
            missing = _make_mxu_daily(self.tmp, key)
            os.remove(daily.mxu_paths(missing)["config"])
            p1, p2, p3 = self._patch()
            with p1, p2, p3:
                plan_missing = daily.plan_for(missing)
            self.assertTrue(any("MXU 实例配置" in error
                                for error in plan_missing["errors"]))

            app = _make_mxu_daily(self.tmp, key)
            app["daily"] = store._clean_daily({"instance": "不存在"}, key)
            p1, p2, p3 = self._patch()
            with p1, p2, p3:
                plan2 = daily.plan_for(app)
            joined = " ".join(plan2["errors"])
            self.assertIn("不存在", joined)

            zero = _make_mxu_daily(
                os.path.join(self.tmp, "zero_" + key), key,
                instances=[{"name": "全套日常", "tasks": [
                    {"taskName": "DailyTask", "enabled": False}]}])
            zero["daily"] = store._clean_daily({"instance": "全套日常"}, key)
            p1, p2, p3 = self._patch()
            with p1, p2, p3:
                plan3 = daily.plan_for(zero)
            self.assertTrue(any("没有启用任何任务" in error
                                for error in plan3["errors"]))

    def test_nte_requires_game_or_launch_pretask(self):
        nte = _make_mxu_daily(self.tmp, "nte")
        p1, p2, p3 = self._patch(game_running=False)
        with p1, p2, p3:
            plan = daily.plan_for(nte)
        self.assertEqual(plan["mode"], "mxu")
        self.assertTrue(any("异环游戏未运行" in error
                            for error in plan["errors"]))
        # 实例带 LaunchGamePC 且游戏未运行 -> 不报游戏错误
        launch = _make_mxu_daily(
            os.path.join(self.tmp, "launch"), "nte",
            instances=[{"name": "挂机任务", "tasks": [
                {"taskName": "__MXU_PRETASK__LaunchGamePC", "enabled": True},
                {"taskName": "DailyTask", "enabled": True}]}])
        p1, p2, p3 = self._patch(game_running=False)
        with p1, p2, p3:
            plan2 = daily.plan_for(launch)
        self.assertFalse(any("异环游戏未运行" in error
                             for error in plan2["errors"]))
        self.assertIn("--quit-after-run", plan2["params"])


class DailyStateMachineTests(TempDirTest):
    """单游戏状态机：finished / failed / timeout / stopped / attach。"""

    def _run(self, app, clock, handle, log_path, stop_event=None, marker=None):
        def launcher(exe, params, cwd):
            _touch(log_path)
            return handle
        handle.on_wait = marker
        with mock.patch.object(daily, "_now", clock.now), \
                mock.patch.object(daily, "_sleep", clock.sleep), \
                mock.patch.object(store, "snapshot_processes",
                                  return_value=set()), \
                mock.patch.object(daily, "_script_running",
                                  return_value=False), \
                mock.patch.object(daily, "_game_running",
                                  return_value=True):
            return daily.run(app, stop_event=stop_event, launcher=launcher)

    def test_okww_finished_and_failed(self):
        app, log = _make_okww_daily(self.tmp)
        clock, handle = FakeClock(), FakeHandle(FakeClock(), exit_calls=2)
        handle.clock = clock

        def marker(h):
            if h.calls == 1:
                _append_text(log, daily.OKWW_SUCCESS_MARKER + "\n")
        result = self._run(app, clock, handle, log, marker=marker)
        self.assertEqual(result["state"], daily.FINISHED)
        self.assertEqual(result["state_label"], "已完成")
        self.assertEqual(result["pid"], 4321)
        self.assertIn("Successfully Executed", result["log_tail"])

        app2, log2 = _make_okww_daily(os.path.join(self.tmp, "fail"))
        clock2 = FakeClock()
        result2 = self._run(app2, clock2, FakeHandle(clock2, exit_calls=1), log2)
        self.assertEqual(result2["state"], daily.FAILED)
        self.assertIn("未出现成功标记", result2["reason"])

    def test_okww_timeout_and_stopped(self):
        app, log = _make_okww_daily(self.tmp, {"timeout_min": 1})
        clock = FakeClock()
        handle = FakeHandle(clock, exit_calls=None)
        result = self._run(app, clock, handle, log)
        self.assertEqual(result["state"], daily.TIMEOUT)
        self.assertTrue(handle.terminated)
        self.assertTrue(handle.closed)

        app2, log2 = _make_okww_daily(os.path.join(self.tmp, "stop"))
        stop_event = threading.Event()
        clock2 = FakeClock()
        handle2 = FakeHandle(clock2, exit_calls=None)

        def marker2(h):
            if h.calls == 1:
                stop_event.set()
        result2 = self._run(app2, clock2, handle2, log2,
                            stop_event=stop_event, marker=marker2)
        self.assertEqual(result2["state"], daily.STOPPED)
        self.assertTrue(handle2.terminated)

    def test_mxu_finished_and_timeout(self):
        # 异环/终末地同走 --autostart MXU：进程退出 finished / 超时 timeout
        for key in ("nte", "maaend"):
            app = _make_mxu_daily(self.tmp, key)
            clock = FakeClock()
            result = self._run(app, clock,
                               FakeHandle(clock, exit_calls=1),
                               os.path.join(self.tmp, key + ".log"))
            self.assertEqual(result["state"], daily.FINISHED)
            self.assertIn("MXU 进程已退出", result["reason"])

            app2 = _make_mxu_daily(os.path.join(self.tmp, "mxu2_" + key),
                                   key)
            app2["daily"] = store._clean_daily({"timeout_min": 1}, key)
            clock2 = FakeClock()
            handle2 = FakeHandle(clock2, exit_calls=None)
            result2 = self._run(app2, clock2, handle2,
                                os.path.join(self.tmp, "mxu2_" + key + ".log"))
            self.assertEqual(result2["state"], daily.TIMEOUT)
            self.assertTrue(handle2.terminated)

    def test_maa_success_failure_attach(self):
        maa, maa_log, _gui = _make_maa_daily(self.tmp)
        clock = FakeClock()
        handle = FakeHandle(clock, exit_calls=None)
        hotkeys = []

        def launcher(exe, params, cwd):
            _touch(maa_log)
            return handle

        def send_ok(hotkey):
            hotkeys.append(hotkey)
            _append_text(maa_log, "任务已全部完成！\n")
            return True

        with mock.patch.object(daily, "_now", clock.now), \
                mock.patch.object(daily, "_sleep", clock.sleep), \
                mock.patch.object(daily, "send_hotkey", side_effect=send_ok), \
                mock.patch.object(daily, "_maa_window_ready",
                                  return_value=True), \
                mock.patch.object(daily, "_script_running",
                                  return_value=False), \
                mock.patch.object(store, "snapshot_processes",
                                  return_value=set()):
            result = daily.run(maa, launcher=launcher)
        self.assertEqual(result["state"], daily.FINISHED)
        self.assertEqual(len(hotkeys), 1)
        self.assertTrue(handle.closed)

        maa2, maa_log2, _gui2 = _make_maa_daily(os.path.join(self.tmp, "maa2"))
        clock2 = FakeClock()
        handle2 = FakeHandle(clock2, exit_calls=None)

        def send_fail(hotkey):
            _append_text(maa_log2, "任务出错: 开始唤醒\n")
            return True

        def launcher2(exe, params, cwd):
            _touch(maa_log2)
            return handle2
        with mock.patch.object(daily, "_now", clock2.now), \
                mock.patch.object(daily, "_sleep", clock2.sleep), \
                mock.patch.object(daily, "send_hotkey", side_effect=send_fail), \
                mock.patch.object(daily, "_maa_window_ready",
                                  return_value=True), \
                mock.patch.object(daily, "_script_running",
                                  return_value=False), \
                mock.patch.object(store, "snapshot_processes",
                                  return_value=set()):
            result2 = daily.run(maa2, launcher=launcher2)
        self.assertEqual(result2["state"], daily.FAILED)
        self.assertIn("任务出错", result2["reason"])

        # MAA 已在运行：attach 模式只发热键、不启动
        maa3, maa_log3, _gui3 = _make_maa_daily(os.path.join(self.tmp, "maa3"))
        clock3 = FakeClock()
        hotkeys3 = []

        def send_ok3(hotkey):
            hotkeys3.append(hotkey)
            _append_text(maa_log3, "任务已全部完成！\n")
            return True

        def fail_launcher(exe, params, cwd):
            raise AssertionError("attach 模式不应启动 MAA")
        with mock.patch.object(daily, "_now", clock3.now), \
                mock.patch.object(daily, "_sleep", clock3.sleep), \
                mock.patch.object(daily, "send_hotkey", side_effect=send_ok3), \
                mock.patch.object(daily, "_script_running",
                                  return_value=True), \
                mock.patch.object(store, "snapshot_processes",
                                  return_value={"MAA.EXE"}):
            result3 = daily.run(maa3, launcher=fail_launcher)
        self.assertEqual(result3["state"], daily.FINISHED)
        self.assertEqual(len(hotkeys3), 1)

    def test_maa_hotkey_failure_and_not_ready(self):
        maa, maa_log, _gui = _make_maa_daily(self.tmp)
        clock = FakeClock()
        handle = FakeHandle(clock, exit_calls=None)

        def launcher(exe, params, cwd):
            _touch(maa_log)
            return handle
        with mock.patch.object(daily, "_now", clock.now), \
                mock.patch.object(daily, "_sleep", clock.sleep), \
                mock.patch.object(daily, "send_hotkey", return_value=False), \
                mock.patch.object(daily, "_maa_window_ready",
                                  return_value=True), \
                mock.patch.object(daily, "_script_running",
                                  return_value=False), \
                mock.patch.object(store, "snapshot_processes",
                                  return_value=set()):
            result = daily.run(maa, launcher=launcher)
        self.assertEqual(result["state"], daily.FAILED)
        self.assertIn("热键", result["reason"])
        self.assertTrue(handle.terminated)

        maa2, maa_log2, _gui2 = _make_maa_daily(os.path.join(self.tmp, "maa2"))
        clock2 = FakeClock()
        handle2 = FakeHandle(clock2, exit_calls=None)

        def launcher2(exe, params, cwd):
            _touch(maa_log2)
            return handle2
        with mock.patch.object(daily, "_now", clock2.now), \
                mock.patch.object(daily, "_sleep", clock2.sleep), \
                mock.patch.object(daily, "_maa_window_ready",
                                  return_value=False), \
                mock.patch.object(daily, "send_hotkey",
                                  side_effect=AssertionError("未就绪不应发热键")), \
                mock.patch.object(daily, "_script_running",
                                  return_value=False), \
                mock.patch.object(store, "snapshot_processes",
                                  return_value=set()):
            result2 = daily.run(maa2, launcher=launcher2)
        self.assertEqual(result2["state"], daily.FAILED)
        self.assertIn("未就绪", result2["reason"])

    def test_maa_close_after_terminates_handle(self):
        maa, maa_log, _gui = _make_maa_daily(self.tmp)
        maa["daily"] = store._clean_daily({"close_after": True}, "maa")
        clock = FakeClock()
        handle = FakeHandle(clock, exit_calls=None)

        def launcher(exe, params, cwd):
            _touch(maa_log)
            return handle

        def send_ok(hotkey):
            _append_text(maa_log, "任务已全部完成！\n")
            return True
        with mock.patch.object(daily, "_now", clock.now), \
                mock.patch.object(daily, "_sleep", clock.sleep), \
                mock.patch.object(daily, "send_hotkey", side_effect=send_ok), \
                mock.patch.object(daily, "_maa_window_ready",
                                  return_value=True), \
                mock.patch.object(daily, "_script_running",
                                  return_value=False), \
                mock.patch.object(store, "snapshot_processes",
                                  return_value=set()):
            result = daily.run(maa, launcher=launcher)
        self.assertEqual(result["state"], daily.FINISHED)
        self.assertTrue(handle.terminated, "close_after=True 时应结束本次启动的 MAA")
        self.assertTrue(handle.closed)

    def test_run_precondition_error_and_dry_run(self):
        maa, _log, _gui = _make_maa_daily(self.tmp, hotkey=False)
        p1, p2, p3 = (
            mock.patch.object(daily, "_script_running", return_value=False),
            mock.patch.object(daily, "_game_running", return_value=True),
            mock.patch.object(store, "snapshot_processes",
                              return_value=set()))
        with p1, p2, p3:
            result = daily.run(maa, launcher=lambda *a: (_ for _ in ()).throw(
                AssertionError("前置失败时不应启动")))
        self.assertEqual(result["state"], daily.FAILED)
        self.assertIn("前置检查未通过", result["reason"])

        result2 = daily.run(maa, dry_run=True)
        self.assertEqual(result2["state"], daily.DRY_RUN)
        self.assertEqual(result2["state_label"], "预演")
        self.assertIn("plan", result2)

    def test_state_labels(self):
        expected = {daily.IDLE: "空闲", daily.STARTING: "启动中",
                    daily.RUNNING: "运行中", daily.FINISHED: "已完成",
                    daily.FAILED: "失败", daily.TIMEOUT: "超时",
                    daily.STOPPED: "已停止", daily.SKIPPED: "已跳过",
                    daily.DRY_RUN: "预演"}
        for state, label in expected.items():
            self.assertEqual(daily.STATE_LABELS.get(state), label)


class DailyQueueTests(TempDirTest):
    """顺序队列：顺序执行 / 禁用跳过 / 失败继续 / 停止剩余 / dry-run。"""

    def _apps(self):
        apps = []
        for key, game in (("maa", "明日方舟"), ("nte", "异环"),
                          ("wuwa", "鸣潮"), ("maaend", "终末地")):
            exe = os.path.join(self.tmp, key, "script.exe")
            os.makedirs(os.path.dirname(exe), exist_ok=True)
            apps.append({"key": key, "game": game, "script_exe": exe,
                         "daily": store._clean_daily({}, key)})
        return apps

    @staticmethod
    def _fake_run(executed, state_by_key=None):
        def fake(app, settings=None, *, dry_run=False, stop_event=None,
                 on_event=None, launcher=None):
            executed.append(app["key"])
            state = (state_by_key or {}).get(app["key"], daily.FINISHED)
            return {"key": app["key"], "game": app["game"], "state": state,
                    "state_label": daily.STATE_LABELS.get(state, state),
                    "reason": "mock"}
        return fake

    def test_order_and_results(self):
        apps = self._apps()
        executed, events = [], []
        with mock.patch.object(daily, "run",
                               side_effect=self._fake_run(executed)):
            queue = daily.DailyQueue(apps, ["wuwa", "maa"],
                                     on_event=events.append)
            self.assertTrue(queue.start())
            queue._thread.join(timeout=5)
        self.assertEqual(executed, ["wuwa", "maa"])
        snapshot = queue.snapshot()
        self.assertEqual(snapshot["state"], daily.FINISHED)
        self.assertEqual([item["key"] for item in snapshot["results"]],
                         ["wuwa", "maa"])
        self.assertTrue(any(event.get("type") == "queue" for event in events))
        self.assertTrue(any(event.get("type") == "item" for event in events))

    def test_disabled_skipped(self):
        apps = self._apps()
        apps[1]["daily"] = store._clean_daily({"enabled": False}, "nte")
        executed = []
        with mock.patch.object(daily, "run",
                               side_effect=self._fake_run(executed)):
            queue = daily.DailyQueue(apps, ["maa", "nte", "wuwa"])
            queue.start()
            queue._thread.join(timeout=5)
        self.assertEqual(executed, ["maa", "wuwa"])
        states = [item["state"] for item in queue.snapshot()["results"]]
        self.assertEqual(states.count(daily.SKIPPED), 1)

    def test_failure_continues(self):
        apps = self._apps()
        executed = []
        with mock.patch.object(daily, "run", side_effect=self._fake_run(
                executed, {"maa": daily.FAILED})):
            queue = daily.DailyQueue(apps, ["maa", "nte", "wuwa"])
            queue.start()
            queue._thread.join(timeout=5)
        self.assertEqual(executed, ["maa", "nte", "wuwa"])
        snapshot = queue.snapshot()
        self.assertEqual(snapshot["state"], daily.FINISHED)
        self.assertEqual(snapshot["results"][0]["state"], daily.FAILED)

    def test_stop_marks_remaining_stopped(self):
        apps = self._apps()
        executed, holder = [], {}
        clock = FakeClock()

        def fake(app, settings=None, *, dry_run=False, stop_event=None,
                 on_event=None, launcher=None):
            executed.append(app["key"])
            holder["queue"].stop()
            return {"key": app["key"], "game": app["game"],
                    "state": daily.STOPPED, "state_label": "已停止",
                    "reason": "mock stop"}

        queue = daily.DailyQueue(apps, ["maa", "nte", "wuwa"])
        holder["queue"] = queue
        with mock.patch.object(daily, "run", side_effect=fake):
            queue.start()
            queue._thread.join(timeout=5)
        self.assertEqual(executed, ["maa"])
        snapshot = queue.snapshot()
        self.assertEqual(snapshot["state"], daily.STOPPED)
        states = [item["state"] for item in snapshot["results"]]
        self.assertEqual(states.count(daily.STOPPED), 3)

    def test_dry_run_flag_forwarded(self):
        apps = self._apps()
        flags, executed = [], []

        def fake(app, settings=None, *, dry_run=False, stop_event=None,
                 on_event=None, launcher=None):
            flags.append(dry_run)
            executed.append(app["key"])
            return {"key": app["key"], "state": daily.DRY_RUN,
                    "state_label": "预演", "reason": "mock"}

        with mock.patch.object(daily, "run", side_effect=fake):
            queue = daily.DailyQueue(apps, ["maa", "wuwa"], dry_run=True)
            queue.start()
            queue._thread.join(timeout=5)
        self.assertEqual(executed, ["maa", "wuwa"])
        self.assertEqual(flags, [True, True])


class DailyLogConfigTests(TempDirTest):
    """日志增量读取、daily 默认值、daily_order 与 config v4 往返。"""

    def test_log_watcher_incremental_and_rotation(self):
        path = _touch(os.path.join(self.tmp, "watch.log"), b"old line\n")
        watcher = daily.LogWatcher(path)
        self.assertEqual(watcher.read(), "")
        _append_text(path, "new line 1\n")
        self.assertIn("new line 1", watcher.read())
        _append_text(path, "new line 2\n")
        self.assertIn("new line 2", watcher.read())
        self.assertIn("new line 1", watcher.tail(10))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("rotated\n")
        watcher.offset = 0
        self.assertIn("rotated", watcher.read())
        self.assertEqual(daily.LogWatcher("").read(), "")

    def test_daily_clean_defaults_and_limits(self):
        wuwa = store._clean_daily(None, "wuwa")
        self.assertEqual(wuwa["task"], "DailyTask")
        self.assertEqual(wuwa["timeout_min"], 90)
        self.assertTrue(wuwa["enabled"])
        self.assertEqual(store._clean_daily(None, "maa")["close_after"], False)
        self.assertEqual(store._clean_daily(None, "maaend")["timeout_min"], 150)
        generic = store._clean_daily(None, "custom_qa")
        self.assertFalse(generic["enabled"])
        clamped = store._clean_daily({"timeout_min": 9999}, "maa")
        self.assertEqual(clamped["timeout_min"], 600)
        self.assertEqual(store._clean_daily({"timeout_min": 0}, "maa")
                         ["timeout_min"], 1)
        args = store._clean_daily({"extra_args": "--flag value"}, "maa")
        self.assertEqual(args["extra_args"], ["--flag", "value"])
        # QA-13 修复：只保留 str、strip 后丢弃 None/数字/空白/嵌套值
        mixed = store._clean_daily({
            "extra_args": [None, 3, " --x ", "", "  ", ["nested"], "--y z"]},
            "maa")["extra_args"]
        self.assertEqual(mixed, ["--x", "--y z"])
        quoted = store._clean_daily({"extra_args": '"--flag value"'}, "maa")
        self.assertEqual(quoted["extra_args"], ["--flag value"])
        # 非 bool 的 enabled 不会被接受
        self.assertTrue(store._clean_daily({"enabled": "false"}, "maa")["enabled"])

    def test_daily_order_clean(self):
        keys = ["maa", "nte", "wuwa", "maaend"]
        self.assertEqual(store._clean_daily_order(["wuwa", "bogus", "wuwa"],
                                                  keys),
                         ["wuwa", "maa", "nte", "maaend"])
        self.assertEqual(store._clean_daily_order(None, keys), keys)
        self.assertEqual(store._clean_daily_order([], keys), keys)

    def test_config_daily_roundtrip_and_legacy(self):
        apps = []
        for key, settings in (("maa", {"timeout_min": 30,
                                       "extra_args": ["--flag"]}),
                              ("wuwa", {"task": "DailyTask"})):
            app = store.make_builtin(key, self.tmp)
            app["daily"] = store._clean_daily(settings, key)
            apps.append(app)
        cfg = os.path.join(self.tmp, "config.json")
        search_root = os.path.join(self.tmp, "search_root")
        os.makedirs(search_root, exist_ok=True)
        with mock.patch.object(store, "CONFIG", cfg), \
                mock.patch.object(store, "SEARCH_ROOT", search_root):
            self.assertTrue(store.save_state(apps, "", self.tmp,
                                             daily_order=["wuwa", "maa"]))
            raw = json.load(open(cfg, "r", encoding="utf-8"))
            self.assertEqual(raw.get("version"), 4)
            self.assertEqual(raw.get("daily_order"), ["wuwa", "maa"])
            self.assertEqual(raw["apps"]["maa"]["daily"]["timeout_min"], 30)
            loaded, _clash, _root, meta = store.load_state_full()
        by_key = {app["key"]: app for app in loaded}
        self.assertEqual(meta["daily_order"][:2], ["wuwa", "maa"])
        self.assertEqual(sorted(meta["daily_order"]),
                         sorted(store.DEFAULT_DAILY_ORDER))
        self.assertEqual(by_key["maa"]["daily"]["timeout_min"], 30)
        self.assertEqual(by_key["maa"]["daily"]["extra_args"], ["--flag"])
        self.assertEqual(by_key["wuwa"]["daily"]["task"], "DailyTask")
        self.assertTrue(by_key["maa"]["daily"]["enabled"])

        # 旧 v4 配置没有 daily 字段 -> 自动补内置默认
        legacy = {"version": 4, "root": self.tmp, "apps": {"maa": {}}}
        _write_json(cfg, legacy)
        with mock.patch.object(store, "CONFIG", cfg), \
                mock.patch.object(store, "SEARCH_ROOT", search_root):
            loaded2, _c, _r, meta2 = store.load_state_full()
        maa = next(app for app in loaded2 if app["key"] == "maa")
        self.assertEqual(maa["daily"]["enabled"], True)
        self.assertEqual(maa["daily"]["timeout_min"], 120)
        self.assertEqual(meta2["daily_order"], store.DEFAULT_DAILY_ORDER)


class DailyQuotingTests(TempDirTest):
    """QA-14：命令参数统一引号处理（ShellExecuteW 参数串 + Popen argv 列表）。"""

    def _patch(self):
        return (
            mock.patch.object(daily, "_script_running", return_value=False),
            mock.patch.object(daily, "_game_running", return_value=True),
            mock.patch.object(store, "snapshot_processes",
                              return_value=set()))

    def test_quote_arg_rendering(self):
        quote = daily._quote_arg
        self.assertEqual(quote("plain"), "plain")
        self.assertEqual(quote("--config"), "--config")
        self.assertEqual(quote("a b"), '"a b"')
        self.assertEqual(quote(""), '""')
        self.assertEqual(quote('say "hi"'), '"say \\"hi\\""')
        self.assertEqual(quote("plain", force=True), '"plain"')
        # 结尾反斜杠按 2n 转义，避免吞掉收尾引号
        self.assertEqual(quote("C:\\my dir\\"), '"C:\\my dir\\\\"')
        # 单项去外层引号（UI shlex(posix=False) 写入的历史值）
        self.assertEqual(daily._normalize_extra_arg('"--flag value"'),
                         "--flag value")
        self.assertEqual(daily._normalize_extra_arg("'x'"), "x")
        self.assertEqual(daily._normalize_extra_arg("  "), "")
        self.assertEqual(daily._extra_args(
            {"extra_args": ['"a b"', " c ", ""]}), ["a b", "c"])
        # 非 str 在 _clean_daily 阶段已丢弃（_extra_args 只处理已清洗值）
        self.assertEqual(store._clean_daily(
            {"extra_args": [3, None]}, "maa")["extra_args"], [])

    def test_build_command_argv_and_params(self):
        exe = r"C:\Program Files\X\MAA.exe"
        config = 'My "Daily" Cfg'
        command = daily._build_command(exe, ["--config", config],
                                       force_quote={1})
        self.assertEqual(command["argv"], [exe, "--config", config])
        self.assertEqual(command["args"], ["--config", config])
        self.assertEqual(command["params"],
                         "--config " + daily._quote_arg(config, force=True))
        self.assertTrue(command["params"].endswith('Cfg"'))
        self.assertEqual(command["command_text"],
                         daily._quote_arg(exe, force=True) + " "
                         + command["params"])

    def test_okww_task_with_space_and_quote(self):
        task = 'Daily Task "X"'
        app, _log = _make_okww_daily(self.tmp, {"task": task})
        p1, p2, p3 = self._patch()
        with p1, p2, p3:
            plan = daily.plan_for(app)
        self.assertTrue(plan["ok"], plan["errors"])
        self.assertEqual(plan["argv"],
                         [plan["exe"], plan["args"][0], "-t", task, "-e"])
        self.assertIn("-t " + daily._quote_arg(task), plan["params"])
        self.assertIn('\\"X\\"', plan["params"])   # 内部引号被转义
        self.assertTrue(plan["params"].rstrip().endswith("-e"))

    def test_maa_config_with_space_and_quote(self):
        config = 'My "Daily" Cfg'
        app, _log, _gui = _make_maa_daily(self.tmp)
        app["daily"] = store._clean_daily({
            "config": config,
            "extra_args": ["--path", r"C:\my dir\x"]}, "maa")
        p1, p2, p3 = self._patch()
        with p1, p2, p3:
            plan = daily.plan_for(app)
        self.assertTrue(plan["ok"], plan["errors"])
        self.assertEqual(plan["argv"], [
            plan["exe"], "--skip-startup-auto-run", "--config", config,
            "--path", r"C:\my dir\x"])
        expected = ("--skip-startup-auto-run --config "
                    + daily._quote_arg(config, force=True)
                    + ' --path "C:\\my dir\\x"')
        self.assertEqual(plan["params"], expected)
        self.assertIn('\\"Daily\\"', plan["params"])
        # argv 是原始 token（config 值本身含引号字符，未做手工引号拼接）
        self.assertEqual(plan["argv"][2:4], ["--config", config])

    def test_mxu_instance_with_space_and_quote(self):
        # 异环与终末地同用 --instance/--quit-after-run，实例名包含空格/引号
        name = 'Full "Daily" Run'
        app = _make_mxu_daily(self.tmp, "maaend", instances=[{
            "name": name,
            "tasks": [{"taskName": "DailyTask", "enabled": True}]}])
        app["daily"] = store._clean_daily({
            "instance": name, "extra_args": ["--opt=a b"]}, "maaend")
        p1, p2, p3 = self._patch()
        with p1, p2, p3:
            plan = daily.plan_for(app)
        self.assertTrue(plan["ok"], plan["errors"])
        self.assertEqual(plan["argv"], [
            plan["exe"], "--autostart", "--instance", name,
            "--quit-after-run", "--opt=a b"])
        expected = ("--autostart --instance "
                    + daily._quote_arg(name, force=True)
                    + ' --quit-after-run "--opt=a b"')
        self.assertEqual(plan["params"], expected)
        self.assertIn('\\"Daily\\"', plan["params"])

        nte = _make_mxu_daily(os.path.join(self.tmp, "nte_quote"), "nte",
                              instances=[{"name": name, "tasks": [
                                  {"taskName": "DailyTask",
                                   "enabled": True}]}])
        nte["daily"] = store._clean_daily({"instance": name}, "nte")
        p1, p2, p3 = self._patch()
        with p1, p2, p3:
            nte_plan = daily.plan_for(nte)
        self.assertTrue(nte_plan["ok"], nte_plan["errors"])
        self.assertIn('--instance ' + daily._quote_arg(name, force=True),
                      nte_plan["params"])
        self.assertTrue(nte_plan["params"].endswith("--quit-after-run"))


# ---------------------------------------------------------------- v0.8 设置 / 勾选 / 独立状态
def _plain_daily_apps():
    apps = []
    for key, game in (("maa", "MAA"), ("nte", "NTE"), ("wuwa", "WW"),
                      ("maaend", "ENDFIELD")):
        apps.append({"key": key, "game": game, "script": game, "builtin": True,
                     "script_exe": "", "script_procs": [], "game_procs": [],
                     "game_exe": "", "daily": store._clean_daily({}, key)})
    return apps


class SettingsTests(unittest.TestCase):
    """v0.8 store._clean_settings / ui._refresh_delay_ms 纯逻辑。"""

    def test_settings_defaults(self):
        defaults = store._clean_settings(None)
        self.assertEqual(defaults, dict(store.DEFAULT_SETTINGS))
        self.assertEqual(defaults["accent"], "#4fc3ff")
        self.assertEqual(defaults["refresh_interval"], 1.5)
        self.assertEqual(defaults["close_action"], "exit")
        self.assertEqual(defaults["daily_default_timeout"], 120)
        self.assertTrue(defaults["check_update_on_start"])
        self.assertFalse(defaults["adb_enabled"])
        for bad in ("x", [], 3, True):
            with self.subTest(bad=bad):
                self.assertEqual(store._clean_settings(bad),
                                 dict(store.DEFAULT_SETTINGS))

    def test_settings_clean_valid(self):
        cleaned = store._clean_settings({
            "accent": "  #B98BFF  ", "check_update_on_start": False,
            "refresh_interval": 2.0, "close_action": "Minimize",
            "clash_exe": r"  C:\Clash\clash-verge.exe  ",
            "daily_default_timeout": 9999, "daily_show_preview": False,
            "adb_enabled": True, "daily_close_after": False,
        })
        self.assertEqual(cleaned["accent"], "#b98bff")
        self.assertFalse(cleaned["check_update_on_start"])
        self.assertEqual(cleaned["refresh_interval"], 2.0)
        self.assertEqual(cleaned["close_action"], "minimize")
        self.assertEqual(cleaned["clash_exe"], r"C:\Clash\clash-verge.exe")
        self.assertEqual(cleaned["daily_default_timeout"], 600)
        self.assertFalse(cleaned["daily_show_preview"])
        self.assertTrue(cleaned["adb_enabled"])
        self.assertFalse(cleaned["daily_close_after"])
        for interval in store.REFRESH_INTERVALS:
            with self.subTest(interval=interval):
                self.assertEqual(store._clean_settings(
                    {"refresh_interval": interval})["refresh_interval"],
                    float(interval))

    def test_settings_clean_invalid(self):
        bad = store._clean_settings({
            "accent": "red", "refresh_interval": 7,
            "close_action": "explode", "daily_default_timeout": -3,
            "check_update_on_start": "false", "enabled": "true"})
        self.assertEqual(bad["accent"], "#4fc3ff")
        self.assertEqual(bad["refresh_interval"], 1.5)
        self.assertEqual(bad["close_action"], "exit")
        self.assertEqual(bad["daily_default_timeout"], 1)
        self.assertTrue(bad["check_update_on_start"])
        self.assertNotIn("enabled", bad)
        # 各种非法 accent 均回退默认
        for accent in ("", "#12345", "#GGGGGG", "#12345g", None, 123):
            with self.subTest(accent=accent):
                self.assertEqual(store._clean_settings(
                    {"accent": accent})["accent"], "#4fc3ff")
        # 非法 refresh / close_action / timeout 回退
        self.assertEqual(store._clean_settings(
            {"refresh_interval": "1.5"})["refresh_interval"], 1.5)
        self.assertEqual(store._clean_settings(
            {"refresh_interval": True})["refresh_interval"], 1.5)
        self.assertEqual(store._clean_settings(
            {"close_action": ""})["close_action"], "exit")
        self.assertEqual(store._clean_settings(
            {"daily_default_timeout": "60"})["daily_default_timeout"], 120)
        self.assertEqual(store._clean_settings(
            {"daily_default_timeout": 0.5})["daily_default_timeout"], 1)

    def test_refresh_delay_ms(self):
        self.assertEqual(ui._refresh_delay_ms({"refresh_interval": 1.0}), 1000)
        self.assertEqual(ui._refresh_delay_ms({"refresh_interval": 1.5}), 1500)
        self.assertEqual(ui._refresh_delay_ms({"refresh_interval": 2.0}), 2000)
        self.assertEqual(ui._refresh_delay_ms({"refresh_interval": 9}), 1500)
        self.assertEqual(ui._refresh_delay_ms({"refresh_interval": "2.0"}), 2000)
        self.assertEqual(ui._refresh_delay_ms({"refresh_interval": "bad"}), 1500)
        self.assertEqual(ui._refresh_delay_ms({}), 1500)
        self.assertEqual(ui._refresh_delay_ms(None), 1500)


class SettingsConfigTests(TempDirTest):
    """v0.8 settings 持久化 / 旧配置兼容 / 默认超时只作用于显式 daily。"""

    def test_settings_roundtrip(self):
        apps = [store.make_builtin("maa", self.tmp),
                store.make_builtin("wuwa", self.tmp)]
        clash = _touch(os.path.join(self.tmp, "Clash", "clash-verge.exe"))
        cfg = os.path.join(self.tmp, "config.json")
        search_root = os.path.join(self.tmp, "search_root")
        os.makedirs(search_root, exist_ok=True)
        settings = {"accent": "#9AE66E", "refresh_interval": 2.0,
                    "close_action": "minimize", "daily_default_timeout": 45,
                    "daily_show_preview": False, "adb_enabled": True,
                    "check_update_on_start": False}
        with mock.patch.object(store, "CONFIG", cfg), \
                mock.patch.object(store, "SEARCH_ROOT", search_root):
            self.assertTrue(store.save_state(
                apps, clash=clash, root=self.tmp,
                daily_order=["wuwa", "maa"], settings=settings))
            raw = json.load(open(cfg, "r", encoding="utf-8"))
            self.assertEqual(raw.get("version"), 4)
            self.assertEqual(raw["settings"]["accent"], "#9ae66e")
            self.assertEqual(raw["settings"]["refresh_interval"], 2.0)
            self.assertEqual(raw["settings"]["close_action"], "minimize")
            self.assertEqual(raw["settings"]["daily_default_timeout"], 45)
            self.assertFalse(raw["settings"]["check_update_on_start"])
            self.assertTrue(raw["settings"]["adb_enabled"])
            # clash 路径在 settings 内写成相对 root 的便携格式
            self.assertFalse(os.path.isabs(raw["settings"]["clash_exe"]))
            self.assertEqual(raw["settings"]["clash_exe"].replace("\\", "/"),
                             "Clash/clash-verge.exe")
            self.assertEqual(raw.get("daily_order"), ["wuwa", "maa"])
            loaded, runtime_clash, _root, meta = store.load_state_full()
        self.assertEqual(meta["settings"]["accent"], "#9ae66e")
        self.assertEqual(meta["settings"]["refresh_interval"], 2.0)
        self.assertEqual(meta["settings"]["close_action"], "minimize")
        self.assertEqual(meta["settings"]["daily_default_timeout"], 45)
        self.assertEqual(meta["daily_order"], ["wuwa", "maa", "nte", "maaend"])
        self.assertEqual(os.path.normpath(runtime_clash),
                         os.path.normpath(clash),
                         "运行期 clash 仍应还原为绝对路径")
        self.assertEqual(os.path.normpath(meta["settings"]["clash_exe"]),
                         os.path.normpath(clash),
                         "QA-15：settings.clash_exe 也应按 root 还原为绝对路径")
        by_key = {app["key"]: app for app in loaded}
        self.assertTrue(by_key["maa"]["daily"]["enabled"])

    def test_legacy_config_without_settings(self):
        cfg = os.path.join(self.tmp, "config.json")
        search_root = os.path.join(self.tmp, "search_root")
        os.makedirs(search_root, exist_ok=True)
        _write_json(cfg, {"version": 4, "root": self.tmp,
                          "apps": {"maa": {}}})
        with mock.patch.object(store, "CONFIG", cfg), \
                mock.patch.object(store, "SEARCH_ROOT", search_root):
            loaded, _clash, _root, meta = store.load_state_full()
        self.assertEqual(meta["settings"], dict(store.DEFAULT_SETTINGS))
        maa = next(app for app in loaded if app["key"] == "maa")
        self.assertEqual(maa["daily"]["timeout_min"], 120)
        self.assertFalse(maa["daily_explicit"])
        self.assertEqual(meta["daily_order"], store.DEFAULT_DAILY_ORDER)

    def test_daily_default_timeout_applies_only_to_explicit_daily(self):
        cfg = os.path.join(self.tmp, "config.json")
        search_root = os.path.join(self.tmp, "search_root")
        os.makedirs(search_root, exist_ok=True)
        custom_exe = _touch(os.path.join(self.tmp, "Custom", "s.exe"))
        _write_json(cfg, {
            "version": 4, "root": self.tmp,
            "settings": {"daily_default_timeout": 55},
            "apps": {"maa": {"daily": {"enabled": True,
                                       "task": "DailyTask"}},
                     "nte": {}},
            "custom_apps": [{"key": "custom_1", "game": "G", "script": "S",
                             "script_exe": custom_exe,
                             "daily": {"enabled": True}}],
        })
        with mock.patch.object(store, "CONFIG", cfg), \
                mock.patch.object(store, "SEARCH_ROOT", search_root):
            loaded, _clash, _root, _meta = store.load_state_full()
        by_key = {app["key"]: app for app in loaded}
        # 写过 daily 但没写 timeout_min -> 用设置页默认超时
        self.assertEqual(by_key["maa"]["daily"]["timeout_min"], 55)
        self.assertTrue(by_key["maa"]["daily_explicit"])
        self.assertEqual(by_key["custom_1"]["daily"]["timeout_min"], 55)
        # 完全没写 daily 的内置卡片保持各游戏内置默认值
        self.assertEqual(by_key["nte"]["daily"]["timeout_min"], 120)
        self.assertFalse(by_key["nte"]["daily_explicit"])


class ClashResolutionTests(TempDirTest):
    """QA-15（task-29 修复）：clash 顶层/settings 相对路径解析与优先级。"""

    def _load(self, data, candidates=()):
        cfg = os.path.join(self.tmp, "config.json")
        _write_json(cfg, data)
        search = os.path.join(self.tmp, "search_root")
        os.makedirs(search, exist_ok=True)
        with mock.patch.object(store, "CONFIG", cfg), \
                mock.patch.object(store, "SEARCH_ROOT", search), \
                mock.patch.object(store, "CLASH_CANDIDATES",
                                  list(candidates)):
            return store.load_state_full()

    def test_settings_clash_relative_and_absolute(self):
        rel = os.path.join("Clash", "clash-verge.exe")
        absolute = _touch(os.path.join(self.tmp, rel))
        for value in (rel.replace("\\", "/"), absolute):
            with self.subTest(value=value):
                _apps, clash, _root, meta = self._load({
                    "version": 4, "root": self.tmp,
                    "settings": {"clash_exe": value}})
                self.assertEqual(os.path.normpath(clash),
                                 os.path.normpath(absolute))
                self.assertEqual(
                    os.path.normpath(meta["settings"]["clash_exe"]),
                    os.path.normpath(absolute))

    def test_clash_priority_top_over_settings(self):
        settings_relative = os.path.join("Clash", "clash-verge.exe")
        settings_abs = _touch(os.path.join(self.tmp, settings_relative))
        top_other = _touch(os.path.join(self.tmp, "Other", "clash.exe"))
        # 顶层绝对路径优先，settings 也独立还原为绝对路径
        _a, clash, _r, meta = self._load({
            "version": 4, "root": self.tmp, "clash": top_other,
            "settings": {"clash_exe": settings_relative.replace("\\", "/")}})
        self.assertEqual(os.path.normpath(clash), os.path.normpath(top_other))
        self.assertEqual(os.path.normpath(meta["settings"]["clash_exe"]),
                         os.path.normpath(settings_abs))
        # 顶层相对路径同样按 root 还原
        _a, clash2, _r, _m = self._load({
            "version": 4, "root": self.tmp,
            "clash": settings_relative.replace("\\", "/")})
        self.assertEqual(os.path.normpath(clash2),
                         os.path.normpath(settings_abs))
        # 顶层路径失效 -> 回退 settings
        _a, clash3, _r, _m = self._load({
            "version": 4, "root": self.tmp,
            "clash": os.path.join(self.tmp, "nope", "x.exe"),
            "settings": {"clash_exe": settings_relative.replace("\\", "/")}})
        self.assertEqual(os.path.normpath(clash3),
                         os.path.normpath(settings_abs))

    def test_clash_fallback_to_auto_candidates(self):
        candidate = _touch(os.path.join(self.tmp, "Auto", "clash.exe"))
        _a, clash, _r, _m = self._load({"version": 4, "root": self.tmp},
                                       candidates=[candidate])
        self.assertEqual(os.path.normpath(clash), os.path.normpath(candidate))
        # settings 路径不存在：保留原值供 UI 显示，运行期回退自动查找
        _a, clash2, _r, meta2 = self._load({
            "version": 4, "root": self.tmp,
            "settings": {"clash_exe": "Clash/nope.exe"}},
            candidates=[candidate])
        self.assertEqual(os.path.normpath(clash2),
                         os.path.normpath(candidate))
        self.assertEqual(meta2["settings"]["clash_exe"].replace("\\", "/"),
                         "Clash/nope.exe")


class DailySelectionTests(unittest.TestCase):
    """v0.8 清日常勾选过滤与 daily_order 顺序。"""

    def _apps(self):
        apps = _plain_daily_apps()
        apps.append({"key": "custom_1", "game": "G", "builtin": False,
                     "daily": store._clean_daily({"enabled": True},
                                                 "custom_1")})
        return apps

    def test_ordered_daily_keys(self):
        apps = self._apps()
        keys = daily.ordered_daily_keys(apps, ["wuwa", "bogus", "maa", "wuwa"])
        self.assertEqual(keys, ["wuwa", "maa", "nte", "maaend", "custom_1"])
        # 未指定 order -> 默认顺序 + 末尾补自定义
        self.assertEqual(daily.ordered_daily_keys(apps),
                         ["maa", "nte", "wuwa", "maaend", "custom_1"])
        self.assertEqual(daily.ordered_daily_keys([], None), [])

    def test_enabled_daily_keys(self):
        apps = self._apps()
        apps[1]["daily"] = store._clean_daily({"enabled": False}, "nte")
        apps[4]["daily"] = store._clean_daily({"enabled": False}, "custom_1")
        keys = daily.enabled_daily_keys(apps, ["maa", "nte", "wuwa", "maaend"])
        self.assertEqual(keys, ["maa", "wuwa", "maaend"])
        # 未写 daily 的内置卡片默认勾选
        bare = [{"key": "maa", "game": "MAA"},
                {"key": "nte", "game": "NTE"}]
        self.assertEqual(daily.enabled_daily_keys(bare), ["maa", "nte"])

    def test_selection_reflects_toggle(self):
        apps = self._apps()
        self.assertIn("nte",
                      daily.enabled_daily_keys(
                          apps, store.DEFAULT_DAILY_ORDER))
        apps[1]["daily"]["enabled"] = False
        self.assertNotIn("nte",
                         daily.enabled_daily_keys(
                             apps, store.DEFAULT_DAILY_ORDER))
        apps[1]["daily"]["enabled"] = True
        self.assertIn("nte",
                      daily.enabled_daily_keys(
                          apps, store.DEFAULT_DAILY_ORDER))


class DailyManagerTests(TempDirTest):
    """v0.8 DailyManager：每游戏独立状态 / start_single / stop_single / 队列。"""

    def _wait_idle(self, manager, timeout=5.0):
        deadline = time.time() + timeout
        while manager.busy and time.time() < deadline:
            time.sleep(0.01)
        self.assertFalse(manager.busy, "DailyManager 未在超时内结束")

    def test_initial_and_reset(self):
        manager = daily.DailyManager(_plain_daily_apps())
        snapshot = manager.snapshot()
        self.assertFalse(snapshot["busy"])
        self.assertIsNone(snapshot["active"])
        self.assertEqual(snapshot["mode"], "")
        self.assertEqual(snapshot["queue"]["state"], daily.IDLE)
        for key in ("maa", "nte", "wuwa", "maaend"):
            state = manager.state_of(key)
            self.assertEqual(state["state"], daily.IDLE)
            self.assertEqual(state["state_label"], "空闲")
        manager.reset()
        self.assertEqual(manager.state_of("maa")["state"], daily.IDLE)

    def test_start_single_isolates_other_apps(self):
        apps = _plain_daily_apps()
        gate, started = threading.Event(), threading.Event()
        executed, events = [], []

        def fake(app, settings=None, *, dry_run=False, stop_event=None,
                 on_event=None, launcher=None):
            executed.append(app["key"])
            if on_event:
                on_event({"type": "state", "key": app["key"],
                          "state": daily.RUNNING, "pid": 4321})
            started.set()
            gate.wait(timeout=5)
            return {"key": app["key"], "game": app["game"],
                    "state": daily.FINISHED, "reason": "mock", "pid": 4321}

        with mock.patch.object(daily, "run", side_effect=fake):
            manager = daily.DailyManager(apps, on_event=events.append)
            ok, reason = manager.start_single("maa")
            self.assertTrue(ok, reason)
            self.assertTrue(started.wait(timeout=2))
            self.assertTrue(manager.busy)
            self.assertIn(manager.state_of("maa")["state"],
                          (daily.STARTING, daily.RUNNING))
            for key in ("nte", "wuwa", "maaend"):
                self.assertEqual(manager.state_of(key)["state"], daily.IDLE,
                                 f"{key} 不应被标记为运行中")
            ok2, reason2 = manager.start_single("nte")
            self.assertFalse(ok2)
            self.assertIn("进行中", reason2)
            self.assertIn("进行中", manager.busy_reason("nte"))
            self.assertFalse(manager.stop_single("nte"))
            gate.set()
            self._wait_idle(manager)
        self.assertEqual(executed, ["maa"])
        self.assertEqual(manager.state_of("maa")["state"], daily.FINISHED)
        for key in ("nte", "wuwa", "maaend"):
            self.assertEqual(manager.state_of(key)["state"], daily.IDLE)
        self.assertFalse(manager.stop_single("maa"))
        self.assertTrue(any(event.get("type") == "state" for event in events))

    def test_stop_single(self):
        apps = _plain_daily_apps()
        started, stop_seen = threading.Event(), threading.Event()

        def fake(app, settings=None, *, dry_run=False, stop_event=None,
                 on_event=None, launcher=None):
            started.set()
            while stop_event is not None and not stop_event.is_set():
                time.sleep(0.01)
            stop_seen.set()
            return {"key": app["key"], "game": app["game"],
                    "state": daily.STOPPED, "reason": "用户停止"}

        with mock.patch.object(daily, "run", side_effect=fake):
            manager = daily.DailyManager(apps)
            self.assertTrue(manager.start_single("wuwa")[0])
            self.assertTrue(started.wait(timeout=2))
            self.assertTrue(manager.stop_single("wuwa"))
            self.assertTrue(stop_seen.wait(timeout=2))
            self._wait_idle(manager)
        self.assertEqual(manager.state_of("wuwa")["state"], daily.STOPPED)
        self.assertFalse(manager.stop_single("maa"))
        self.assertFalse(manager.stop_all())

    def test_queue_isolates_non_current_states(self):
        apps = _plain_daily_apps()
        gate, started = threading.Event(), threading.Event()
        executed = []

        def fake(app, settings=None, *, dry_run=False, stop_event=None,
                 on_event=None, launcher=None):
            executed.append(app["key"])
            if on_event:
                on_event({"type": "state", "key": app["key"],
                          "state": daily.RUNNING, "pid": 2})
            if app["key"] == "maa":
                started.set()
                gate.wait(timeout=5)
            return {"key": app["key"], "game": app["game"],
                    "state": daily.FINISHED, "reason": "mock"}

        with mock.patch.object(daily, "run", side_effect=fake):
            manager = daily.DailyManager(apps)
            ok, reason = manager.start_queue(["maa", "wuwa"])
            self.assertTrue(ok, reason)
            self.assertTrue(started.wait(timeout=2))
            snapshot = manager.snapshot()
            self.assertEqual(snapshot["active"], "maa")
            self.assertEqual(snapshot["mode"], "queue")
            self.assertEqual(snapshot["queue"]["current"], "maa")
            self.assertEqual(manager.state_of("maa")["state"], daily.RUNNING)
            # 队列里非当前项以及其他未参与卡片都保持空闲
            for key in ("wuwa", "nte", "maaend"):
                self.assertEqual(manager.state_of(key)["state"], daily.IDLE)
            self.assertIn("进行中", manager.busy_reason("wuwa"))
            gate.set()
            self._wait_idle(manager)
        self.assertEqual(executed, ["maa", "wuwa"])
        for key in ("maa", "wuwa"):
            self.assertEqual(manager.state_of(key)["state"], daily.FINISHED)
        for key in ("nte", "maaend"):
            self.assertEqual(manager.state_of(key)["state"], daily.IDLE)
        queue = manager.snapshot()["queue"]
        self.assertEqual(queue["state"], daily.FINISHED)
        self.assertEqual([item["key"] for item in queue["results"]],
                         ["maa", "wuwa"])

    def test_queue_stop_marks_remaining_stopped(self):
        apps = _plain_daily_apps()
        holder, executed = {}, []

        def fake(app, settings=None, *, dry_run=False, stop_event=None,
                 on_event=None, launcher=None):
            executed.append(app["key"])
            if app["key"] == "maa":
                holder["manager"].stop_all()
                if stop_event is not None:
                    stop_event.wait(2)
                return {"key": app["key"], "game": app["game"],
                        "state": daily.STOPPED, "reason": "用户停止"}
            return {"key": app["key"], "game": app["game"],
                    "state": daily.FINISHED, "reason": "mock"}

        with mock.patch.object(daily, "run", side_effect=fake):
            manager = daily.DailyManager(apps)
            holder["manager"] = manager
            ok, reason = manager.start_queue(["maa", "wuwa", "maaend"])
            self.assertTrue(ok, reason)
            self._wait_idle(manager)
            snapshot = manager.snapshot()
        self.assertEqual(executed, ["maa"])
        self.assertEqual(snapshot["queue"]["state"], daily.STOPPED)
        for key in ("maa", "wuwa", "maaend"):
            self.assertEqual(manager.state_of(key)["state"], daily.STOPPED)

    def test_queue_selection_and_edges(self):
        apps = _plain_daily_apps()
        apps[1]["daily"] = store._clean_daily({"enabled": False}, "nte")
        keys = daily.enabled_daily_keys(apps, ["maa", "nte", "wuwa"])
        # 未列出的存在卡片补在末尾（maaend），disabled 的 nte 被过滤
        self.assertEqual(keys, ["maa", "wuwa", "maaend"])
        executed = []

        def fake(app, settings=None, *, dry_run=False, stop_event=None,
                 on_event=None, launcher=None):
            executed.append(app["key"])
            return {"key": app["key"], "game": app["game"],
                    "state": daily.FINISHED, "reason": "mock"}

        with mock.patch.object(daily, "run", side_effect=fake):
            manager = daily.DailyManager(apps)
            ok, reason = manager.start_queue(keys)
            self.assertTrue(ok, reason)
            self._wait_idle(manager)
            self.assertEqual(executed, ["maa", "wuwa", "maaend"])
            self.assertEqual(manager.state_of("nte")["state"], daily.IDLE)
            self.assertEqual(manager.state_of("wuwa")["state"], daily.FINISHED)
            ok2, reason2 = manager.start_queue(["bogus"])
            self.assertFalse(ok2)
            self.assertIn("没有勾选", reason2)
            ok3, reason3 = manager.start_single("bogus")
            self.assertFalse(ok3)
            self.assertIn("不存在", reason3)

    def test_start_while_queue_busy(self):
        apps = _plain_daily_apps()
        gate, started = threading.Event(), threading.Event()

        def fake(app, settings=None, *, dry_run=False, stop_event=None,
                 on_event=None, launcher=None):
            started.set()
            gate.wait(timeout=5)
            return {"key": app["key"], "game": app["game"],
                    "state": daily.FINISHED, "reason": "mock"}

        with mock.patch.object(daily, "run", side_effect=fake):
            manager = daily.DailyManager(apps)
            self.assertTrue(manager.start_queue(["maa"])[0])
            self.assertTrue(started.wait(timeout=2))
            self.assertFalse(manager.start_single("nte")[0])
            ok, reason = manager.start_queue(["wuwa"])
            self.assertFalse(ok)
            self.assertIn("已有清日常任务在运行", reason)
            gate.set()
            self._wait_idle(manager)


class UiPureLogicTests(unittest.TestCase):
    """v0.8 UI 侧可无头测试的纯函数（页面切换为实例方法，见未覆盖点）。"""

    def test_parse_changelog(self):
        text = "\n".join([
            "# CHANGELOG",
            "## v0.7.0（2026-10-18）",
            "- v0.7 内容",
            "## v0.8.0 (2026-10-18)",
            "- v0.8 内容 A",
            "- v0.8 内容 B",
            "## v0.6.0",
            "- v0.6 内容",
            "随便一段不是标题的文字",
        ])
        sections = ui._parse_changelog(text)
        self.assertEqual([item["version"] for item in sections],
                         ["v0.8.0", "v0.7.0", "v0.6.0"])
        self.assertEqual(sections[0]["date"], "2026-10-18")
        self.assertIn("v0.8 内容 A", sections[0]["body"])
        self.assertIn("v0.8 内容 B", sections[0]["body"])
        self.assertEqual(sections[2]["date"], "")
        self.assertEqual(ui._parse_changelog(""), [])

    def test_find_changelog(self):
        path = ui._find_changelog()
        self.assertTrue(path, "源码运行时应能找到仓库根目录 CHANGELOG.md")
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(os.path.basename(path), "CHANGELOG.md")

    def test_refresh_delay_mapping(self):
        settings = {"refresh_interval": 1.0}
        self.assertEqual(ui._refresh_delay_ms(settings), 1000)
        settings["refresh_interval"] = 2.0
        self.assertEqual(ui._refresh_delay_ms(settings), 2000)
        settings["refresh_interval"] = 9
        self.assertEqual(ui._refresh_delay_ms(settings), 1500)


# ---------------------------------------------------------------- v0.9 UI 令牌 / 软件更新 / 小工具
class V09ThemeTests(unittest.TestCase):
    """v0.9 设计令牌、字体、色板与项目链接常量。"""

    def test_theme_tokens_and_scale(self):
        theme = ui.T
        self.assertEqual(theme.UI_FONT, "Microsoft YaHei UI")
        sizes = theme.UI_FONT_SIZES
        self.assertTrue(20 <= sizes["title"] <= 22)
        self.assertEqual(sizes["page"], 16)
        self.assertGreaterEqual(sizes["aux"], 10)
        self.assertGreaterEqual(min(sizes.values()), 10)
        self.assertIn(theme.RADIUS, (10, 12))
        self.assertEqual(theme.RADIUS_SM, 8)
        self.assertEqual((theme.SPACE_XS, theme.SPACE_SM, theme.SPACE_MD,
                          theme.SPACE_LG, theme.SPACE_XL), (8, 12, 16, 20, 24))
        self.assertEqual((theme.WIN_W, theme.WIN_H), (1180, 760))
        self.assertEqual((theme.MIN_W, theme.MIN_H), (1000, 640))
        self.assertEqual(theme.SIDEBAR_W, 232)
        # 旧 Pillow 渲染尺寸保持（render.py 回归）
        self.assertEqual((theme.W, theme.H), (1200, 560))
        self.assertEqual((theme.BTN_W, theme.BTN_H), (99, 44))
        self.assertEqual(len(theme.ACCENT_PRESETS), 8)

    def test_palette_hex_and_compat_aliases(self):
        theme = ui.T
        color_names = [name for name in dir(theme)
                       if name.startswith("UI_")
                       and isinstance(getattr(theme, name), str)
                       and getattr(theme, name).startswith("#")]
        self.assertTrue(color_names)
        for name in color_names:
            with self.subTest(name=name):
                self.assertRegex(getattr(theme, name), r"^#[0-9a-fA-F]{6}$")
        aliases = {"HEX_BG": "UI_BG", "HEX_TXT": "UI_TEXT",
                   "HEX_TXT2": "UI_TEXT_2", "HEX_TXT3": "UI_TEXT_3",
                   "HEX_OK": "UI_SUCCESS", "HEX_ERR": "UI_DANGER",
                   "HEX_WAIT": "UI_WARNING"}
        for old, new in aliases.items():
            self.assertEqual(getattr(theme, old), getattr(theme, new))
        accents = [color for _name, color in theme.ACCENT_PRESETS]
        self.assertEqual(len(set(accents)), 8)
        for color in accents:
            self.assertRegex(color, r"^#[0-9a-fA-F]{6}$")

    def test_project_links_and_title(self):
        self.assertEqual(ui.TITLE, "All-My-Maa · 游戏脚本中心")
        self.assertEqual(ui.GITHUB_REPO, "Diaohesi/All-My-Maa")
        self.assertEqual(ui.PROJECT_GITHUB,
                         "https://github.com/Diaohesi/All-My-Maa")
        self.assertEqual(ui.PROJECT_PAGES,
                         "https://diaohesi.github.io/All-My-Maa/")
        self.assertEqual(ui.RELEASE_API,
                         "https://api.github.com/repos/"
                         f"{ui.GITHUB_REPO}/releases/latest")
        self.assertEqual(ui.RELEASE_PAGE,
                         f"https://github.com/{ui.GITHUB_REPO}/releases/latest")

    def test_mix_colors(self):
        self.assertEqual(ui._mix("#000000", "#ffffff", 0), "#000000")
        self.assertEqual(ui._mix("#000000", "#ffffff", 1), "#ffffff")
        self.assertEqual(ui._mix("#000000", "#ffffff", 0.5), "#7f7f7f")
        self.assertEqual(ui._mix("#000000", "#ff0000", 0.5), "#7f0000")
        self.assertEqual(ui._mix("bad", "#ffffff", 0.5), "bad")


class SoftwareUpdateTests(unittest.TestCase):
    """v0.9 软件更新纯逻辑：版本比较 / release 解析 / 链接 / 无网络错误处理。"""

    def test_version_compare(self):
        self.assertEqual(store.version_key("v0.9.0"), (0, 9, 0))
        self.assertTrue(store.is_newer("v0.9.0", "v0.8.0"))
        self.assertFalse(store.is_newer("v0.9.0", "0.9.0"))
        self.assertTrue(store.is_newer("v0.10.0", "v0.9.9"))
        self.assertTrue(store.is_newer("V0.9.0", "v0.8.0"))
        self.assertFalse(store.is_newer("v0.9.0", "v0.9.0"))

    def test_parse_release_payload(self):
        payload = json.dumps({
            "tag_name": "v0.9.0",
            "name": "All-My-Maa v0.9.0",
            "body": "## 更新\n- **圆角 UI**",
            "html_url": "https://example.com/release",
            "published_at": "2026-10-18T00:00:00Z",
        }, ensure_ascii=False)
        info = ui.parse_release_payload(payload, "0.8.0")
        self.assertEqual(info["error"], "")
        self.assertEqual(info["version"], "0.9.0")
        self.assertEqual(info["current"], "0.8.0")
        self.assertTrue(info["newer"])
        self.assertIn("圆角 UI", info["changelog"])
        self.assertEqual(info["url"], "https://example.com/release")
        self.assertEqual(info["name"], "All-My-Maa v0.9.0")
        self.assertEqual(info["published_at"], "2026-10-18T00:00:00Z")
        # dict / bytes 输入、tag 无 v 前缀、name 兜底
        self.assertEqual(ui.parse_release_payload(
            {"tag_name": "0.9.0"}, "0.8.0")["version"], "0.9.0")
        self.assertEqual(ui.parse_release_payload(
            payload.encode("utf-8"), "0.8.0")["version"], "0.9.0")
        self.assertEqual(ui.parse_release_payload(
            {"name": "v0.9.0"}, "0.8.0")["version"], "0.9.0")
        # 相同/更低版本不提示更新
        self.assertFalse(ui.parse_release_payload(
            {"tag_name": "v0.8.0"}, "0.8.0")["newer"])
        self.assertFalse(ui.parse_release_payload(
            {"tag_name": "v0.7.9"}, "0.8.0")["newer"])

    def test_parse_release_payload_errors(self):
        bad = ui.parse_release_payload("{not json", "0.8.0")
        self.assertTrue(bad["error"])
        self.assertIn("解析 release 信息失败", bad["error"])
        self.assertEqual(ui.parse_release_payload(["x"], "0.8.0")["error"],
                         "release 信息格式不正确")
        self.assertEqual(ui.parse_release_payload({}, "0.8.0")["error"],
                         "release 信息缺少版本号")
        self.assertEqual(ui.parse_release_payload({"tag_name": "v"},
                                                  "0.8.0")["error"],
                         "release 信息缺少版本号")
        self.assertIn("无法识别版本号",
                      ui.parse_release_payload({"tag_name": "release-latest"},
                                               "0.8.0")["error"])
        self.assertTrue(ui.parse_release_payload(b"\xff\xfe\x00",
                                                 "0.8.0")["error"])

    def test_release_url_fallback(self):
        info = ui.parse_release_payload({"tag_name": "v0.9.0"}, "0.8.0")
        self.assertEqual(info["url"], ui.RELEASE_PAGE)
        self.assertEqual(info["changelog"], "")
        self.assertEqual(info["published_at"], "")

    def test_check_latest_with_mocks(self):
        app = {"key": "custom", "release":
               "https://github.com/x/y/releases/latest"}
        with mock.patch.object(store, "github_latest_tag",
                               return_value="v0.9.0") as fake:
            self.assertEqual(store.check_latest(app), "v0.9.0")
            fake.assert_called_once()
        with mock.patch.object(store, "github_latest_tag",
                               side_effect=OSError("offline")):
            self.assertIsNone(store.check_latest(app))
        with mock.patch.object(store, "github_latest_tag") as fake:
            self.assertIsNone(store.check_latest({"release": ""}))
            fake.assert_not_called()
        # MAA 走 api.maa.plus；mock http_get 避免真实网络
        with mock.patch.object(store, "http_get",
                               return_value=b'{"version": "v6.19.0"}'):
            self.assertEqual(store.check_latest({"key": "maa"}), "v6.19.0")
        with mock.patch.object(store, "http_get",
                               side_effect=OSError("offline")), \
                mock.patch.object(store, "github_latest_tag",
                                  side_effect=OSError("offline")):
            self.assertIsNone(store.check_latest(
                {"key": "maa", "release": "https://example.com/r"}))


class SmallToolsTests(TempDirTest):
    """v0.9 小工具：脚本/日志目录、License/更新日志定位、Clash 路径解析（mock 打开）。"""

    def test_script_directory(self):
        self.assertEqual(ui._script_directory(self.tmp),
                         os.path.abspath(self.tmp))
        self.assertEqual(ui._script_directory(""), store.APP_DIR)
        self.assertEqual(ui._script_directory(None), store.APP_DIR)
        # 相对路径按当前工作目录转绝对路径（临时切换 cwd 后恢复）
        sub = os.path.join(self.tmp, "sub")
        os.makedirs(sub, exist_ok=True)
        old_cwd = os.getcwd()
        try:
            os.chdir(self.tmp)
            self.assertEqual(ui._script_directory("sub"), sub)
        finally:
            os.chdir(old_cwd)

    def test_log_directory(self):
        self.assertEqual(ui._log_directory(self.tmp), self.tmp)
        log_dir = os.path.join(self.tmp, "log")
        os.makedirs(log_dir)
        self.assertEqual(ui._log_directory(self.tmp), log_dir)
        logs_dir = os.path.join(self.tmp, "logs")
        os.makedirs(logs_dir)
        self.assertEqual(ui._log_directory(self.tmp), logs_dir,
                         "logs 优先于 log")

    def test_license_and_changelog(self):
        license_path = ui._find_license()
        self.assertTrue(license_path)
        self.assertTrue(os.path.isfile(license_path))
        self.assertEqual(ui._license_label(), "License：MIT License")
        changelog = ui._find_changelog()
        self.assertTrue(changelog)
        self.assertTrue(os.path.isfile(changelog))
        preview = ui._changelog_preview_text(3)
        self.assertTrue(preview)
        self.assertNotIn("未找到", preview)
        self.assertIn("v0.", preview)
        self.assertTrue(preview.splitlines()[0].startswith("v"),
                        "更新日志预览最新版本应在最上面")

    def test_open_path_and_clash_candidates(self):
        with mock.patch.object(store.subprocess, "Popen") as popen:
            self.assertTrue(store.open_path(self.tmp))
            popen.assert_called_once_with(["explorer", self.tmp])
        with mock.patch.object(store.subprocess, "Popen") as popen:
            self.assertFalse(store.open_path(
                os.path.join(self.tmp, "not_here")))
            popen.assert_not_called()
        # Clash 自动候选：取第一个存在的路径（前面的候选不存在）
        candidate = _touch(os.path.join(self.tmp, "Clash", "clash-verge.exe"))
        cfg = os.path.join(self.tmp, "config.json")
        _write_json(cfg, {"version": 4, "root": self.tmp})
        search = os.path.join(self.tmp, "search_root")
        os.makedirs(search, exist_ok=True)
        with mock.patch.object(store, "CONFIG", cfg), \
                mock.patch.object(store, "SEARCH_ROOT", search), \
                mock.patch.object(store, "CLASH_CANDIDATES",
                                  [os.path.join(self.tmp, "missing.exe"),
                                   candidate]):
            _apps, clash, _root, _meta = store.load_state_full()
        self.assertEqual(os.path.normpath(clash), os.path.normpath(candidate))


class ChangelogFormatTests(unittest.TestCase):
    """v0.9 更新日志纯文本渲染：标题/列表/粗体/链接/多版本/截断/空文本。"""

    def test_sections_order_and_limit(self):
        raw = "\n".join([
            "# CHANGELOG",
            "## v0.8.0（2026-10-18）",
            "- 旧版本内容",
            "## v0.9.0 (2026-10-18)",
            "",
            "### 新增",
            "- **圆角 UI** 与 [链接](https://example.com)",
            "> 注意事项",
        ])
        text = ui.format_changelog_text(raw)
        self.assertIn("v0.9.0 · 2026-10-18", text)
        self.assertIn("v0.8.0 · 2026-10-18", text)
        self.assertLess(text.index("v0.9.0"), text.index("v0.8.0"),
                        "最新版本应排在最上面")
        self.assertIn("圆角 UI", text)
        self.assertIn("链接", text)
        self.assertIn("注意事项", text)
        for mark in ("**", "](", "`", "###", "# ", "- 圆角"):
            self.assertNotIn(mark, text)
        limited = ui.format_changelog_text(raw, 1)
        self.assertIn("v0.9.0", limited)
        self.assertNotIn("v0.8.0", limited)
        self.assertNotIn("旧版本内容", limited)
        self.assertEqual(ui.format_changelog_text(""), "")
        self.assertEqual(ui.format_changelog_text("   \n\n"), "")

    def test_plain_fallback(self):
        text = ui.format_changelog_text("### 新增\n- **圆角 UI**\n> 注意事项")
        self.assertIn("新增", text)
        self.assertIn("圆角 UI", text)
        self.assertIn("注意事项", text)
        for mark in ("###", "**", "> ", "- "):
            self.assertNotIn(mark, text)

    def test_markdown_helpers(self):
        markdown = ui._markdown_to_plain
        self.assertEqual(markdown("![图标](https://x/y.png) 文案"),
                         "图标 文案")
        self.assertEqual(markdown("[链接文字](https://x)"), "链接文字")
        self.assertEqual(markdown("<https://x>"), "")
        self.assertEqual(markdown("**粗体** __下划线__ `代码` ~~删除~~"),
                         "粗体 下划线 代码 删除")
        self.assertEqual(markdown("### 标题"), "标题")
        self.assertEqual(markdown("- 条目"), "条目")
        self.assertEqual(markdown("1. 条目"), "条目")
        self.assertEqual(markdown("> 引用"), "引用")
        self.assertEqual(markdown("---"), "")
        self.assertEqual(ui._markdown_body_to_plain("a\n\n\nb\n\n"),
                         "a\n\nb")


# ---------------------------------------------------------------- v0.9.1 图标资源
class V091IconTests(TempDirTest):
    """v0.9.1 图标资产：LinYuxia 品牌 + 四个页面图标（192×192）、映射、缺失回退。"""

    EXPECTED = (("brand", "LinYuxia.png"),
                ("home", "page_home.png"),
                ("daily", "page_daily.png"),
                ("settings", "page_settings.png"),
                ("about", "page_about.png"))

    @staticmethod
    def _copy(src, dst):
        with open(src, "rb") as fh:
            data = fh.read()
        with open(dst, "wb") as fh:
            fh.write(data)

    def test_icon_assets_exist_and_are_192(self):
        from PIL import Image
        for name, filename in self.EXPECTED:
            with self.subTest(name=name):
                path = os.path.join(store.ASSETS, filename)
                self.assertTrue(os.path.isfile(path), path)
                self.assertGreater(os.path.getsize(path), 0)
                with Image.open(path) as img:
                    self.assertEqual(img.size, (192, 192))
                    self.assertEqual(img.format, "PNG")
        self.assertEqual(ui.BRAND_ICON_FILE, "LinYuxia.png")
        self.assertEqual(ui.PAGE_ICON_FILES, {
            "home": "page_home.png", "daily": "page_daily.png",
            "settings": "page_settings.png", "about": "page_about.png"})

    def test_icon_mapping_and_size_tokens(self):
        for name, filename in self.EXPECTED:
            with self.subTest(name=name):
                self.assertEqual(ui.icon_asset_file(name), filename)
                path = ui.icon_path(name)
                self.assertEqual(os.path.normpath(path),
                                 os.path.normpath(os.path.join(
                                     store.ASSETS, filename)))
                self.assertTrue(os.path.isfile(path))
        self.assertEqual(ui.icon_asset_file("bogus"), "")
        self.assertEqual(ui.icon_path("bogus"), "")
        self.assertEqual(ui.resolve_icon_path("bogus"), "")
        sizes = ui.ICON_SIZES
        self.assertEqual((sizes["window"], sizes["window_small"]), (64, 32))
        self.assertTrue(44 <= sizes["brand"] <= 48)
        self.assertTrue(20 <= sizes["nav"] <= 22)
        self.assertTrue(28 <= sizes["page"] <= 32)
        self.assertGreaterEqual(sizes["about"], 48)

    def test_icon_missing_fallbacks(self):
        empty = os.path.join(self.tmp, "empty_assets")
        os.makedirs(empty, exist_ok=True)
        real_assets = store.ASSETS
        try:
            with mock.patch.object(store, "ASSETS", empty):
                # 空目录：图标路径与回退都为空，不崩溃
                self.assertEqual(ui.icon_path("brand"), "")
                self.assertEqual(ui.resolve_icon_path("brand"), "")
                self.assertEqual(ui.resolve_icon_path("home"), "")
                # 品牌缺失 -> 回退 hub.png
                self._copy(os.path.join(real_assets, "hub.png"),
                           os.path.join(empty, "hub.png"))
                self.assertEqual(
                    os.path.normpath(ui.resolve_icon_path("brand")),
                    os.path.normpath(os.path.join(empty, "hub.png")))
                # 页面图标没有回退
                self.assertEqual(ui.resolve_icon_path("home"), "")
                self._copy(os.path.join(real_assets, "page_home.png"),
                           os.path.join(empty, "page_home.png"))
                self.assertEqual(
                    os.path.normpath(ui.icon_path("home")),
                    os.path.normpath(os.path.join(empty, "page_home.png")))
                # 关于页回退顺序：page_about > LinYuxia > hub
                self.assertEqual(
                    os.path.normpath(ui.resolve_icon_path("about")),
                    os.path.normpath(os.path.join(empty, "hub.png")))
                self._copy(os.path.join(real_assets, "LinYuxia.png"),
                           os.path.join(empty, "LinYuxia.png"))
                self.assertEqual(
                    os.path.normpath(ui.resolve_icon_path("about")),
                    os.path.normpath(os.path.join(empty, "LinYuxia.png")))
                self._copy(os.path.join(real_assets, "page_about.png"),
                           os.path.join(empty, "page_about.png"))
                self.assertEqual(
                    os.path.normpath(ui.resolve_icon_path("about")),
                    os.path.normpath(os.path.join(empty, "page_about.png")))
        finally:
            store.ASSETS = real_assets


# ---------------------------------------------------------------- v0.10 异环/启动/字体/更新
class _FakeGameProc:
    def __init__(self, pid=1234, exit_code=None):
        self.pid = pid
        self._exit = exit_code

    def poll(self):
        return self._exit


class V010GameExeTests(TempDirTest):
    """v0.10 resolve_game_exe：异环 HTGame 优先/glob/迁移。"""

    @staticmethod
    def _file(path, size=200 * 1024):
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(b"MZ" + b"0" * max(0, size - 2))
        return path

    def test_nte_launcher_priority(self):
        launcher = self._file(os.path.join(self.tmp, "NTELauncher.exe"))
        body = self._file(os.path.join(self.tmp, *store.NTE_GAME_RELATIVE))
        app = {"key": "nte", "game": "异环", "game_exe": body,
               "script_exe": os.path.join(self.tmp, "script", "MaaNTE.exe"),
               "game_procs": ["htgame.exe"]}
        resolved = store.resolve_game_exe(app)
        self.assertEqual(os.path.normpath(resolved),
                         os.path.normpath(launcher))
        self.assertEqual(os.path.normpath(app["game_exe"]),
                         os.path.normpath(launcher))
        self.assertEqual([name.upper() for name in app["game_procs"]],
                         ["NTELAUNCHER.EXE"])
        # 已是启动器 -> 原样；其它游戏不改写
        self.assertEqual(store.resolve_game_exe(
            {"key": "nte", "game_exe": launcher}), launcher)
        self.assertEqual(store.resolve_game_exe(
            {"key": "wuwa", "game_exe": body}), body)

    def test_nte_missing_launcher_keeps_current(self):
        with tempfile.TemporaryDirectory(prefix="gh_nte_nol_") as root:
            body = self._file(os.path.join(root, *store.NTE_GAME_RELATIVE))
            app = {"key": "nte", "game": "异环", "game_exe": body}
            self.assertEqual(store.resolve_game_exe(app), body)
            self.assertEqual(app["game_exe"], body)
        self.assertEqual(store.resolve_game_exe({"key": "nte"}), "")

    def test_nte_candidate_scoring(self):
        hints = store.GAME_EXE_HINTS["nte"]
        self.assertEqual(hints[0].lower(), "ntelauncher.exe")
        base = os.path.join(self.tmp, "异环")
        launcher = self._file(os.path.join(base, "NTELauncher.exe"))
        body = self._file(os.path.join(base, *store.NTE_GAME_RELATIVE))
        keywords = store.GAME_KEYWORDS["nte"]
        hit_launcher = store._score_exe_path(launcher, 0, keywords, hints)
        hit_body = store._score_exe_path(body, 0, keywords, hints)
        self.assertTrue(hit_launcher)
        self.assertTrue(hit_body)
        self.assertGreater(hit_launcher["score"], hit_body["score"])

    def test_nte_candidate_discovery_launcher_first(self):
        with tempfile.TemporaryDirectory(prefix="gh_nte_cands_") as root:
            launcher = self._file(os.path.join(root, "NTELauncher.exe"))
            self._file(os.path.join(root, *store.NTE_GAME_RELATIVE))
            with mock.patch.object(store, "_iter_registry_entries",
                                   return_value=[]), \
                    mock.patch.object(store, "_fs_scan_roots",
                                      return_value=[(root, "异环")]):
                candidates = store.find_game_candidates(
                    {"key": "nte", "game": "异环"})
            self.assertTrue(candidates)
            self.assertEqual(os.path.basename(candidates[0]["path"]),
                             "NTELauncher.exe")
            self.assertEqual(os.path.normpath(candidates[0]["path"]),
                             os.path.normpath(launcher))

    def test_load_migration_nte(self):
        root = os.path.join(self.tmp, "cfgroot")
        os.makedirs(root, exist_ok=True)
        launcher = self._file(os.path.join(root, "NTELauncher.exe"))
        body = self._file(os.path.join(root, *store.NTE_GAME_RELATIVE))
        search = os.path.join(self.tmp, "search_root")
        os.makedirs(search, exist_ok=True)
        cfg = os.path.join(self.tmp, "config.json")
        _write_json(cfg, {"version": 4, "root": root,
                          "apps": {"nte": {"game_exe": body,
                                           "daily": {}}}})
        with mock.patch.object(store, "CONFIG", cfg), \
                mock.patch.object(store, "SEARCH_ROOT", search):
            apps, _clash, _root, _meta = store.load_state_full()
        nte = next(app for app in apps if app["key"] == "nte")
        self.assertEqual(os.path.normpath(nte["game_exe"]),
                         os.path.normpath(launcher))
        raw = json.load(open(cfg, "r", encoding="utf-8"))
        self.assertEqual(os.path.basename(raw["apps"]["nte"]["game_exe"]),
                         "NTELauncher.exe")
        # 找不到启动器时保留 HTGame
        root2 = os.path.join(self.tmp, "cfgroot2")
        os.makedirs(root2, exist_ok=True)
        body2 = self._file(os.path.join(root2, *store.NTE_GAME_RELATIVE))
        cfg2 = os.path.join(self.tmp, "config2.json")
        _write_json(cfg2, {"version": 4, "root": root2,
                           "apps": {"nte": {"game_exe": body2,
                                            "daily": {}}}})
        with mock.patch.object(store, "CONFIG", cfg2), \
                mock.patch.object(store, "SEARCH_ROOT", search):
            apps2, _c, _r, _m = store.load_state_full()
        nte2 = next(app for app in apps2 if app["key"] == "nte")
        self.assertEqual(os.path.basename(nte2["game_exe"]),
                         "HTGame.exe")


class V010GameLaunchTests(TempDirTest):
    """v0.10 build_game_launch：四款策略/exe/args/cwd/wait/fallback。"""

    @staticmethod
    def _file(path, size=200 * 1024):
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(b"MZ" + b"0" * max(0, size - 2))
        return path

    def test_wuwa_direct_game_exe(self):
        body = self._file(os.path.join(self.tmp, "Wuthering Waves Game",
                                       "Wuthering Waves.exe"))
        launcher = self._file(os.path.join(self.tmp, "launcher.exe"))
        app = {"key": "wuwa", "game": "鸣潮", "game_exe": launcher,
               "script_exe": os.path.join(self.tmp, "ok-ww.exe")}
        spec = store.build_game_launch(app)
        self.assertEqual(spec["strategy"], "exe")
        self.assertEqual(os.path.normpath(spec["exe"]),
                         os.path.normpath(body))
        self.assertEqual(spec["args"], ["-krqlv=hd"])
        self.assertEqual(os.path.normpath(spec["cwd"]),
                         os.path.normpath(os.path.dirname(body)))
        self.assertFalse(spec["elevated"])
        self.assertEqual(spec["wait"]["timeout_s"], 120)
        self.assertEqual(spec["wait"]["any_of"][0]["class_re"],
                         "^UnrealWindow$")
        self.assertEqual(spec["fallback"][0]["type"], "exe")
        self.assertEqual(os.path.normpath(spec["fallback"][0]["exe"]),
                         os.path.normpath(launcher))
        # ok-ww devices.json 中的 pc_full_path 也可发现
        dev = os.path.join(self.tmp, "dev")
        pc_exe = self._file(os.path.join(dev, "Game",
                                         "Wuthering Waves.exe"))
        script = os.path.join(dev, "ok-ww", "working", "main.py")
        self._file(script, size=16)
        _write_json(os.path.join(dev, "ok-ww", "configs", "devices.json"),
                    {"devices": [{"pc_full_path": pc_exe}]})
        spec2 = store.build_game_launch(
            {"key": "wuwa", "script_exe": script})
        self.assertEqual(os.path.normpath(spec2["exe"]),
                         os.path.normpath(pc_exe))

    def test_nte_launcher_and_fallback(self):
        launcher = self._file(os.path.join(self.tmp, "NTELauncher.exe"))
        body = self._file(os.path.join(self.tmp, *store.NTE_GAME_RELATIVE))
        spec = store.build_game_launch(
            {"key": "nte", "game": "异环", "game_exe": body})
        self.assertEqual(spec["strategy"], "launcher")
        self.assertEqual(os.path.normpath(spec["exe"]),
                         os.path.normpath(launcher))
        self.assertEqual(os.path.normpath(spec["cwd"]),
                         os.path.normpath(self.tmp))
        self.assertEqual(spec["args"], [])
        self.assertEqual(spec["wait"]["timeout_s"], 180)
        self.assertIn("异环", spec["wait"]["any_of"][0]["title_re"])
        self.assertIn("开始游戏", spec.get("hint", ""))
        self.assertEqual(spec["fallback"][0]["type"], "user_pick")
        # 找不到启动器：exe 为空 + user_pick 回退
        no_launcher = store.build_game_launch({"key": "nte", "game": "异环"})
        self.assertEqual(no_launcher["strategy"], "launcher")
        self.assertEqual(no_launcher["exe"], "")
        self.assertEqual(no_launcher["fallback"][0]["type"], "user_pick")

    def test_maaend_launcher_first(self):
        launcher = self._file(os.path.join(self.tmp, "Launcher.exe"))
        endfield = self._file(os.path.join(self.tmp, "games",
                                           "Endfield Game", "Endfield.exe"))
        with mock.patch.object(store, "_hypergryph_installs",
                               return_value=[]):
            spec = store.build_game_launch(
                {"key": "maaend", "game": "终末地", "game_exe": launcher})
        self.assertEqual(spec["strategy"], "launcher")
        self.assertEqual(os.path.normpath(spec["exe"]),
                         os.path.normpath(launcher))
        self.assertEqual(os.path.normpath(spec["cwd"]),
                         os.path.normpath(self.tmp))
        self.assertEqual(spec["wait"]["timeout_s"], 180)
        self.assertEqual(spec["wait"]["any_of"][0]["title_re"], "Endfield")
        self.assertEqual(os.path.normpath(spec["fallback"][0]["exe"]),
                         os.path.normpath(endfield))
        self.assertIn("启动器", spec.get("hint", ""))

    def test_maa_pc_branch(self):
        exe = self._file(os.path.join(self.tmp, "MAA.exe"))
        arknights = self._file(os.path.join(self.tmp, "games",
                                            "Arknights Game",
                                            "Arknights.exe"))
        _write_json(os.path.join(self.tmp, "gui.new.json"), {
            "Configurations": {"Default": {"Gui": {
                "StartUpSettings": {"PcClientPath": arknights,
                                    "PcClientWaitSeconds": 90},
                "ConnectSettings": {"Config": "PC"}}}}})
        with mock.patch.object(store, "_hypergryph_installs",
                               return_value=[]):
            spec = store.build_game_launch({"key": "maa",
                                            "script_exe": exe})
        self.assertEqual(spec["strategy"], "maa_pc")
        self.assertEqual(os.path.normpath(spec["exe"]),
                         os.path.normpath(arknights))
        self.assertEqual(spec["wait"]["timeout_s"], 90)
        self.assertEqual(spec["wait"]["any_of"][0]["title_re"], "明日方舟")
        self.assertEqual(spec["args"], [])

    def test_maa_adb_branch(self):
        exe = self._file(os.path.join(self.tmp, "MAA.exe"))
        emu = self._file(os.path.join(self.tmp, "MuMu",
                                      "MuMuPlayer.exe"))
        adb = self._file(os.path.join(self.tmp, "adb.exe"))
        _write_json(os.path.join(self.tmp, "gui.new.json"), {
            "Gui": {
                "StartUpSettings": {
                    "EmulatorPath": emu, "EmulatorWaitSeconds": 45,
                    "AdbPath": adb, "AdbSerial": "127.0.0.1:16384"},
                "ConnectSettings": {"Config": "MuMuEmulator12"}}})
        with mock.patch.object(store, "_hypergryph_installs",
                               return_value=[]):
            spec = store.build_game_launch({"key": "maa",
                                            "script_exe": exe})
        self.assertEqual(spec["strategy"], "maa_adb")
        self.assertEqual(os.path.normpath(spec["exe"]),
                         os.path.normpath(emu))
        self.assertEqual(spec["adb"]["serial"], "127.0.0.1:16384")
        self.assertEqual(spec["adb"]["path"], os.path.normpath(adb))
        self.assertEqual(spec["adb"]["package"], "com.hypergryph.arknights")
        self.assertEqual(spec["wait"]["timeout_s"], 45)

    def test_missing_files_user_pick(self):
        with mock.patch.object(store, "_hypergryph_installs",
                               return_value=[]):
            wuwa = store.build_game_launch({"key": "wuwa", "game": "鸣潮"})
            nte = store.build_game_launch({"key": "nte", "game": "异环"})
            maaend = store.build_game_launch({"key": "maaend",
                                              "game": "终末地"})
        self.assertEqual(wuwa["exe"], "")
        self.assertEqual(wuwa["args"], [])
        self.assertEqual([item["type"] for item in wuwa["fallback"]],
                         ["user_pick"])
        self.assertEqual(nte["exe"], "")
        self.assertEqual([item["type"] for item in nte["fallback"]],
                         ["user_pick"])
        self.assertEqual(maaend["strategy"], "launcher")
        self.assertEqual(maaend["exe"], "")
        self.assertEqual(maaend["fallback"][0]["type"], "user_pick")
        # 自定义游戏保持现有 game_exe 直接启动
        custom = store.build_game_launch(
            {"key": "custom_1", "game_exe": r"D:\Games\game.exe"})
        self.assertEqual(custom["strategy"], "exe")
        self.assertEqual(custom["exe"], r"D:\Games\game.exe")
        self.assertEqual(custom["wait"]["any_of"], [])
        self.assertEqual(custom["fallback"][0]["type"], "user_pick")


class V010WaitLaunchTests(unittest.TestCase):
    """v0.10 等待器：成功/超时/提前退出 + 启动→等待→回退（spawn mock）。"""

    def test_wait_success(self):
        spec = {"wait": {"timeout_s": 5, "poll_ms": 100}}
        calls = []
        ok, reason = store.wait_game_launched(
            {"key": "wuwa"}, spec, state_fn=lambda: True,
            sleep_fn=lambda seconds: calls.append(seconds),
            clock_fn=lambda: 0.0)
        self.assertEqual((ok, reason), (True, ""))
        self.assertEqual(calls, [])

    def test_wait_timeout(self):
        spec = {"wait": {"timeout_s": 0.2, "poll_ms": 50}}
        times = iter([0.0, 0.1, 0.2, 0.3, 0.4])
        ok, reason = store.wait_game_launched(
            {"key": "wuwa"}, spec, state_fn=lambda: False,
            sleep_fn=lambda seconds: None,
            clock_fn=lambda: next(times, 10.0))
        self.assertFalse(ok)
        self.assertIn("超时", reason)

    def test_wait_process_early_exit(self):
        spec = {"wait": {"timeout_s": 5, "poll_ms": 50}}
        times = iter([0.0, 0.1, 0.2, 0.3])
        ok, reason = store.wait_game_launched(
            {"key": "wuwa"}, spec, state_fn=lambda: False,
            sleep_fn=lambda seconds: None,
            clock_fn=lambda: next(times, 10.0),
            process=_FakeGameProc(exit_code=1))
        self.assertFalse(ok)
        self.assertIn("提前退出", reason)

    def test_launch_game_with_wait_and_fallback(self):
        spec = {"strategy": "exe", "exe": "game.exe", "args": ["-x"],
                "cwd": r"C:\Game",
                "wait": {"timeout_s": 1, "poll_ms": 100},
                "fallback": [{"type": "exe", "exe": "launcher.exe",
                              "hint": "已打开启动器"}]}
        calls = []

        def spawn(exe, args=None, cwd=""):
            calls.append((exe, list(args or []), cwd))
            return _FakeGameProc(pid=99), ""
        result = store.launch_game_with_wait(
            {"key": "wuwa"}, spec, spawn_fn=spawn,
            state_fn=lambda: True, sleep_fn=lambda seconds: None,
            clock_fn=lambda: 0.0)
        self.assertTrue(result["ok"])
        self.assertEqual(result["pid"], 99)
        self.assertEqual(calls[0], ("game.exe", ["-x"], r"C:\Game"))
        self.assertEqual(calls, [calls[0]])
        # 超时 -> 回退启动器
        calls.clear()
        times = iter([0.0, 0.1, 0.2, 0.3, 0.4, 0.5])
        result2 = store.launch_game_with_wait(
            {"key": "wuwa"}, spec, spawn_fn=spawn,
            state_fn=lambda: False, sleep_fn=lambda seconds: None,
            clock_fn=lambda: next(times, 10.0))
        self.assertFalse(result2["ok"])
        self.assertEqual(result2["fallback"]["type"], "exe")
        self.assertIn("启动器", result2["fallback"]["hint"])
        self.assertEqual(calls[-1][0], "launcher.exe")
        self.assertEqual(calls[-1][1], [])
        # spawn 失败 -> 直接失败，不等待
        result3 = store.launch_game_with_wait(
            {"key": "wuwa"}, spec,
            spawn_fn=lambda *args, **kwargs: (None, "启动失败"),
            state_fn=lambda: True, sleep_fn=lambda seconds: None,
            clock_fn=lambda: 0.0)
        self.assertFalse(result3["ok"])
        self.assertEqual(result3["reason"], "启动失败")


class V010SettingsThemeTests(unittest.TestCase):
    """v0.10 font_scale / 淡紫默认 / 圆角渐变令牌 / 标题栏纯逻辑。"""

    def test_font_scale_clean_and_mapping(self):
        self.assertEqual(store.FONT_SCALES, (0.9, 1.0, 1.12, 1.25))
        self.assertEqual(store._clean_settings({})["font_scale"], 1.0)
        for scale in store.FONT_SCALES:
            with self.subTest(scale=scale):
                self.assertEqual(store._clean_settings(
                    {"font_scale": scale})["font_scale"], float(scale))
        for bad in (2.0, 0.8, "1.0", True, None):
            with self.subTest(bad=bad):
                self.assertEqual(store._clean_settings(
                    {"font_scale": bad})["font_scale"], 1.0)
        self.assertEqual(ui.window_scale_value(0.9), 0.9)
        self.assertEqual(ui.window_scale_value(1.12), 1.12)
        self.assertEqual(ui.window_scale_value(2.0), 1.0)
        self.assertEqual(ui.window_scale_value(None), 1.0)
        self.assertEqual(ui.window_scale_value("bad"), 1.0)
        self.assertEqual(ui.window_scale_value("bad", 0.9), 0.9)

    def test_scaled_font(self):
        with mock.patch.object(ui, "_FONT_SCALE", 1.0):
            self.assertEqual(ui._scaled_font(-11), (theme.UI_FONT, -11))
            self.assertEqual(ui._scaled_font("bad"), (theme.UI_FONT, -11))
        with mock.patch.object(ui, "_FONT_SCALE", 1.12):
            self.assertEqual(ui._scaled_font(-11), (theme.UI_FONT, -12))
            self.assertEqual(ui._scaled_font(10), (theme.UI_FONT, -11))
        with mock.patch.object(ui, "_FONT_SCALE", 1.25):
            self.assertEqual(ui._scaled_font(-11), (theme.UI_FONT, -14))

    def test_new_theme_tokens(self):
        self.assertEqual(store.NEW_DEFAULT_ACCENT, "#b98bff")
        self.assertEqual(theme.UI_ACCENT, "#b98bff")
        self.assertEqual(theme.ACCENT_PRESETS[0], ("淡紫", "#b98bff"))
        purple_presets = [color for name, color in theme.ACCENT_PRESETS
                          if "紫" in name]
        self.assertGreaterEqual(len(purple_presets), 3)
        self.assertEqual(theme.RADIUS_PANEL, 16)
        self.assertEqual(theme.RADIUS_BUTTON, 13)
        self.assertEqual(theme.RADIUS_INPUT, 10)
        self.assertEqual((theme.SPACE_UI_XS, theme.SPACE_UI_SM,
                          theme.SPACE_UI_MD, theme.SPACE_UI_LG,
                          theme.SPACE_UI_XL), (10, 14, 18, 22, 26))
        self.assertEqual(theme.TITLEBAR_H, 44)
        for name in ("UI_GRADIENT_TOP", "UI_GRADIENT_SIDEBAR_TOP",
                     "UI_GRADIENT_SIDEBAR_BOTTOM"):
            with self.subTest(name=name):
                self.assertRegex(getattr(theme, name), r"^#[0-9a-fA-F]{6}$")
        self.assertNotEqual(theme.UI_GRADIENT_TOP, theme.UI_BG)

    def test_titlebar_buttons_and_close_mapping(self):
        normal = ui.titlebar_buttons(False)
        self.assertEqual(normal, {"maximized": False, "minimize": "—",
                                  "maximize": "□", "close": "✕"})
        maximized = ui.titlebar_buttons(True)
        self.assertTrue(maximized["maximized"])
        self.assertEqual(maximized["maximize"], "❐")
        self.assertEqual(maximized["close"], "✕")
        # 关闭行为映射（设置清洗）+ 最小窗口尺寸
        self.assertEqual(store._clean_settings(
            {"close_action": "minimize"})["close_action"], "minimize")
        self.assertEqual(store._clean_settings(
            {"close_action": "EXIT"})["close_action"], "exit")
        self.assertEqual(store._clean_settings(
            {"close_action": "explode"})["close_action"], "exit")
        self.assertEqual((theme.MIN_W, theme.MIN_H), (1000, 640))

    def test_auto_download_update_settings(self):
        defaults = store.DEFAULT_SETTINGS
        self.assertFalse(defaults["auto_download_update"])
        self.assertEqual(defaults["font_scale"], 1.0)
        self.assertTrue(store._clean_settings(
            {"auto_download_update": True})["auto_download_update"])
        self.assertFalse(store._clean_settings(
            {"auto_download_update": False})["auto_download_update"])
        for bad in ("true", 1, None, "yes"):
            with self.subTest(bad=bad):
                self.assertFalse(store._clean_settings(
                    {"auto_download_update": bad})["auto_download_update"])


class V010SettingsRoundTripTests(TempDirTest):
    """v0.10 settings 新增 font_scale / auto_download_update 往返与旧配置兼容。"""

    def test_settings_roundtrip_new_fields(self):
        apps = [store.make_builtin("maa", self.tmp)]
        cfg = os.path.join(self.tmp, "config.json")
        search = os.path.join(self.tmp, "search_root")
        os.makedirs(search, exist_ok=True)
        settings = {"accent": "#b98bff", "font_scale": 1.12,
                    "auto_download_update": True}
        with mock.patch.object(store, "CONFIG", cfg), \
                mock.patch.object(store, "SEARCH_ROOT", search):
            self.assertTrue(store.save_state(apps, clash="", root=self.tmp,
                                             settings=settings))
            raw = json.load(open(cfg, "r", encoding="utf-8"))
            self.assertEqual(raw["settings"]["font_scale"], 1.12)
            self.assertTrue(raw["settings"]["auto_download_update"])
            self.assertEqual(raw["settings"]["accent"], "#b98bff")
            _apps, _clash, _root, meta = store.load_state_full()
        self.assertEqual(meta["settings"]["font_scale"], 1.12)
        self.assertTrue(meta["settings"]["auto_download_update"])
        self.assertEqual(meta["settings"]["accent"], "#b98bff")
        # 旧配置没有新增字段 -> 默认值
        _write_json(cfg, {"version": 4, "root": self.tmp, "apps": {}})
        with mock.patch.object(store, "CONFIG", cfg), \
                mock.patch.object(store, "SEARCH_ROOT", search):
            _a, _c, _r, meta2 = store.load_state_full()
        self.assertEqual(meta2["settings"]["font_scale"], 1.0)
        self.assertFalse(meta2["settings"]["auto_download_update"])


class V010AutoUpdateTests(unittest.TestCase):
    """v0.10 自动更新纯逻辑：资产选择 / updater 脚本引号 / 门控 / 版本。"""

    def test_select_update_asset(self):
        payload = {"assets": [
            {"name": "notes.txt", "url": "u0"},
            {"name": "GameHub.exe", "url": "exe", "size": "456"},
            {"name": "AllMyMaa-v0.10.0.zip", "url": "zip", "size": 789},
            "not-a-dict",
        ]}
        selected = ui.select_update_asset(payload)
        self.assertEqual(selected["kind"], "exe")
        self.assertEqual(selected["name"], "GameHub.exe")
        self.assertEqual(selected["size"], 456)
        # 无 exe 时选 zip
        zip_selected = ui.select_update_asset({"assets": [
            {"name": "other.zip", "url": "z1"},
            {"name": "AllMyMaa-v0.10.0.zip", "url": "z2"}]})
        self.assertEqual(zip_selected["kind"], "zip")
        self.assertEqual(zip_selected["name"], "AllMyMaa-v0.10.0.zip")
        self.assertIsNone(ui.select_update_asset({}))
        self.assertIsNone(ui.select_update_asset("bad"))
        self.assertIsNone(ui.select_update_asset({"assets": [
            {"name": "notes.txt", "url": "u"}]}))
        self.assertIsNone(ui.select_update_asset({"assets": [
            {"name": "no-url.exe"}]}))

    def test_build_updater_script_quotes_paths(self):
        target = r"C:\Program Files\All My Maa\O'Brien\AllMyMaa.exe"
        new_exe = r"C:\Temp\new dir\AllMyMaa.exe"
        script = ui.build_updater_script(4321, new_exe, target)
        self.assertIn("Wait-Process -Id 4321 -Timeout 60", script)
        self.assertIn("\r\n", script)
        self.assertIn("-LiteralPath 'C:\\Program Files\\All My Maa\\"
                      "O''Brien\\AllMyMaa.exe'", script)
        self.assertIn(".bak", script)
        self.assertIn(".new", script)
        self.assertIn("Move-Item -LiteralPath", script)
        self.assertIn("Start-Process -FilePath", script)
        self.assertIn("'C:\\Temp\\new dir\\AllMyMaa.exe'", script)
        # pid 非法 -> 0
        self.assertIn("Wait-Process -Id 0 ", ui.build_updater_script(
            None, new_exe, target))

    def test_update_gates(self):
        self.assertTrue(ui.can_auto_update(True, True))
        self.assertFalse(ui.can_auto_update(False, True))
        self.assertFalse(ui.can_auto_update(True, False))
        self.assertTrue(ui.should_source_update(True, True))
        self.assertFalse(ui.should_source_update(True, False))
        self.assertFalse(ui.should_source_update(False, True))
        self.assertTrue(ui.update_available("0.9.0", "v0.10.0"))
        self.assertTrue(ui.update_available("v0.9.0", "0.10.0"))
        self.assertFalse(ui.update_available("0.10.0", "v0.10.0"))
        self.assertFalse(ui.update_available("0.10.1", "v0.10.0"))
        self.assertFalse(ui.update_available("", "v0.10.0"))


# ---------------------------------------------------------------- v0.10.1 异环 hotfix
class V0103ElevationTests(TempDirTest):
    """v0.10.3 默认管理员启动：提权决策/自重启命令/状态/打包 manifest/入口诊断。"""

    def test_should_elevate_matrix(self):
        should = elevation.should_elevate
        self.assertTrue(should(False, [], {}, False))
        self.assertFalse(should(True, [], {}, False))
        self.assertFalse(should(False, [], {}, True))
        self.assertFalse(should(False, ["--no-elevate"], {}, False))
        self.assertFalse(should(False, ["--elevated"], {}, False))
        for value in ("1", "true", "YES", " on "):
            with self.subTest(value=value):
                self.assertFalse(should(False, [],
                                        {"GAMEHUB_NO_ELEVATE": value}, False))
        for value in ("0", "false", "", "no", "off"):
            with self.subTest(value=value):
                self.assertTrue(should(False, [],
                                       {"GAMEHUB_NO_ELEVATE": value}, False))
        self.assertTrue(should(False, ["--some-arg"], {}, False))
        self.assertFalse(should(True, ["--no-elevate"], {}, True))
        # _env_flag 大小写/空白归一
        self.assertTrue(elevation._env_flag({"X": " TRUE "}, "X"))
        self.assertFalse(elevation._env_flag({"X": "off"}, "X"))
        self.assertFalse(elevation._env_flag(None, "X"))

    def test_pythonw_path(self):
        pw = _touch(os.path.join(self.tmp, "pythonw.exe"), b"")
        py = _touch(os.path.join(self.tmp, "python.exe"), b"")
        self.assertEqual(os.path.normpath(elevation.pythonw_path(py)),
                         os.path.normpath(pw))
        self.assertEqual(os.path.normpath(elevation.pythonw_path(pw)),
                         os.path.normpath(pw))
        other = _touch(os.path.join(self.tmp, "only", "python.exe"), b"")
        self.assertEqual(os.path.normpath(elevation.pythonw_path(other)),
                         os.path.normpath(other))
        # 当前解释器优先找同目录 pythonw.exe；空路径同 None
        self.assertEqual(os.path.basename(elevation.pythonw_path(None)).lower(),
                         "pythonw.exe")
        self.assertEqual(elevation.pythonw_path(None),
                         elevation.pythonw_path(""))

    def test_build_relaunch_spec(self):
        hub = os.path.join(self.tmp, "hub dir", "hub.pyw")
        app_dir = os.path.join(self.tmp, "app dir")
        os.makedirs(app_dir, exist_ok=True)
        pw = _touch(os.path.join(self.tmp, "pythonw.exe"), b"")
        spec = elevation.build_relaunch(hub, app_dir, pythonw=pw,
                                        extra_args=["--no-elevate", "x"])
        self.assertEqual(spec["verb"], "runas")
        self.assertEqual(os.path.normpath(spec["file"]),
                         os.path.normpath(pw))
        self.assertEqual(spec["params"],
                         f'"{os.path.abspath(hub)}" --elevated --no-elevate x')
        self.assertEqual(spec["cwd"], os.path.abspath(app_dir))
        self.assertEqual(spec["show"], 1)
        # 默认 cwd = hub 所在目录；无空格的 hub 路径也始终加引号
        simple = os.path.join(self.tmp, "hub.pyw")
        spec2 = elevation.build_relaunch(simple, pythonw=pw)
        self.assertEqual(spec2["cwd"],
                         os.path.abspath(os.path.dirname(simple)))
        self.assertTrue(spec2["params"].startswith(
            '"' + os.path.abspath(simple) + '" --elevated'))

    def test_elevation_status(self):
        with mock.patch.object(elevation, "is_admin", return_value=True):
            status = elevation.elevation_status([], {}, False)
        self.assertTrue(status["admin"])
        self.assertFalse(status["frozen"])
        self.assertFalse(status["would_elevate"])
        self.assertTrue(status["pythonw"])
        with mock.patch.object(elevation, "is_admin", return_value=False):
            self.assertTrue(elevation.elevation_status([], {}, False)
                            ["would_elevate"])
            self.assertFalse(elevation.elevation_status(
                ["--no-elevate"], {}, False)["would_elevate"])
            self.assertFalse(elevation.elevation_status(
                [], {"GAMEHUB_NO_ELEVATE": "1"}, False)["would_elevate"])
            frozen = elevation.elevation_status([], {}, True)
        self.assertTrue(frozen["frozen"])
        self.assertFalse(frozen["would_elevate"])
        self.assertIn(elevation.is_admin(), (True, False))

    def test_hub_elevation_check_cli(self):
        env = dict(os.environ)
        env.pop("GAMEHUB_NO_ELEVATE", None)
        hub = os.path.join(REPO_ROOT, "hub.pyw")
        proc = subprocess.run(
            [sys.executable, hub, "--elevation-check"], cwd=REPO_ROOT,
            env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0)
        self.assertNotIn("Traceback", proc.stderr)
        data = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertIsInstance(data.get("admin"), bool)
        self.assertIsInstance(data.get("frozen"), bool)
        self.assertIsInstance(data.get("pythonw"), str)
        self.assertEqual(data.get("would_elevate"),
                         not elevation.is_admin())
        # 环境变量 / --no-elevate 让诊断结果跳过提权
        env2 = dict(env, GAMEHUB_NO_ELEVATE="1")
        proc2 = subprocess.run(
            [sys.executable, hub, "--elevation-check"], cwd=REPO_ROOT,
            env=env2, capture_output=True, text=True, timeout=30)
        data2 = json.loads(proc2.stdout.strip().splitlines()[-1])
        self.assertFalse(data2.get("would_elevate"))
        proc3 = subprocess.run(
            [sys.executable, hub, "--elevation-check", "--no-elevate"],
            cwd=REPO_ROOT, env=env, capture_output=True, text=True,
            timeout=30)
        data3 = json.loads(proc3.stdout.strip().splitlines()[-1])
        self.assertFalse(data3.get("would_elevate"))

    def test_not_admin_message_mocked(self):
        with mock.patch.object(elevation, "ctypes") as fake_ctypes:
            elevation.not_admin_message()
        call = fake_ctypes.windll.user32.MessageBoxW.call_args
        self.assertIsNotNone(call)
        args = call.args
        self.assertEqual(args[0], 0)
        self.assertIn("未获得管理员权限", args[1])
        self.assertIn("普通权限", args[1])
        self.assertIn("权限提示", args[2])
        self.assertEqual(args[3], 0x00000040)

    def test_build_manifest_flags(self):
        bat = open(os.path.join(REPO_ROOT, "tools", "build_exe.bat"),
                   "r", encoding="utf-8", errors="replace").read()
        yml = open(os.path.join(REPO_ROOT, ".github", "workflows",
                                "build-exe.yml"),
                   "r", encoding="utf-8", errors="replace").read()
        for name, text in (("build_exe.bat", bat), ("workflow", yml)):
            with self.subTest(file=name):
                self.assertIn("--uac-admin", text)
                self.assertIn("--onefile", text)
                self.assertIn("--windowed", text)
                self.assertIn("--icon", text)
                self.assertIn("--add-data", text)
                self.assertIn("hub.pyw", text)
                self.assertIn("GameHub", text)
        self.assertIn("assets\\hub.ico", bat)
        self.assertIn("assets/hub.ico", yml)

    def test_ui_permission_strings_and_hub_flow(self):
        ui_src = open(os.path.join(REPO_ROOT, "gamehub", "ui.py"),
                      "r", encoding="utf-8").read()
        self.assertIn("当前权限：", ui_src)
        self.assertIn("管理员", ui_src)
        self.assertIn("普通用户", ui_src)
        self.assertIn("默认以管理员身份启动", ui_src)
        self.assertIn("store.hub_is_elevated()", ui_src)
        hub_src = open(os.path.join(REPO_ROOT, "hub.pyw"),
                       "r", encoding="utf-8").read()
        for mark in ("--elevation-check", "--no-elevate",
                     "should_elevate(", "relaunch_as_admin(",
                     "not_admin_message(", "GAMEHUB_NO_ELEVATE"):
            with self.subTest(mark=mark):
                self.assertIn(mark, hub_src)
        elev_src = open(os.path.join(REPO_ROOT, "gamehub", "elevation.py"),
                        "r", encoding="utf-8").read()
        self.assertIn("--elevated", elev_src)
        self.assertIn("--no-elevate", elev_src)
        # 提权决策必须早于 Pillow 检查与 UI 导入
        self.assertLess(hub_src.index("should_elevate("),
                        hub_src.index("import PIL"))
        self.assertLess(hub_src.index("should_elevate("),
                        hub_src.index("from gamehub.ui import run"))


# ---------------------------------------------------------------- v0.10.4 异环回 MXU autostart
class V0104RevertTests(TempDirTest):
    """v0.10.4 异环清日常回 MXU 同款：命令形状/实例推断/旧热键-UIPI 无残留。"""

    def _patches(self):
        return (
            mock.patch.object(store, "snapshot_processes", return_value=set()),
            mock.patch.object(daily, "_game_running", return_value=True),
        )

    def test_mxu_ui_and_uipi_removed(self):
        for name in ("mxu_ui_hotkey", "mxu_latest_log", "mxu_autostart_instance",
                     "mxu_target_elevated", "mxu_ui_hint", "_plan_mxu_ui",
                     "_run_mxu_ui", "_mxu_ui_window", "MXU_UI_DONE_MARKERS",
                     "MXU_UI_FAIL_MARKERS", "MXU_UI_NOTE"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(daily, name),
                                 f"旧热键/UIPI 符号残留: {name}")
        app = _make_mxu_daily(self.tmp, "nte")
        p1, p2 = self._patches()
        with p1, p2:
            plan = daily.plan_for(app)
        for key in ("hotkey", "use_hotkey", "manual_start", "manual_reason",
                    "target_elevated", "elevated", "attach",
                    "autostart_instance"):
            with self.subTest(key=key):
                self.assertNotIn(key, plan)
        daily_src = open(os.path.join(REPO_ROOT, "gamehub", "daily.py"),
                         "r", encoding="utf-8").read()
        ui_src = open(os.path.join(REPO_ROOT, "gamehub", "ui.py"),
                      "r", encoding="utf-8").read()
        for text, label in ((daily_src, "daily.py"), (ui_src, "ui.py")):
            for mark in ("mxu_ui", "mxu_ui_hint", "mxu_target_elevated",
                         "Ctrl+F10", "Ctrl + F10", "UIPI"):
                with self.subTest(file=label, mark=mark):
                    self.assertNotIn(mark, text)

    def test_instance_inference_autostart_and_override(self):
        app = _make_mxu_daily(self.tmp, "nte")
        cfg = daily.mxu_paths(app)["config"]
        # autoStartInstanceId 按 id 匹配
        _write_json(cfg, {
            "settings": {"autoStartInstanceId": "cfg-two"},
            "instances": [
                {"id": "cfg-one", "name": "实例一",
                 "tasks": [{"enabled": True}]},
                {"id": "cfg-two", "name": "实例二",
                 "tasks": [{"enabled": True}]}]})
        self.assertEqual(
            daily._suggest_mxu_instance(app, daily.mxu_instances(app)),
            "实例二")
        # autoStartInstanceId 按 uuid / name 匹配
        _write_json(cfg, {
            "settings": {"autoStartInstanceId": "uuid-9"},
            "instances": [{"uuid": "uuid-9", "name": "实例九",
                           "tasks": [{"enabled": True}]}]})
        self.assertEqual(
            daily._suggest_mxu_instance(app, daily.mxu_instances(app)),
            "实例九")
        _write_json(cfg, {
            "settings": {"autoStartInstanceId": "实例一"},
            "instances": [{"name": "实例一", "tasks": [{"enabled": True}]}]})
        self.assertEqual(
            daily._suggest_mxu_instance(app, daily.mxu_instances(app)),
            "实例一")
        # 无 autoStart：取第一个有启用任务的实例（跳过 0 任务）
        _write_json(cfg, {"instances": [
            {"name": "无任务", "tasks": [{"enabled": False}]},
            {"name": "有任务", "tasks": [{"enabled": True}]}]})
        self.assertEqual(
            daily._suggest_mxu_instance(app, daily.mxu_instances(app)),
            "有任务")
        # 无实例 / 全部未启用 -> ""
        _write_json(cfg, {"instances": []})
        self.assertEqual(
            daily._suggest_mxu_instance(app, daily.mxu_instances(app)), "")
        _write_json(cfg, {"instances": [
            {"name": "空", "tasks": [{"enabled": False}]}]})
        self.assertEqual(
            daily._suggest_mxu_instance(app, daily.mxu_instances(app)), "")
        # 用户显式实例覆盖 autoStart 推断
        _write_json(cfg, {
            "settings": {"autoStartInstanceId": "cfg-two"},
            "instances": [
                {"id": "cfg-one", "name": "实例一",
                 "tasks": [{"enabled": True}]},
                {"id": "cfg-two", "name": "实例二",
                 "tasks": [{"enabled": True}]}]})
        app["daily"] = store._clean_daily({"instance": "实例一"}, "nte")
        p1, p2 = self._patches()
        with p1, p2:
            plan = daily.plan_for(app)
        self.assertEqual(plan["args"],
                         ["--autostart", "--instance", "实例一",
                          "--quit-after-run"])
        self.assertIn('--instance "实例一"', plan["params"])

    def test_nte_maaend_plan_parity(self):
        nte = _make_mxu_daily(self.tmp, "nte")
        maaend = _make_mxu_daily(self.tmp, "maaend")
        p1, p2 = self._patches()
        with p1, p2:
            nte_plan = daily.plan_for(nte)
            maaend_plan = daily.plan_for(maaend)
        for plan, exe_name, timeout in ((nte_plan, "MaaNTE.exe", 120),
                                        (maaend_plan, "MaaEnd.exe", 150)):
            with self.subTest(exe=exe_name):
                self.assertEqual(plan["mode"], "mxu")
                self.assertEqual(plan["args"][:1], ["--autostart"])
                self.assertIn("--instance", plan["args"])
                self.assertEqual(plan["args"][-1], "--quit-after-run")
                self.assertEqual(plan["argv"][0], plan["exe"])
                self.assertEqual(plan["argv"][1:4], [
                    "--autostart", "--instance",
                    plan["settings"]["instance"]])
                self.assertTrue(plan["params"].endswith("--quit-after-run"))
                self.assertIn("--instance ", plan["params"])
                self.assertEqual(plan["timeout_min"], timeout)
                self.assertIn(exe_name, plan["command_text"])
                self.assertEqual(plan["errors"], [])
        # 默认实例推断：异环「挂机任务」/ 终末地「全套日常」
        self.assertEqual(nte_plan["settings"]["instance"], "挂机任务")
        self.assertEqual(maaend_plan["settings"]["instance"], "全套日常")
        # 清日常顺序/勾选仍包含异环与终末地（v0.8 行为无回归）
        apps = [nte, maaend]
        self.assertIn("nte", daily.enabled_daily_keys(
            apps, store.DEFAULT_DAILY_ORDER))
        self.assertIn("maaend", daily.enabled_daily_keys(
            apps, store.DEFAULT_DAILY_ORDER))


def main():
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("\n===== 汇总 =====")
    print(f"用例数: {result.testsRun}  "
          f"失败: {len(result.failures)}  "
          f"错误: {len(result.errors)}  "
          f"跳过: {len(result.skipped)}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
