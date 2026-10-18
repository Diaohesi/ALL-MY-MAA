# All-My-Maa 回归测试报告（v0.10.1 最终版）

| 项目 | 内容 |
| --- | --- |
| 仓库 | `D:\All MAA\GameHub`（GitHub: https://github.com/Diaohesi/All-My-Maa ） |
| 被测版本 | **All-My-Maa v0.10.1**（功能快照：v0.10.0 + 异环 hotfix——启动游戏回 `NTELauncher.exe`、清日常改「打开 MaaNTE + 发送 Ctrl+F10 开始任务热键」；`gamehub.__init__.VERSION` 当前仍为 `0.10.0`，按发布流程由 release 任务 bump 为 `0.10.1`） |
| 代码基线 | `ce4a9f4`（docs: refresh All-My-Maa v0.10.0 screenshots） |
| 工作区增量 | `gamehub/daily.py` **+285 / -1**（`mxu_ui_hotkey`/`mxu_latest_log`/`_plan_mxu_ui`/`_run_mxu_ui` 与 run 分派；异环清日常改热键模式）、`gamehub/store.py` **+38 / -91**（异环 hints/resolve 回启动器、`_migrate_nte_game_exe` 改 HTGame→NTELauncher、`build_game_launch` 异环 launcher+user_pick）、`gamehub/ui.py` +16/-1；`tools/test_daily.py`/`test_game_exe.py`/`test_game_launch.py` 同步更新；文档由文档任务更新 |
| 测试脚本 | `tools/regression_test.py`（标准库 `unittest`，v0.10.1 最终版 **228 用例 / 45 个测试类**） |
| 执行命令 | `python tools/regression_test.py`（任意 CWD 可运行；`-v` 详细输出） |
| 执行时间 | 2026-10-18（最终快照：`gamehub/daily.py` mtime 18:39:37，`gamehub/store.py` mtime 18:38:19，`gamehub/ui.py` mtime 18:39:16） |
| 运行环境 | Windows 10/11 · Python 3.13.7 · Pillow 12.2.0 · 字体 msyh.ttc/msyhbd.ttc 存在 |
| 结果 | **228 个用例：228 通过 / 0 失败 / 0 错误 / 0 跳过；退出码 0（全绿）** |
| 耗时 | 约 2–3 s |

实际输出结尾：

```
----------------------------------------------------------------------
Ran 228 tests in 3.273s

OK

===== 汇总 =====
用例数: 228  失败: 0  错误: 0  跳过: 0
```

> **本版更新（222 → 228 用例，异环 hotfix）**
> - 按 v0.10.1 新行为更新 **13 条**旧断言（保持测试目的、未弱化覆盖）：`DailyPlanTests` 2 条、`DailyPreconditionTests` 3 条、`DailyQuotingTests` 1 条、`DailyStateMachineTests` 1 条、`V010GameExeTests` 5 条（方法更名并改为启动器优先）、`V010GameLaunchTests` 1 条。
> - 新增 **`V0101MxuUiTests` 6 条**：热键读取/缺失/globalEnabled=false 手动回退、MaaNTE 启动/attach、日志完成标记、超时/无日志/无窗口、只结束本次 pid。
> - 原有 209 条其余用例全部继续通过；`tools/test_ui_state.py`、`test_game_exe.py`、`test_game_launch.py`、`test_daily.py`、`test_launch_spec.py` 交叉复核均 rc=0 / FAILURES: none；`test_detect_game.py` rc=0。
> - 全部 mock/假时钟/临时目录：**不启动 GUI/游戏、不发送真实热键、不联网**。

## 一、测试范围与覆盖矩阵

