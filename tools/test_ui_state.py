# -*- coding: utf-8 -*-
"""v0.8 UI 状态自测（不启动 GUI 主循环、不启动脚本/游戏）。

覆盖：
- settings 清洗 / 持久化往返、refresh interval 应用
- 清日常勾选过滤、daily_order 顺序
- DailyManager 每游戏独立状态（单游戏互斥、队列顺序/跳过）
"""
import json
import os
import sys
import tempfile
import threading
import time
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from gamehub import daily, store, ui  # noqa: E402

failures = []


def check(label, got, expected):
    ok = got == expected
    print(("OK   " if ok else "FAIL ") + f"{label}: {got!r}")
    if not ok:
        failures.append(f"{label}: got {got!r}, expect {expected!r}")


# ---------------------------------------------------------------- settings
def test_settings_clean():
    print("\n=== settings 清洗 ===")
    defaults = store._clean_settings(None)
    check("缺省 accent", defaults["accent"], "#4fc3ff")
    check("缺省刷新间隔", defaults["refresh_interval"], 1.5)
    check("缺省关闭行为", defaults["close_action"], "exit")

    cleaned = store._clean_settings({
        "accent": "#B98BFF", "check_update_on_start": False,
        "refresh_interval": 2.0, "close_action": "minimize",
        "clash_exe": r"C:\Clash\clash-verge.exe",
        "daily_default_timeout": 9999, "daily_show_preview": False,
        "adb_enabled": True, "daily_close_after": False,
    })
    check("accent 小写归一", cleaned["accent"], "#b98bff")
    check("check_update_on_start", cleaned["check_update_on_start"], False)
    check("refresh 2.0 保留", cleaned["refresh_interval"], 2.0)
    check("close_action minimize", cleaned["close_action"], "minimize")
    check("默认超时上限", cleaned["daily_default_timeout"], 600)
    check("adb_enabled", cleaned["adb_enabled"], True)
    check("daily_show_preview", cleaned["daily_show_preview"], False)

    bad = store._clean_settings({
        "accent": "red", "refresh_interval": 7, "close_action": "explode",
        "daily_default_timeout": -3, "enabled": "true"})
    check("非法 accent 回退", bad["accent"], "#4fc3ff")
    check("非法刷新间隔回退", bad["refresh_interval"], 1.5)
    check("非法关闭行为回退", bad["close_action"], "exit")
    check("负超时回退最小值", bad["daily_default_timeout"], 1)

    check("refresh_delay 1.0", ui._refresh_delay_ms({"refresh_interval": 1.0}),
          1000)
    check("refresh_delay 1.5", ui._refresh_delay_ms({"refresh_interval": 1.5}),
          1500)
    check("refresh_delay 2.0", ui._refresh_delay_ms({"refresh_interval": 2.0}),
          2000)
    check("refresh_delay 非法回退 1500",
          ui._refresh_delay_ms({"refresh_interval": 9}), 1500)
    check("refresh_delay 缺省 1500", ui._refresh_delay_ms({}), 1500)


