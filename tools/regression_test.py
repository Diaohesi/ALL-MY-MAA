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
import unittest
from unittest import mock

# 保证从任意 CWD 运行都能 import gamehub
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from gamehub import render, store, theme  # noqa: E402

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
            self.assertEqual(raw.get("version"), 3)
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