| 测试类 | 用例数 | 覆盖点 | 结果 |
| --- | --- | --- | --- |
| `VersionTests` / `PathHelperTests` / `CleanProcsTests` / `ProcNameTests` | 3 / 5 / 5 / 1 | 版本比较、路径转换、进程名清洗 | 14 通过 |
| `ConfigStateTests` | 13 | 配置往返/BOM/损坏 JSON/Clash、config v4、detect 往返、v3→v4 迁移 | 13 通过 |
| `FindAppExeTests` / `PickBestExeTests` / `ReadVersionTests` / `ProcessTests` | 4 / 3 / 8 / 3 | 路径扫描、版本读取、进程快照 | 18 通过 |
| `RenderSmokeTests` / `ImportSmokeTests` | 8 / 2 | 旧 Pillow 渲染尺寸、`import gamehub.ui` | 10 通过 |
| `GameCandidatesTests` | 8 | v0.5 游戏启动程序自动检测 | 8 通过 |
| `DetectRuleCleanTests` / `DetectorInterfaceRulesTests` / `BuiltinRuleTableTests` | 7 / 6 / 2 | v0.6 检测规则 schema、interface.json、内置表 | 15 通过 |
| `WindowMatchTests` / `ProcMatchTests` / `GameRulesSourceTests` | 8 / 3 / 7 | 窗口/进程匹配、规则优先级 | 18 通过 |
| `DetectGameStateTests` / `DetectorSnapshotSmokeTests` | 11 / 4 | 检测状态分支、真实快照契约 | 15 通过 |
| `LaunchSpecTests` | 11 | v0.7 鸣潮启动规格/回退/路径判定/持久化 | 11 通过 |
| `DailyPlanTests` / `DailyPreconditionTests` | 6 / 6 | 四款 dry-run 命令、前置检查（含异环 mxu_ui 新行为） | 12 通过 |
| `DailyStateMachineTests` / `DailyQueueTests` / `DailyLogConfigTests` / `DailyQuotingTests` | 8 / 5 / 4 / 5 | 状态机、队列、日志/配置、命令引号 | 22 通过 |
| `SettingsTests` / `SettingsConfigTests` | 4 / 3 | settings 清洗/持久化/默认超时 | 7 通过 |
| `DailySelectionTests` / `DailyManagerTests` | 3 / 7 | 勾选过滤/顺序、每游戏独立状态 | 10 通过 |
| `UiPureLogicTests` / `ClashResolutionTests` | 3 / 3 | 刷新间隔/CHANGELOG、clash 路径（QA-15） | 6 通过 |
| `V09ThemeTests` / `SoftwareUpdateTests` | 4 / 5 | v0.9 设计令牌、软件更新纯逻辑 | 9 通过 |
| `SmallToolsTests` / `ChangelogFormatTests` | 4 / 3 | 小工具路径、更新日志纯文本 | 7 通过 |
| `V091IconTests` | 3 | 图标资产/映射/回退 | 3 通过 |
| `V010GameExeTests`（更新为启动器优先） | 5 | 见 2.1 | 5 通过 |
| `V010GameLaunchTests` | 6 | 四款启动策略/等待/回退（含异环 launcher） | 6 通过 |
| `V010WaitLaunchTests` | 4 | 等待成功/超时/提前退出、启动回退 | 4 通过 |
| `V010SettingsThemeTests` / `V010SettingsRoundTripTests` | 5 / 1 | font_scale/淡紫/圆角渐变/标题栏、settings 往返 | 6 通过 |
| `V010AutoUpdateTests` | 3 | 更新资产选择/updater 脚本/门控 | 3 通过 |
| **`V0101MxuUiTests`**（v0.10.1 新增） | 6 | 见 2.2 | 6 通过 |
| **合计** | **228** | | **228 通过 / 0 跳过** |

## 二、v0.10.1 hotfix 覆盖说明