def test_settings_roundtrip(tmp):
    print("\n=== settings / 勾选 / 顺序持久化 ===")
    cfg = os.path.join(tmp, "config.json")
    apps = []
    for key in ("maa", "nte", "wuwa", "maaend"):
        app = store.make_builtin(key, tmp)
        app["daily"] = store._clean_daily({"enabled": key != "nte"}, key)
        app["daily_explicit"] = True
        apps.append(app)
    settings = store._clean_settings({
        "accent": "#9ae66e", "refresh_interval": 2.0,
        "close_action": "minimize", "daily_default_timeout": 45,
        "daily_show_preview": False, "adb_enabled": True,
    })
    with mock.patch.object(store, "CONFIG", cfg):
        check("保存成功", store.save_state(
            apps, clash="", root=tmp,
            daily_order=["wuwa", "maa", "maaend", "nte"],
            settings=settings), True)
        raw = json.load(open(cfg, encoding="utf-8"))
        check("config settings 落盘", raw["settings"]["accent"], "#9ae66e")
        check("config daily_order 落盘", raw["daily_order"],
              ["wuwa", "maa", "maaend", "nte"])
        loaded, _clash, _root, meta = store.load_state_full()
    check("重载 settings accent", meta["settings"]["accent"], "#9ae66e")
    check("重载 refresh", meta["settings"]["refresh_interval"], 2.0)
    check("重载 close_action", meta["settings"]["close_action"], "minimize")
    check("重载 daily_order", meta["daily_order"],
          ["wuwa", "maa", "maaend", "nte"])
    by_key = {app["key"]: app for app in loaded}
    check("旧 daily enabled 保留", by_key["maa"]["daily"]["enabled"], True)
    check("禁用项保留", by_key["nte"]["daily"]["enabled"], False)

    # 勾选过滤 / 顺序
    check("ordered keys", daily.ordered_daily_keys(
        loaded, meta["daily_order"]), ["wuwa", "maa", "maaend", "nte"])
    check("enabled keys", daily.enabled_daily_keys(
        loaded, meta["daily_order"]), ["wuwa", "maa", "maaend"])
    check("过滤无效 key 并补齐缺失", daily.ordered_daily_keys(
        loaded, ["bogus", "nte"]), ["nte", "maa", "wuwa", "maaend"])

    # 默认超时设置只作用于未显式写 timeout 的 daily
    legacy = {"version": 4, "root": tmp, "settings": {
        "daily_default_timeout": 55},
        "apps": {"maa": {"daily": {"enabled": True, "task": "DailyTask"}}}}
    with open(cfg, "w", encoding="utf-8") as fh:
        json.dump(legacy, fh, ensure_ascii=False)
    with mock.patch.object(store, "CONFIG", cfg):
        loaded2, _c, _r, _m = store.load_state_full()
    maa = next(app for app in loaded2 if app["key"] == "maa")
    check("未写 timeout 时用设置默认超时",
          maa["daily"]["timeout_min"], 55)


# ---------------------------------------------------------------- manager
def make_apps():
    apps = []
    for key, game in (("maa", "MAA"), ("nte", "NTE"),
                      ("wuwa", "WW"), ("maaend", "ENDFIELD")):
        apps.append({
            "key": key, "game": game, "script": game, "builtin": True,
            "script_exe": "", "script_procs": [], "game_procs": [],
            "game_exe": "", "daily": store._clean_daily({}, key),
            "daily_explicit": False,
        })
    return apps


