# All-My-Maa 回归测试报告（v0.11.0 最终版）

| 项目 | 内容 |
| --- | --- |
| 仓库 | `D:\All MAA\GameHub`（GitHub: https://github.com/Diaohesi/All-My-Maa ） |
| 被测版本 | **All-My-Maa v0.11.0**（功能快照：v0.10.5 + ① 异环清日常改为「打开 MaaNTE UI → 发送 Ctrl+F10 开始任务 → 轮询 HTTP `/maa/state` / 回退 debug 日志等待结束（完成后保留 MaaNTE 窗口）」；② 最小化到系统托盘（纯 ctypes `Shell_NotifyIconW`）与设置 `minimize_to_tray`；`gamehub.__init__.VERSION` 当前仍为 `0.10.5`，按发布流程由 release 任务 bump 为 `0.11.0`） |
| 代码基线 | `896c47a`（release: v0.10.5） |
| 工作区增量 | `gamehub/daily.py` **+380 / -98**（恢复 `mxu_ui` 计划/热键/HTTP/日志回退/保留窗口；删除异环 `pre_game`/`--autostart`；`mxu_web_port`/`mxu_http_state`/`_mxu_state_row`/`_run_mxu_ui`）、新增 `gamehub/tray.py`（391 行：`TrayManager`/Win32 托盘窗口/菜单/图标/回调）、`gamehub/store.py` +2/-1（`minimize_to_tray` 默认 True 与清洗）、`gamehub/ui.py` +93/-5（托盘初始化、最小化分支、托盘回调、设置项、退出清理）、新增 `tools/test_tray.py`；`tools/test_daily.py`/`test_ui_state.py`/`regression_test.py` 同步更新 |
| 测试脚本 | `tools/regression_test.py`（标准库 `unittest`，v0.11.0 最终版 **248 用例 / 48 个测试类**） |
| 执行命令 | `python tools/regression_test.py`（任意 CWD 可运行；`-v` 详细输出） |
| 执行时间 | 2026-10-18（最终快照：`gamehub/daily.py` mtime 20:30:44，`gamehub/tray.py` mtime 20:36:41，`gamehub/ui.py` mtime 20:36:21，`gamehub/store.py` mtime 20:34:47） |
| 运行环境 | Windows 10/11 · Python 3.13.7 · Pillow 12.2.0 · 字体 msyh.ttc/msyhbd.ttc 存在 |
| 结果 | **248 个用例：248 通过 / 0 失败 / 0 错误 / 0 跳过；退出码 0（全绿）** |
| 耗时 | 约 2.0–2.8 s |

实际输出结尾：

```
----------------------------------------------------------------------
Ran 248 tests in 2.149s

OK

===== 汇总 =====
用例数: 248  失败: 0  错误: 0  跳过: 0
```

> **本版更新（239 → 248 用例，v0.11.0 两项功能复核）**
> - feature-dev 已按 v0.11 语义把旧 pre_game/autostart 用例替换为 `V0110MxuUiTests` 9 条（基线 239 全绿）。
> - QA 新增 **`V0110MxuUiGapsTests` 3 条**（计划缺失 exe/未选实例/旧 pre_game 无残留、HTTP 解析边界与自定义端口、HTTP running→无状态结束且保留窗口）+ **`V0110TrayTests` 6 条**（设置默认/持久化/非法回退、start/stop 幂等、失败降级、tooltip/回调调度、最小化分支/显示恢复/同步、退出清理）→ **248 用例**。
> - 原有其余用例全部继续通过；`tools/test_tray.py`（新增）、`test_ui_state.py`、`test_daily.py`、`test_elevation.py`、`test_game_exe.py`、`test_game_launch.py`、`test_launch_spec.py` 交叉复核均 rc=0 / FAILURES: none；`test_detect_game.py` rc=0。
> - 全部 mock/假时钟/临时目录：**不启动 GUI/游戏、不创建真实托盘、不联网**。

## 一、测试范围与覆盖矩阵