### 2.1 异环启动回启动器（`V010GameExeTests` / `V010GameLaunchTests`）
- `GAME_EXE_HINTS["nte"][0] == "ntelauncher.exe"`；`_score_exe_path` 中 NTELauncher 分数高于 HTGame。
- `resolve_game_exe`：已是 NTELauncher 直接返回；当前为 `HTGame.exe` 时向安装根/脚本目录查找 `NTELauncher.exe` 并写回 `game_exe` + `game_procs=["NTELAUNCHER.EXE"]`；找不到启动器时保留 HTGame 原值；非异环游戏不改写。
- `find_game_candidates`：异环候选首位为 `NTELauncher.exe`（特殊优先规则合并启动器候选）。
- `load_state_full` 迁移：配置里异环指向 HTGame 且能找到启动器时自动纠正为 NTELauncher 并保存；找不到时保留 HTGame。
- `build_game_launch("nte")`：`strategy=launcher`、`exe=NTELauncher.exe`、`cwd=安装根`、`args=[]`、wait 180s（`UnrealWindow` / `HTGame.exe`）、`hint` 提示在启动器中登录并点击开始游戏、fallback `user_pick`（说明直启 HTGame 可能 UE 报错）；缺启动器时 `exe=""` + user_pick。

### 2.2 异环清日常改热键模式（`V0101MxuUiTests` 6）
- **热键读取** `daily.mxu_ui_hotkey`：支持 `settings.hotkeys.startTasks` 字符串（`"Ctrl+F10"`）或 dict（`{key, modifiers}`，modifiers 可为字符串/列表）；`globalEnabled=false`、缺失、无效键均返回 `None`。
- **日志定位** `daily.mxu_latest_log`：取 MaaNTE `debug/` 下最新 `.log`（排除 `maafw*`），无日志时回退 `mxu-tauri.log` 或空串。
- **计划** `_plan_mxu_ui`：`mode=mxu_ui`、直接打开 `MaaNTE.exe`、`cwd=安装根`、`params=""`、`argv=[exe]`、`command_text` 含 exe、携带 hotkey/log_path/attach/manual_start；已在运行 → `attach=True`（只发热键，不启动/不报错）；热键不可用 → `manual_start=True` + 「手动」提示（不静默成功）；缺 MaaNTE.exe → 明确错误；实例/任务字段可保留但不再必须。
- **执行** `_run_mxu_ui`（全部 mock 窗口/热键/进程）：
  - 启动 MaaNTE → 等待主窗口（≤60s）→ 置前 → 发送开始任务热键 → 监控最新日志；
  - 日志出现完成标记（`停止任务`/`tasks-completed`/`已停止`/`任务已全部完成`）→ `finished`；出现失败标记 → `failed`；
  - 超时 → `timeout` 且**只结束本次启动的进程**；无 debug 日志 15s → `failed` 并结束本次进程；窗口未出现 → `failed` 并结束本次进程；
  - 用户停止：非 attach 时结束本次启动的 MaaNTE（reason 含「已结束本次启动的 MaaNTE」）；attach 时**不结束用户自己打开的 MaaNTE**（reason 含「未结束用户自己打开的 MaaNTE」）；
  - 手动模式（热键不可用）→ `failed` 且保留 MaaNTE 窗口供用户手动操作（close 不 terminate）。
- 终末地仍保留 `--autostart MXU` 行为：实例自动建议/覆盖、缺实例/实例不存在/0 启用任务前置校验、进程退出 finished / 超时 timeout（`DailyPlanTests`/`DailyPreconditionTests`/`DailyStateMachineTests` 已按此拆分更新）。

### 2.3 交叉验证与既有回归
- `tools/test_ui_state.py`、`tools/test_game_exe.py`、`tools/test_game_launch.py`、`tools/test_daily.py`、`tools/test_launch_spec.py` 均 **rc=0 / FAILURES: none**；`tools/test_detect_game.py` rc=0（只读，本机当前检测到终末地运行）。
- 其余 209 条既有契约（v0.4~v0.10：detector/launch spec/清日常其余部分/settings/勾选/独立状态/图标/软件更新/标题栏/字体/自动更新）全部继续通过，无回归。
- 稳定性：本套件连续运行 2 次均 228/228 通过。

## 三、缺陷清单与状态