def test_manager_isolation():
    print("\n=== 每游戏独立状态（单游戏互斥） ===")
    apps = make_apps()
    gate = threading.Event()
    started = threading.Event()
    executed = []

    def fake_run(app, settings=None, *, dry_run=False, stop_event=None,
                 on_event=None, launcher=None):
        executed.append(app["key"])
        if on_event:
            on_event({"type": "state", "key": app["key"],
                      "state": daily.RUNNING, "pid": 4321})
        started.set()
        gate.wait(timeout=5)
        state = daily.STOPPED if (stop_event and stop_event.is_set()) \
            else daily.FINISHED
        return {"key": app["key"], "game": app["game"], "state": state,
                "reason": "mock", "pid": 4321}

    events = []
    with mock.patch.object(daily, "run", side_effect=fake_run):
        manager = daily.DailyManager(apps, on_event=events.append)
        ok, reason = manager.start_single("maa")
        check("开始单游戏", ok, True)
        check("单游戏进行中", manager.state_of("maa")["state"] in
              (daily.STARTING, daily.RUNNING), True)
        started.wait(timeout=2)
        # 其它行必须保持自己的空闲状态
        for key in ("nte", "wuwa", "maaend"):
            check(f"{key} 不被标记为运行中",
                  manager.state_of(key)["state"], daily.IDLE)
        ok2, reason2 = manager.start_single("nte")
        check("另一项运行时拒绝开始", ok2, False)
        check("拒绝原因提示", "进行中" in reason2, True)
        check("队列进行中提示", "队列" in manager.busy_reason("nte")
              or "进行中" in manager.busy_reason("nte"), True)
        gate.set()
        time.sleep(0.2)
        check("单游戏结束状态", manager.state_of("maa")["state"],
              daily.FINISHED)
        check("其它行仍空闲", manager.state_of("nte")["state"], daily.IDLE)
        check("busy 释放", manager.busy, False)

        # 队列顺序 + 勾选过滤
        executed.clear()
        gate.clear()
        started.clear()
        apps[1]["daily"] = store._clean_daily({"enabled": False}, "nte")
        keys = daily.enabled_daily_keys(apps, ["maend", "maa", "wuwa"])
        keys = daily.enabled_daily_keys(apps, ["maa", "nte", "wuwa", "maaend"])
        check("队列只含勾选项", keys, ["maa", "wuwa", "maaend"])
        ok, reason = manager.start_queue(keys)
        check("开始队列", ok, True)
        started.wait(timeout=2)
        check("队列当前项运行中",
              manager.state_of("maa")["state"] in
              (daily.STARTING, daily.RUNNING), True)
        gate.set()
        for _ in range(50):
            if not manager.busy:
                break
            time.sleep(0.05)
        check("队列执行顺序", executed, ["maa", "wuwa", "maaend"])
        for key in ("maa", "wuwa", "maaend"):
            check(f"{key} 队列完成", manager.state_of(key)["state"],
                  daily.FINISHED)
        check("未勾选项保持空闲", manager.state_of("nte")["state"], daily.IDLE)


def test_manager_stop():
    print("\n=== 单游戏停止 ===")
    apps = make_apps()
    stop_seen = threading.Event()
    started = threading.Event()

    def fake_run(app, settings=None, *, dry_run=False, stop_event=None,
                 on_event=None, launcher=None):
        started.set()
        for _ in range(100):
            if stop_event is not None and stop_event.is_set():
                stop_seen.set()
                break
            time.sleep(0.02)
        return {"key": app["key"], "game": app["game"],
                "state": daily.STOPPED, "reason": "用户停止"}

    with mock.patch.object(daily, "run", side_effect=fake_run):
        manager = daily.DailyManager(apps)
        manager.start_single("wuwa")
        started.wait(timeout=2)
        check("停止接口返回", manager.stop_single("wuwa"), True)
        stop_seen.wait(timeout=2)
        check("stop_event 传递到 runner", stop_seen.is_set(), True)
        for _ in range(50):
            if not manager.busy:
                break
            time.sleep(0.05)
        check("停止后状态", manager.state_of("wuwa")["state"], daily.STOPPED)
        check("停止非当前项返回 False", manager.stop_single("maa"), False)


def test_theme_tokens():
    print("\n=== v0.9 设计令牌 / 品牌 / 小工具路径 ===")
    theme = ui.T
    check("品牌标题", ui.TITLE, "All-My-Maa · 游戏脚本中心")
    check("字体", theme.UI_FONT, "Microsoft YaHei UI")
    check("标题字号范围", 20 <= theme.UI_FONT_SIZES["title"] <= 22, True)
    check("正文字号范围", 11 <= theme.UI_FONT_SIZES["body"] <= 12, True)
    check("辅助字号不小于 10", theme.UI_FONT_SIZES["aux"] >= 10, True)
    check("圆角 10-12", 10 <= theme.RADIUS <= 12, True)
    check("小圆角", theme.RADIUS_SM, 8)
    check("间距体系", (theme.SPACE_XS, theme.SPACE_SM, theme.SPACE_MD,
                       theme.SPACE_LG), (8, 12, 16, 20))
    check("默认窗口", (theme.WIN_W, theme.WIN_H), (1180, 760))
    check("最小窗口", (theme.MIN_W, theme.MIN_H), (1000, 640))
    check("侧边栏宽度", theme.SIDEBAR_W, 232)
    check("旧渲染尺寸保持", (theme.W, theme.H), (1200, 560))
    check("项目主页", ui.PROJECT_PAGES,
          "https://diaohesi.github.io/All-My-Maa/")
    check("GitHub", ui.PROJECT_GITHUB, "https://github.com/Diaohesi/All-My-Maa")

    tmp = tempfile.mkdtemp(prefix="gh_tools_")
    check("脚本目录", ui._script_directory(tmp), os.path.abspath(tmp))
    check("脚本目录缺省", ui._script_directory(""), store.APP_DIR)
    check("无 logs 回退", ui._log_directory(tmp), tmp)
    os.makedirs(os.path.join(tmp, "logs"), exist_ok=True)
    check("logs 目录", ui._log_directory(tmp), os.path.join(tmp, "logs"))
    check("License 可定位", bool(ui._find_license()), True)
    check("更新日志预览非空", bool(ui._changelog_preview_text(3)), True)