| 测试类 | 用例数 | 覆盖点 | 结果 |
| --- | --- | --- | --- |
| `VersionTests` / `PathHelperTests` / `CleanProcsTests` / `ProcNameTests` | 3 / 5 / 5 / 1 | 版本比较、路径转换、进程名清洗 | 14 通过 |
| `ConfigStateTests` | 13 | 配置往返/BOM/损坏 JSON/Clash、config v4、detect 往返、v3→v4 迁移 | 13 通过 |
| `FindAppExeTests` / `PickBestExeTests` / `ReadVersionTests` / `ProcessTests` | 4 / 3 / 8 / 3 | 路径扫描、版本读取、进程快照 | 18 通过 |
| `RenderSmokeTests` / `ImportSmokeTests` | 8 / 2 | 旧 Pillow 渲染尺寸、`import gamehub.ui/tray` | 10 通过 |
| `GameCandidatesTests` | 8 | 游戏启动程序自动检测 | 8 通过 |
| `DetectRuleCleanTests` / `DetectorInterfaceRulesTests` / `BuiltinRuleTableTests` | 7 / 6 / 2 | 检测规则 schema、interface.json、内置表 | 15 通过 |
| `WindowMatchTests` / `ProcMatchTests` / `GameRulesSourceTests` | 8 / 3 / 7 | 窗口/进程匹配、规则优先级 | 18 通过 |
| `DetectGameStateTests` / `DetectorSnapshotSmokeTests` | 11 / 4 | 检测状态分支、真实快照契约 | 15 通过 |
| `LaunchSpecTests` | 11 | 鸣潮启动规格/回退/路径判定/持久化 | 11 通过 |
| `DailyPlanTests` / `DailyPreconditionTests` | 7 / 5 | 四款 dry-run 命令、前置（异环 mxu_ui） | 12 通过 |
| `DailyStateMachineTests` / `DailyQueueTests` / `DailyLogConfigTests` / `DailyQuotingTests` | 8 / 5 / 4 / 5 | 状态机、队列、日志/配置、引号 | 22 通过 |
| `SettingsTests` / `SettingsConfigTests` | 4 / 3 | settings 清洗/持久化/默认（含 minimize_to_tray） | 7 通过 |
| `DailySelectionTests` / `DailyManagerTests` | 3 / 7 | 勾选过滤/顺序、每游戏独立状态 | 10 通过 |
| `UiPureLogicTests` / `ClashResolutionTests` | 3 / 3 | 刷新间隔/CHANGELOG、clash 路径（QA-15） | 6 通过 |
| `V09ThemeTests` / `SoftwareUpdateTests` | 4 / 5 | 设计令牌、软件更新纯逻辑 | 9 通过 |
| `SmallToolsTests` / `ChangelogFormatTests` | 4 / 3 | 小工具路径、更新日志纯文本 | 7 通过 |
| `V091IconTests` | 3 | 图标资产/映射/回退 | 3 通过 |
| `V010GameExeTests` / `V010GameLaunchTests` | 5 / 6 | 异环启动器优先、四款启动策略 | 11 通过 |
| `V010WaitLaunchTests` / `V010SettingsThemeTests` / `V010SettingsRoundTripTests` / `V010AutoUpdateTests` | 4 / 5 / 1 / 3 | 等待/字体标题栏/settings 往返/自动更新 | 13 通过 |
| `V0103ElevationTests` | 8 | 默认管理员启动/提权/打包 manifest/权限显示 | 8 通过 |
| `V0110MxuUiTests`（feature-dev） | 9 | 异环 mxu_ui：计划/热键/HTTP/日志/保留窗口/超时/停止 | 9 通过 |
| **`V0110MxuUiGapsTests`**（v0.11.0 QA 新增） | 3 | 见 2.1–2.3 | 3 通过 |
| **`V0110TrayTests`**（v0.11.0 QA 新增） | 6 | 见 2.4 | 6 通过 |
| **合计** | **248** | | **248 通过 / 0 跳过** |

## 二、v0.11.0 功能覆盖说明

### 2.1 异环 `mxu_ui` 计划（QA 补充 + feature-dev 用例）
- `mode="mxu_ui"`、`exe=MaaNTE.exe`、`params=""`、`args=[]`、`argv=[exe]`、`command_text` 含 exe；**不再带 `--autostart`/`--quit-after-run`/`pre_game`**。
- 热键：读取 `settings.hotkeys.startTasks`（字符串/dict）；`globalEnabled=false`、缺失、无效键 → `hotkey=None` + warning「手动…」（不静默成功）。
- 实例：`instance`（来自设置/自动建议）、`instance_id`（按实例 id/uuid）、`web_port`（配置 `webServerPort` 或默认 12701）。
- 计划错误覆盖：MaaNTE.exe 缺失、脚本已在运行、无实例配置、未选择实例、实例不存在、实例 0 启用任务；notes 提示 HTTP/日志等待、完成后保留窗口、以管理员启动正常 UI。
- **旧 pre_game 无残留**：`daily` 无 `_launch_pre_game`/`_terminate_quiet`/`PRE_GAME_WAIT_SECONDS`，源码无 `pre_game` 标记；异环计划无 `--autostart`/`--quit-after-run`（终末地仍保留 MXU CLI）。

