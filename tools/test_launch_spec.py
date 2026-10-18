# -*- coding: utf-8 -*-
"""启动规格（launch spec）自测：规格拼装 / 环境清理 / 回退 / 进程路径判定。

不启动 GUI、不启动游戏；只有 --live 才会读取本机真实的 ok-ww 安装做只读核对。
不会写出真实 config.json（持久化用例使用临时 CONFIG）。

用法：
    python tools/test_launch_spec.py            # 全部离线用例（mock）
    python tools/test_launch_spec.py --live     # 额外打印本机 ok-ww 真实检测结果
"""
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


def touch(path, content=b"stub"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(content)
    return path


def make_fake_install(tmp, include_script=True):
    """临时目录里拼一个 ok-ww 安装布局，返回 (app, 关键路径)。"""
    app_root = os.path.join(tmp, "WuwaMAA", "ok-ww")
    launcher = touch(os.path.join(app_root, "ok-ww.exe"))
    app_dir = os.path.join(app_root, "data", "apps", "ok-ww")
    pythonw = touch(os.path.join(app_dir, "python", "pythonw.exe"))
    working = os.path.join(app_dir, "working")
    os.makedirs(working, exist_ok=True)
    script = os.path.join(working, "main.py")
    if include_script:
        touch(script, b"print('stub')\n")
    app_json = os.path.join(app_dir, "app.json")
    with open(app_json, "w", encoding="utf-8") as fh:
        json.dump({"current_version": "v9.9.9", "current_profile": "China"}, fh)
    app = {"key": "wuwa", "game": "鸣潮", "script_exe": launcher,
           "script_procs": ["OK-WW.EXE"]}
    return app, {"launcher": launcher, "pythonw": pythonw, "working": working,
                 "script": script, "app_json": app_json}


def check_spec_assembly(tmp):
    print("\n=== 启动规格拼装 ===")
    app, paths = make_fake_install(tmp)
    spec = store.build_okww_launch(app)
    check("type", spec["type"], "python")
    check("exe= bundled pythonw", spec["exe"], paths["pythonw"])
    check("script=working\\main.py", spec["script"], paths["script"])
    check("cwd=working", spec["cwd"], paths["working"])
    check("launcher_exe=ok-ww.exe", spec["launcher_exe"], paths["launcher"])
    check("fallback=launcher", spec["fallback"], "launcher")
    check("process_exe_names", spec["process_exe_names"],
          ["pythonw.exe", "python.exe"])
    check("process_exe_dirs", spec["process_exe_dirs"],
          [os.path.dirname(paths["pythonw"])])
    for key in ("PYTHONNOUSERSITE", "PYTHONIOENCODING", "PYTHONUNBUFFERED"):
        check(f"env {key}", spec["env"].get(key),
              store.LAUNCH_ENV_SET[key])
    check("env PYAPPIFY_APP_VERSION", spec["env"].get("PYAPPIFY_APP_VERSION"),
          "v9.9.9")
    check("env PYAPPIFY_APP_PROFILE", spec["env"].get("PYAPPIFY_APP_PROFILE"),
          "China")
    check("env PYAPPIFY_EXECUTABLE", spec["env"].get("PYAPPIFY_EXECUTABLE"),
          paths["launcher"])
    for name in ("PYTHONHOME", "PYTHONPATH", "PYTHONSTARTUP", "PYAPPIFY_PID"):
        check(f"clear_env 含 {name}", name in spec["clear_env"], True)

    print("\n=== 环境变量清理/注入（_launch_env） ===")
    old_env = os.environ.copy()
    try:
        os.environ["PYTHONHOME"] = r"C:\bad\python"
        os.environ["PYTHONPATH"] = r"C:\bad\path"
        os.environ["PYAPPIFY_PID"] = "12345"
        env = store._launch_env(spec)
    finally:
        os.environ.clear()
        os.environ.update(old_env)
    check("清理 PYTHONHOME", "PYTHONHOME" in env, False)
    check("清理 PYTHONPATH", "PYTHONPATH" in env, False)
    check("清理 PYAPPIFY_PID", "PYAPPIFY_PID" in env, False)
    check("注入 PYTHONNOUSERSITE", env.get("PYTHONNOUSERSITE"), "1")
    check("注入 PYTHONIOENCODING", env.get("PYTHONIOENCODING"), "utf-8")
    check("注入 PYTHONUNBUFFERED", env.get("PYTHONUNBUFFERED"), "1")
    check("PATH 为系统默认", env.get("PATH"), store._wrapper_path())
    check("注入 PYAPPIFY_APP_VERSION", env.get("PYAPPIFY_APP_VERSION"),
          "v9.9.9")
    return app, paths, spec


def check_fallback(tmp):
    print("\n=== 回退启动器（working/main.py 缺失） ===")
    app, paths = make_fake_install(os.path.join(tmp, "fallback"))
    app["launch"] = store.build_okww_launch(app)
    check("规格仍生成（用于回退）", bool(app["launch"].get("exe")), True)
    launched = []
    with mock.patch.object(store, "launch_exe",
                           side_effect=lambda exe: (launched.append(exe), (True, ""))[1]):
        ok, error, mode = store.launch_app(app)
    check("回退成功", ok, True)
    check("回退模式 launcher", mode, "launcher")
    check("回退启动的是 ok-ww.exe", launched, [paths["launcher"]])

    # 正式脚本存在时走 bundled pythonw（mock Popen，不真的启动）
    app2, paths2 = make_fake_install(os.path.join(tmp, "python_launch"))
    spec2 = store.build_okww_launch(app2)
    app2["launch"] = spec2
    captured = {}

    class FakeProc:
        pid = 4242

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeProc()

    with mock.patch.object(store.subprocess, "Popen", side_effect=fake_popen):
        ok, error, mode = store.launch_app(app2)
    check("正式脚本启动成功", (ok, mode), (True, "script"))
    check("命令 = [pythonw, main.py]",
          [os.path.normpath(item) for item in captured.get("command", [])],
          [os.path.normpath(paths2["pythonw"]),
           os.path.normpath(paths2["script"])])
    check("cwd = working", captured["kwargs"].get("cwd"), paths2["working"])
    env = captured["kwargs"].get("env") or {}
    check("启动 env 注入 PYTHONNOUSERSITE",
          env.get("PYTHONNOUSERSITE"), "1")
    check("启动 env 清理 PYTHONHOME", "PYTHONHOME" in env, False)


def check_process_path_judgement(tmp):
    print("\n=== 正式脚本进程判定（按 exe 路径，启动器不算） ===")
    app, paths = make_fake_install(os.path.join(tmp, "proc"))
    spec = store.build_okww_launch(app)
    app["launch"] = spec
    python_dir = os.path.dirname(paths["pythonw"])

    with mock.patch.object(store, "pids_for_procs", return_value={111, 222}), \
            mock.patch.object(store, "process_path",
                              side_effect=lambda pid: {
                                  111: paths["pythonw"],
                                  222: r"C:\Users\someone\Python313\pythonw.exe",
                              }.get(pid, "")):
        pids = store.launch_running_pids(app)
        running = store.launch_spec_running(app)
    check("只看 ok-ww 目录内 pythonw", pids, {111})
    check("脚本运行中", running, True)

    # 路径读不到时不能退化成“同名进程”误判（避免误判用户其它 python）
    with mock.patch.object(store, "pids_for_procs", return_value={333}), \
            mock.patch.object(store, "process_path", return_value=""):
        check("路径读不到 -> 不判定运行", store.launch_spec_running(app), False)

    # 启动器 ok-ww.exe 不算脚本运行中
    launcher_spec = dict(spec)
    with mock.patch.object(store, "pids_for_procs",
                           side_effect=lambda names: {444}
                           if "OK-WW.EXE" in names or "PYTHONW.EXE" in names
                           else set()), \
            mock.patch.object(store, "process_path",
                              return_value=paths["launcher"]):
        check("启动器路径不算运行", store.launch_spec_running(
            {"launch": launcher_spec}), False)

    check("process_exec_dirs 判定只在本目录", python_dir,
          spec["process_exe_dirs"][0])


def check_persistence(tmp):
    print("\n=== 启动规格持久化 / 旧配置兼容 ===")
    install_tmp = os.path.join(tmp, "persist")
    app, paths = make_fake_install(install_tmp)
    cfg = os.path.join(tmp, "config.json")
    with mock.patch.object(store, "CONFIG", cfg):
        apps = [store.make_builtin("wuwa", install_tmp)]
        apps[0]["launch"] = store.build_okww_launch(apps[0])
        check("保存成功", store.save_state(apps, clash="", root=install_tmp), True)
        raw = json.load(open(cfg, encoding="utf-8"))
        saved_launch = raw["apps"]["wuwa"].get("launch")
        check("config 写入 launch 规格", isinstance(saved_launch, dict), True)
        check("路径写成相对路径（便于搬移）",
              os.path.isabs(saved_launch.get("exe", "")), False)
        loaded = {item["key"]: item for item in store.load_state()[0]}
        got = loaded["wuwa"]["launch"]
        check("重载后 exe 路径还原",
              os.path.normpath(got["exe"]), os.path.normpath(paths["pythonw"]))
        check("重载后 script 路径还原",
              os.path.normpath(got["script"]), os.path.normpath(paths["script"]))
        check("重载后 cwd 还原",
              os.path.normpath(got["cwd"]), os.path.normpath(paths["working"]))
        check("重载后 launcher_exe 还原",
              os.path.normpath(got["launcher_exe"]),
              os.path.normpath(paths["launcher"]))

    # 旧 v3 配置没有 launch 字段 -> 自动补齐
    cfg2 = os.path.join(tmp, "legacy.json")
    with mock.patch.object(store, "CONFIG", cfg2):
        apps = [store.make_builtin("wuwa", install_tmp)]
        apps[0]["launch"] = store.build_okww_launch(apps[0])
        store.save_state(apps, clash="", root=install_tmp)
        raw = json.load(open(cfg2, encoding="utf-8"))
        raw["version"] = 3
        for key in raw["apps"]:
            raw["apps"][key].pop("launch", None)
        with open(cfg2, "w", encoding="utf-8") as fh:
            json.dump(raw, fh, ensure_ascii=False)
        loaded = {item["key"]: item for item in store.load_state()[0]}
        auto = loaded["wuwa"].get("launch")
        check("旧配置自动补齐 launch", isinstance(auto, dict), True)
        check("旧配置 auto exe", os.path.normpath(auto.get("exe", "")),
              os.path.normpath(paths["pythonw"]))


def check_other_apps_unchanged():
    print("\n=== 其它三款保持普通 exe 启动 ===")
    for key, exe_name in (("maa", "MAA.exe"), ("nte", "MaaNTE.exe"),
                          ("maaend", "MaaEnd.exe")):
        app = {"key": key, "game": key,
               "script_exe": os.path.join(ROOT, exe_name)}
        check(f"{key} 无 launch 规格", app.get("launch"), None)
    app = {"key": "maa", "script_exe": os.path.join(ROOT, "MAA.exe")}
    launched = []
    with mock.patch.object(store, "launch_exe",
                           side_effect=lambda exe: (launched.append(exe), (True, ""))[1]):
        ok, error, mode = store.launch_app(app)
    check("普通 exe 仍走 launch_exe", (ok, mode), (True, "exe"))
    check("普通 exe 启动路径", launched, [app["script_exe"]])


def live_check():
    print("\n=== 本机真实 ok-ww 只读核对 ===")
    apps = {item["key"]: item for item in store.load_state()[0]}
    wuwa = apps["wuwa"]
    spec = wuwa.get("launch") or {}
    if spec:
        print("  exe    =", spec.get("exe"))
        print("  script =", spec.get("script"))
        print("  cwd    =", spec.get("cwd"))
        print("  launcher =", spec.get("launcher_exe"))
        running = store.launch_spec_running(wuwa)
        pids = store.launch_running_pids(wuwa)
        print("  正式脚本运行中:", running, "pids:", sorted(pids))
        for pid in sorted(pids):
            path = store.process_path(pid)
            under = os.path.normpath(path).lower().startswith(
                os.path.normpath(os.path.dirname(spec.get("exe", ""))).lower())
            print(f"    pid {pid}: {path}  在 ok-ww python 目录内={under}")
    else:
        print("  未生成 launch 规格（安装目录不存在？）")


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    with tempfile.TemporaryDirectory(prefix="gh_launch_spec_") as tmp:
        check_spec_assembly(tmp)
        check_fallback(tmp)
        check_process_path_judgement(tmp)
        check_persistence(tmp)
        check_other_apps_unchanged()
    if "--live" in argv[1:]:
        live_check()
    print("\nFAILURES:", failures if failures else "none")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