def test_release_parsing():
    print("\n=== 软件更新/版本解析（纯逻辑） ===")
    info = ui.parse_release_payload(json.dumps({
        "tag_name": "v0.9.0", "name": "All-My-Maa v0.9.0",
        "body": "新增圆角 UI", "html_url": "https://example.com/release",
        "published_at": "2026-10-01T00:00:00Z",
    }), "0.8.0")
    check("解析无错误", info["error"], "")
    check("版本号去 v", info["version"], "0.9.0")
    check("检测到新版本", info["newer"], True)
    check("更新说明", info["changelog"], "新增圆角 UI")
    check("发布页", info["url"], "https://example.com/release")

    same = ui.parse_release_payload({"tag_name": "v0.8.0"}, "0.8.0")
    check("同版本不提示更新", same["newer"], False)
    older = ui.parse_release_payload({"tag_name": "v0.7.9"}, "0.8.0")
    check("旧版本不提示更新", older["newer"], False)
    padded = ui.parse_release_payload({"tag_name": "0.9"}, "0.8.0")
    check("非 v 前缀版本", (padded["version"], padded["newer"]),
          ("0.9", True))
    bytes_info = ui.parse_release_payload(
        json.dumps({"tag_name": "v1.0.0"}).encode("utf-8"), "0.8.0")
    check("bytes payload", bytes_info["newer"], True)
    bad = ui.parse_release_payload("{not json", "0.8.0")
    check("坏 JSON 给出错误", bool(bad["error"]), True)
    missing = ui.parse_release_payload({}, "0.8.0")
    check("缺版本号给出错误", bool(missing["error"]), True)
    invalid = ui.parse_release_payload({"tag_name": "release-latest"},
                                       "0.8.0")
    check("无法识别版本给出错误", bool(invalid["error"]), True)


def test_format_changelog():
    print("\n=== 更新日志纯文本渲染 ===")
    raw = (
        "## v0.9.0 (2026-10-18)\n"
        "- **界面重构**：圆角与间距\n"
        "- 修复 [Issue #12](https://example.com/12) 的链接\n"
        "## v0.8.0 (2026-10-01)\n"
        "- `代码`样式与 ~~删除线~~\n"
        "  - 子条目保留换行\n"
    )
    out = ui.format_changelog_text(raw)
    check("标题行", "v0.9.0 · 2026-10-18" in out, True)
    check("无 ## 符号", "##" not in out, True)
    check("无列表符号", not any(line.lstrip().startswith(("- ", "* "))
                                for line in out.splitlines()), True)
    check("无粗体/代码/链接语法",
          ("**" not in out and "`" not in out and "](" not in out), True)
    check("保留链接文字", "Issue #12" in out, True)
    check("保留条目换行", "界面重构：圆角与间距" in out, True)
    check("最新版本在上", out.index("v0.9.0") < out.index("v0.8.0"), True)
    limited = ui.format_changelog_text(raw, 1)
    check("limit_entries 截断", ("v0.9.0" in limited
                                and "v0.8.0" not in limited), True)
    plain = ui.format_changelog_text("### 新增\n- **圆角 UI**\n> 注意事项")
    check("无标题/引用符号", ("#" not in plain and ">" not in plain
                            and "**" not in plain), True)
    check("条目文字保留", "圆角 UI" in plain and "注意事项" in plain, True)
    check("空文本", ui.format_changelog_text(""), "")
    check("空白文本", ui.format_changelog_text("   \n\n"), "")
    preview = ui._changelog_preview_text(3)
    check("关于预览无原始 Markdown", "##" not in preview, True)
    check("License 清晰一行", ui._license_label(), "License：MIT License")