### 2.2 异环执行链路（`_run_mxu_ui`，feature-dev 用例 + QA 补充）
- 启动 MaaNTE UI（无参数）→ 等待主窗口（≤60s；超时 → failed 且结束本次进程）→ 焦点 → 发送 `Ctrl+F10`；热键缺失/发送失败 → failed「手动点击开始任务」并**保留窗口**（只 close 不 terminate）。
- 发送成功后进入等待：
  - **HTTP `/maa/state`**：`running=true` 标记开始；running→false 时 `overall_status` 含 fail/error → failed，否则 finished；直接返回 `succeeded`→finished、`failed`→failed、`stopped`→finished（reason 均含「MaaNTE 窗口保留」）。
  - **HTTP 不可用**：连续失败 ≥10s → 自动切换到 debug 日志判定（不误报失败）。
  - **日志回退**：开始标记、完成标记（`tasks-completed`/`停止任务`/`已停止`/`任务已全部完成`）→ finished；失败标记（`任务出错`/`执行失败`）→ failed；MaaNTE 提前退出 → failed。
  - **停止/超时**：用户停止 → stopped「已结束本次启动的 MaaNTE」；超时 → timeout「已结束本次启动的 MaaNTE」；两者均只结束**本次** launcher 返回的进程句柄，结果 pid 为该次 pid。
  - **完成保留窗口**：finished/failed 分支不 terminate，仅 close 句柄；窗口保留供用户查看。

### 2.3 HTTP 解析边界（QA 补充）
- URL 固定 `http://127.0.0.1:<web_port>/maa/state`（自定义 `webServerPort=12888` 生效）。
- `_mxu_state_row` 支持任意嵌套结构，按 `id`/`instance_id` 优先、`name` 兜底匹配；`is_running`/`isRunning` 或 `task_run_state.is_running`，`overall_status`/`overallStatus` 顶层或内层均可。
- 无匹配实例 → `ok=True, found=False, running=False`；HTTP 异常 → `ok=False, error=...`（不抛异常）。

### 2.4 最小化到系统托盘（`V0110TrayTests` + feature-dev `test_tray.py`）
- **设置**：`minimize_to_tray` 默认 `True`；仅接受 bool（字符串/数字/None 回退默认）；`save_state`/`load_state_full` 往返持久化（写入 config settings 并读回 false）。
- **TrayManager**：`start()`/`stop()` 幂等（重复 start 不重复创建、重复 stop 不重复清理）；平台不支持/原生启动异常 → 返回 False、`failed=True`、`last_error` 记录、不崩溃，可安全 stop 降级。
- **tooltip/回调**：默认 tooltip、截断 127 字符、空值回退；未启动时 update 返回 False，启动后调用 `_modify_native`；菜单「打开主界面/退出」通过 `root.after(0, callback)` 切回 Tk 线程；根窗口已销毁时安全忽略；空回调不调度。
- **最小化分支**：设置开启且托盘 start 成功 → `root.withdraw()` + `_tray_hidden=True`；设置关闭/托盘为 None/start 失败/异常 → 返回 False 并回退 `iconify()`；`_show_from_tray` deiconify+lift+focus；`_sync_tray` 按设置 start/stop 并清理 hidden 状态。
- **退出清理**：关闭行为 minimize 且隐藏成功 → 不销毁窗口；隐藏失败 → iconify；force/exit → `tray.stop()` + `root.destroy()`；`tray.stop()` 异常被吞掉保证退出。

### 2.5 交叉验证与既有回归
- `tools/test_tray.py`（v0.11 新增）、`tools/test_ui_state.py`、`tools/test_daily.py`、`tools/test_elevation.py`、`tools/test_game_exe.py`、`tools/test_game_launch.py`、`tools/test_launch_spec.py` 均 **rc=0 / FAILURES: none**；`tools/test_detect_game.py` rc=0（只读）。
- 其余历史契约（v0.4~v0.10.5：detector/launch spec/清日常其余逻辑/settings/勾选/独立状态/图标/软件更新/标题栏/字体/自动更新/默认管理员启动等）全部继续通过，无回归。
- 稳定性：本套件连续运行 2 次均 248/248 通过。

## 三、缺陷清单与状态