### 3.1 已修复项（持续回归通过）
QA-01/02（read_version 回退）、QA-03（save_state 返回 bool）、QA-04（版本比较）、QA-05（非 str 进程名）、QA-09（DisplayIcon 引号+索引）、QA-10（v4 迁移不覆盖用户进程名）、QA-11（游戏名最长/精确反查）、QA-12（字符串进程名不按空白拆分）、QA-13（extra_args 只保留 str 并 strip）、QA-14（命令参数统一引号处理）、QA-15（clash 便携相对路径还原）——全部保持通过。

### 3.2 保留项（低风险/设计边界，不阻塞 v0.10.1）
- QA-06：目录扫描跳过 `data/resources/config/build/dist` 等名字（设计取舍，建议 README FAQ 说明）。
- QA-07：自定义卡片 exe 丢失后仍以相对路径加载、无 missing 提示（建议后续排期）。
- QA-08：`_portable(path==root)` → `"."`（仅异常输入触发）。

> 本轮未发现新增阻塞性缺陷；13 条旧断言已按 v0.10.1 新行为更新并全部通过。

## 四、未覆盖点与测试限制

1. **真实热键/窗口/日志（需 Lead 实机验证）**：真实发送 `Ctrl+F10` 到 MaaNTE（焦点/热键冲突/管理员窗口）、真实 MaaNTE 主窗口检测与置前、真实 debug 最新日志的完成/失败/停止标记、超时/无日志/窗口未出现时的真实行为。自动化全部 mock 窗口/热键/日志。
2. **真实异环启动器**：NTELauncher 启动后登录/点击开始游戏、HTGame 直启 UE 报错的真实表现；启动器缺失时 user_pick 回退交互。
3. **真实 attach 场景**：用户自己打开 MaaNTE 时只发热键、停止时不结束用户实例的实机验证。
4. **真实 GUI/自动更新/标题栏/字体/小工具/清日常 UAC/日志端到端**：沿用前版未覆盖点（真实窗口视觉、下载替换 exe、拖拽/最大化、路径打开等）。
5. **打包版路径**：PyInstaller `_MEIPASS` 下资源/配置路径未在打包产物上验证。
6. **长时/并发**：跨天运行、并发点击、系统休眠唤醒未覆盖。
7. **版本号**：`VERSION` 当前仍为 `0.10.0`，发布任务 bump 为 `0.10.1` 后建议再跑一次本套件（预期仍 228/228 全绿）。

## 五、结论与建议

- **v0.10.1 hotfix 回归全绿：228/228 通过、0 失败/0 错误/0 跳过、exit 0（约 2–3 s）**；可重复执行、无副作用。
- 13 条 v0.10 旧断言已按新行为更新（未弱化覆盖），新增 6 条异环热键模式断言；其余 209 条无回归。
- 未发现新增阻塞性缺陷；QA-15 保持修复；QA-06/07/08 仍为低风险/设计边界。
- 发布前建议：① Lead 实机验证真实热键 `Ctrl+F10`、MaaNTE 窗口/日志、NTELauncher 启动与 attach 行为；② release 任务 bump `VERSION=0.10.1` 后重跑本套件（预期 228/228）；③ CI 增加 Windows runner 执行 `python tools/regression_test.py`（无需网络）。

## 附录：证据与约束遵守

- QA 只修改 `tools/regression_test.py`、`docs/qa-report.md`；未修改 `gamehub/`、`tools/test_*.py`（feature-dev 自测）、`README.md`、`CHANGELOG.md` 等；未 commit / push。
- 未启动 GUI/游戏、未发送真实热键、未联网；mxu_ui 状态机全部 mock `_mxu_ui_window`/`send_hotkey`/launcher（FakeHandle + 假时钟），日志使用临时文件。
- 配置类用例全部使用临时目录 + `mock.patch` 隔离；真实 `config.json` mtime `18:39:24`（Lead GUI 验证写入 v4），QA 运行前后未变化。
- 交叉验证：`tools/test_ui_state.py`、`tools/test_game_exe.py`、`tools/test_game_launch.py`、`tools/test_daily.py`、`tools/test_launch_spec.py` 均 rc=0 / FAILURES: none；`tools/test_detect_game.py` rc=0。
- 稳定性：本套件连续运行 2 次均 228/228 通过。