def test_ui_icons():
    print("\n=== v0.9.1 UI 图标映射/尺寸/回退 ===")
    from PIL import Image
    import shutil

    check("品牌图标文件", ui.BRAND_ICON_FILE, "LinYuxia.png")
    check("页面图标映射", ui.PAGE_ICON_FILES, {
        "home": "page_home.png", "daily": "page_daily.png",
        "settings": "page_settings.png", "about": "page_about.png"})
    check("窗口尺寸档", (ui.ICON_SIZES["window"],
                        ui.ICON_SIZES["window_small"]), (64, 32))
    check("品牌尺寸 44-48", 44 <= ui.ICON_SIZES["brand"] <= 48, True)
    check("导航尺寸 20-22", 20 <= ui.ICON_SIZES["nav"] <= 22, True)
    check("页面尺寸 28-32", 28 <= ui.ICON_SIZES["page"] <= 32, True)
    check("关于尺寸", ui.ICON_SIZES["about"] >= 48, True)

    for name in ("brand", "home", "daily", "settings", "about"):
        path = ui.icon_path(name)
        check(f"{name} 图标存在", bool(path) and os.path.isfile(path), True)
        check(f"{name} 图标文件名", os.path.basename(path),
              ui.BRAND_ICON_FILE if name == "brand"
              else ui.PAGE_ICON_FILES[name])
    for name in ("brand", "home", "daily", "settings", "about"):
        path = ui.icon_path(name)
        with Image.open(path) as image:
            check(f"{name} 源图 192×192", image.size, (192, 192))
    check("未知图标返回空", ui.icon_path("bogus"), "")
    check("未知图标无回退", ui.resolve_icon_path("bogus"), "")

    real_hub = os.path.join(store.ASSETS, "hub.png")
    real_brand = os.path.join(store.ASSETS, "LinYuxia.png")
    real_page_home = os.path.join(store.ASSETS, "page_home.png")
    empty = tempfile.mkdtemp(prefix="gh_icons_empty_")
    with mock.patch.object(store, "ASSETS", empty):
        check("缺资源 path 为空", ui.icon_path("brand"), "")
        check("缺资源回退为空", ui.resolve_icon_path("brand"), "")
        check("缺页面图标不崩溃", ui.resolve_icon_path("home"), "")
        shutil.copyfile(real_hub, os.path.join(empty, "hub.png"))
        check("品牌回退旧 hub.png",
              ui.resolve_icon_path("brand"), os.path.join(empty, "hub.png"))
        check("页面图标无回退", ui.resolve_icon_path("home"), "")
        shutil.copyfile(real_brand, os.path.join(empty, "LinYuxia.png"))
        check("关于回退 LinYuxia",
              ui.resolve_icon_path("about"), os.path.join(empty, "LinYuxia.png"))
        shutil.copyfile(real_page_home,
                        os.path.join(empty, "page_home.png"))
        check("补齐页面图标",
              ui.icon_path("home"), os.path.join(empty, "page_home.png"))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    with tempfile.TemporaryDirectory(prefix="gh_ui_state_") as tmp:
        test_settings_clean()
        test_settings_roundtrip(tmp)
        test_manager_isolation()
        test_manager_stop()
        test_theme_tokens()
        test_release_parsing()
        test_format_changelog()
        test_ui_icons()
    print("\nFAILURES:", failures if failures else "none")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