### 3.1 已修复项（持续回归通过）
QA-01/02（read_version 回退）、QA-03（save_state 返回 bool）、QA-04（版本比较）、QA-05（非 str 进程名）、QA-09（DisplayIcon 引号+索引）、QA-10（v4 迁移不覆盖用户进程名）、QA-11（游戏名最长/精确反查）、QA-12（字符串进程名不按空白拆分）、QA-13（extra_args 只保留 str 并 strip）、QA-14（命令参数统一引号处理）、QA-15（clash 便携相对路径还原）——全部保持通过。

### 3.2 保留项（低风险/设计边界，不阻塞 v0.11.0）
- QA-06：目录扫描跳过 `data/resources/config/build/dist` 等名字（设计取舍，建议 README FAQ 说明）。
- QA-07：自定义卡片 exe 丢失后仍以相对路径加载、无 missing 提示（建议后续排期）。
- QA-08：`_portable(path==root)` → `"."`（仅异常输入触发）。

> 本轮未发现新增阻塞性缺陷；mxu_ui 计划/执行/HTTP/日志回退/保留窗口/本次进程清理与托盘设置/生命周期/降级/回调/最小化/退出清理断言全部通过。

## 四、未覆盖点与测试限制

1. **真实 MaaNTE HTTP（需 Lead 实机验证）**：`/maa/state` 真实字段/嵌套结构、`webServerPort` 实际值、running→succeeded/failed 的时序、HTTP 从可用到不可用的切换、真实日志滚动/回退 marker。
2. **真实热键/窗口**：向 MaaNTE 发送 `Ctrl+F10` 的实际效果（焦点/热键冲突/管理员权限）、主窗口检测/置前、任务结束后窗口保留的真实交互。
3. **真实 Windows 托盘**：`Shell_NotifyIconW` 图标显示、左键恢复/双击、右键菜单（打开/退出）、tooltip、Explorer 重启后的图标恢复、退出时图标清理；测试全部 mock，未创建真实托盘。
4. **真实最小化行为**：`withdraw`/`iconify` 在窗口管理器/DPI/多屏下的表现、任务栏/Alt-Tab、托盘失败回退的真实体验。
5. **真实任务失败/超时/停止**：真实任务失败 marker、超时 120 分钟、用户停止后仅结束本次进程的行为。
6. **其它沿用前版未覆盖点**：真实 UAC/默认管理员、真实游戏启动/自动更新/打包 `_MEIPASS` 路径/长时并发。
7. **版本号**：`VERSION` 当前仍为 `0.10.5`，发布任务 bump 为 `0.11.0` 后建议再跑一次本套件（预期仍 248/248 全绿）。

## 五、结论与建议

- **v0.11.0 回归全绿：248/248 通过、0 失败/0 错误/0 跳过、exit 0（约 2.0–2.8 s）**；可重复执行、无副作用、不创建真实托盘/不启动 GUI。
- 异环清日常 UI+热键+HTTP/日志等待（保留窗口）与最小化到托盘（设置/幂等/降级/回调/最小化分支/退出清理）覆盖完整；旧 pre_game/autostart 已无残留；终末地 MXU CLI 与其他历史契约无回归。
- 未发现新增阻塞性缺陷；QA-15 保持修复；QA-06/07/08 仍为低风险/设计边界。
- 发布前建议：① Lead 实机验证真实 MaaNTE HTTP `/maa/state` 字段与时序、真实 `Ctrl+F10` 热键/窗口、真实 Windows 托盘与最小化/退出；② release 任务 bump `VERSION=0.11.0` 后重跑本套件（预期 248/248）；③ CI 增加 Windows runner 执行 `python tools/regression_test.py`（无需网络）。

## 附录：证据与约束遵守

- QA 只修改 `tools/regression_test.py`、`docs/qa-report.md`；未修改 `gamehub/`、`tools/test_*.py`（feature-dev 自测）、`README.md`、`CHANGELOG.md` 等；未 commit / push。
- 未启动 GUI/游戏、**未创建真实系统托盘**、未发送真实热键、未联网；HTTP 全部 mock `urlopen`/`mxu_http_state`，托盘全部 mock `_start_native`/`_stop_native`/Tk root，未调用真实 Shell_NotifyIconW。
- 配置类用例全部使用临时目录 + `mock.patch` 隔离；真实 `config.json` mtime `20:24:36`（Lead GUI 验证写入 v4），QA 运行前后未变化。
- 交叉验证：`tools/test_tray.py`、`tools/test_ui_state.py`、`tools/test_daily.py`、`tools/test_elevation.py`、`tools/test_game_exe.py`、`tools/test_game_launch.py`、`tools/test_launch_spec.py` 均 rc=0 / FAILURES: none；`tools/test_detect_game.py` rc=0。
- 稳定性：本套件连续运行 2 次均 248/248 通过。
