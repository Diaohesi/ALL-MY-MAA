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
* 不依赖网络：http_get / check_latest 等联网函数不在此测试范围内。
"""
import json
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

# 保证从任意 CWD 运行都能 import gamehub
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from gamehub import detector, render, store, theme  # noqa: E402

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
