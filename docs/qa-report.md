# All-My-Maa 回归测试报告（v0.10.5 最终版）

| 项目 | 内容 |
| --- | --- |
| 仓库 | `D:\All MAA\GameHub`（GitHub: https://github.com/Diaohesi/All-My-Maa ） |
| 被测版本 | **All-My-Maa v0.10.5**（功能快照：v0.10.4 + 异环清日常 pre_game——游戏未运行时先打开 `NTELauncher.exe` 并等待游戏窗口（最长 300 秒），确认游戏运行后再启动 `MaaNTE.exe --autostart --instance "<实例>" --quit-after-run`；游戏已运行则跳过启动器；等待超时/启动器失败不启动 MaaNTE；`gamehub.__init__.VERSION` 当前仍为 `0.10.4`，按发布流程由 release 任务 bump 为 `0.10.5`） |
| 代码基线 | `f4b638d`（release: v0.10.4） |
| 工作区增量 | `gamehub/daily.py` **+96 / -6**（`PRE_GAME_WAIT_SECONDS=300`、`_plan_mxu` 异环 pre_game 计划、`_launch_pre_game`/`_terminate_quiet`、`_run_mxu` 启动器→等待→MaaNTE 链路与本次进程清理）；`tools/test_daily.py` 同步更新；`tools/regression_test.py` 按新语义更新/新增用例；文档由文档任务更新 |
| 测试脚本 | `tools/regression_test.py`（标准库 `unittest`，v0.10.5 最终版 **239 用例 / 47 个测试类**） |
| 执行命令 | `python tools/regression_test.py`（任意 CWD 可运行；`-v` 详细输出） |
| 执行时间 | 2026-10-18（最终快照：`gamehub/daily.py` mtime 20:04:24） |
| 运行环境 | Windows 10/11 · Python 3.13.7 · Pillow 12.2.0 · 字体 msyh.ttc/msyhbd.ttc 存在 |
| 结果 | **239 个用例：239 通过 / 0 失败 / 0 错误 / 0 跳过；退出码 0（全绿）** |
| 耗时 | 约 2.0–2.6 s |

实际输出结尾：

```
----------------------------------------------------------------------
Ran 239 tests in 2.164s

OK

===== 汇总 =====
用例数: 239  失败: 0  错误: 0  跳过: 0
```

> **本版更新（235 → 239 用例，异环 pre_game 复核）**
> - 既有用例已按新语义更新：`_make_mxu_daily` 为异环提供 `NTELauncher.exe`；`DailyPreconditionTests` 改为断言 pre_game（未运行/已运行/启动器缺失）；`DailyStateMachineTests` 新增"启动器→等待→MaaNTE autostart→进程退出"链路与等待超时不启动 MXU（feature-dev 完成，回归 235/235）。
> - QA 新增 **`V0105PreGameTests` 4 条**：pre_game 计划三态、`_launch_pre_game` Popen 规格（普通权限/参数/cwd/flags）、启动器失败与等待中停止均不启动 MXU、MaaNTE 启动后停止只结束本次进程 → **239 用例**。
> - 原有其余用例全部继续通过；`tools/test_daily.py`、`test_ui_state.py`、`test_elevation.py`、`test_game_exe.py`、`test_game_launch.py`、`test_launch_spec.py` 交叉复核均 rc=0 / FAILURES: none；`test_detect_game.py` rc=0。
> - 全部 mock/假时钟/临时目录：**不启动 GUI/游戏、不实际拉起启动器、不联网**。

## 一、测试范围与覆盖矩阵

| 测试类 | 用例数 | 覆盖点 | 结果 |
| --- | --- | --- | --- |
| `VersionTests` / `PathHelperTests` / `CleanProcsTests` / `ProcNameTests` | 3 / 5 / 5 / 1 | 版本比较、路径转换、进程名清洗 | 14 通过 |
| `ConfigStateTests` | 13 | 配置往返/BOM/损坏 JSON/Clash、config v4、detect 往返、v3→v4 迁移 | 13 通过 |
| `FindAppExeTests` / `PickBestExeTests` / `ReadVersionTests` / `ProcessTests` | 4 / 3 / 8 / 3 | 路径扫描、版本读取、进程快照 | 18 通过 |
| `RenderSmokeTests` / `ImportSmokeTests` | 8 / 2 | 旧 Pillow 渲染尺寸、`import gamehub.ui` | 10 通过 |
| `GameCandidatesTests` | 8 | 游戏启动程序自动检测 | 8 通过 |
| `DetectRuleCleanTests` / `DetectorInterfaceRulesTests` / `BuiltinRuleTableTests` | 7 / 6 / 2 | 检测规则 schema、interface.json、内置表 | 15 通过 |
| `WindowMatchTests` / `ProcMatchTests` / `GameRulesSourceTests` | 8 / 3 / 7 | 窗口/进程匹配、规则优先级 | 18 通过 |
| `DetectGameStateTests` / `DetectorSnapshotSmokeTests` | 11 / 4 | 检测状态分支、真实快照契约 | 15 通过 |
| `LaunchSpecTests` | 11 | 鸣潮启动规格/回退/路径判定/持久化 | 11 通过 |
| `DailyPlanTests` / `DailyPreconditionTests` | 7 / 6 | 四款 dry-run 命令、前置（含异环 pre_game 三态） | 13 通过 |
| `DailyStateMachineTests` / `DailyQueueTests` / `DailyLogConfigTests` / `DailyQuotingTests` | 9 / 5 / 4 / 5 | 状态机（含 pre_game 链路）、队列、日志/配置、引号 | 23 通过 |
| `SettingsTests` / `SettingsConfigTests` | 4 / 3 | settings 清洗/持久化/默认超时 | 7 通过 |
| `DailySelectionTests` / `DailyManagerTests` | 3 / 7 | 勾选过滤/顺序、每游戏独立状态 | 10 通过 |
| `UiPureLogicTests` / `ClashResolutionTests` | 3 / 3 | 刷新间隔/CHANGELOG、clash 路径（QA-15） | 6 通过 |
| `V09ThemeTests` / `SoftwareUpdateTests` | 4 / 5 | 设计令牌、软件更新纯逻辑 | 9 通过 |
| `SmallToolsTests` / `ChangelogFormatTests` | 4 / 3 | 小工具路径、更新日志纯文本 | 7 通过 |
| `V091IconTests` | 3 | 图标资产/映射/回退 | 3 通过 |
| `V010GameExeTests` / `V010GameLaunchTests` | 5 / 6 | 异环启动器优先、四款启动策略 | 11 通过 |
| `V010WaitLaunchTests` / `V010SettingsThemeTests` / `V010SettingsRoundTripTests` / `V010AutoUpdateTests` | 4 / 5 / 1 / 3 | 等待/字体标题栏/settings 往返/自动更新 | 13 通过 |
| `V0103ElevationTests` | 8 | 默认管理员启动/提权/打包 manifest/权限显示 | 8 通过 |
| `V0104RevertTests` | 3 | 异环回 MXU autostart、旧热键/UIPI 无残留 | 3 通过 |
| **`V0105PreGameTests`**（v0.10.5 新增） | 4 | 见 2.1–2.3 | 4 通过 |
| **合计** | **239** | | **239 通过 / 0 跳过** |

## 二、v0.10.5 异环 pre_game 覆盖说明

### 2.1 pre_game 计划（`test_pre_game_plan_variants` + 既有前置用例）
- **游戏未运行**：`plan["pre_game"]` = `{spec: build_game_launch(nte), timeout_s: 300, hint: "将先打开异环启动器，请登录并进入游戏"}`；`spec.strategy=launcher`、`exe=NTELauncher.exe`；notes 提示先登录并点击开始游戏、确认游戏运行后再启动 MaaNTE；MXU 命令仍为 `--autostart --instance "<实例>" --quit-after-run`；无错误。
- **游戏已运行**：`pre_game` 为空（不重复打开启动器），notes 记录"已检测到异环游戏在运行"。
- **启动器缺失**：`pre_game` 为空且 `errors` 含"未找到异环启动器 NTELauncher.exe…"，不会静默继续。
- `PRE_GAME_WAIT_SECONDS == 300`；计划中不含 `hotkey/use_hotkey/manual_start/attach` 等旧热键/UIPI 字段。

### 2.2 启动器进程规格（`test_launch_pre_game_subprocess_spec`）
- `_launch_pre_game` 用 `subprocess.Popen([exe] + args, cwd=spec.cwd, close_fds=True, creationflags=0x8|0x200)`（DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP）**普通权限**启动，不强制提权。
- 启动器 exe 不存在 → `(None, "启动器不存在：…")`；Popen 抛异常 → `(None, "启动异环启动器失败：…")`（均不启动 MaaNTE）。

### 2.3 执行链路与本次进程清理（`test_pre_game_failure_and_stop_no_mxu` / `test_stop_after_mxu_only_own_processes`）
- **成功链路**：检测游戏未运行 → 启动 `NTELauncher.exe` → 等待循环（每 1s 检测游戏）→ 检测到游戏运行后启动 `MaaNTE.exe --autostart … --quit-after-run` → MXU 进程退出 → `finished`。
- **启动器失败**：直接 `failed`（reason 含"启动器"），**不调用 MXU launcher**。
- **等待中用户停止**：`stopped`（reason"用户停止（未启动 MaaNTE）"），结束本次启动器进程，**不启动 MXU**。
- **等待超时（300s）**：`failed`（reason"等待异环游戏启动超时…"），结束本次启动器进程，**不启动 MXU**（既有状态机用例覆盖）。
- **MaaNTE 启动后停止/超时**：结束本次 MXU 进程**并同时结束本次启动器进程**，结果 `pid` 为本次 MXU 句柄，绝不结束用户自己打开的进程。
- **前置仍生效**：实例缺失/实例不存在/0 启用任务/MaaNTE 已在运行（报错、不 attach）均继续覆盖（`DailyPreconditionTests`）。
- **旧热键/UIPI 无残留**：`V0104RevertTests` 继续通过（模块无旧符号、计划无旧字段、源码无 `mxu_ui`/`Ctrl+F10`/`UIPI`）。

### 2.4 交叉验证与既有回归
- `tools/test_daily.py`、`tools/test_ui_state.py`、`tools/test_elevation.py`、`tools/test_game_exe.py`、`tools/test_game_launch.py`、`tools/test_launch_spec.py` 均 **rc=0 / FAILURES: none**；`tools/test_detect_game.py` rc=0（只读）。
- 其余历史契约（v0.4~v0.10.4：detector/launch spec/清日常其余逻辑/settings/勾选/独立状态/图标/软件更新/标题栏/字体/自动更新/默认管理员启动/回 MXU 等）全部继续通过，无回归。
- 稳定性：本套件连续运行 2 次均 239/239 通过。

## 三、缺陷清单与状态

### 3.1 已修复项（持续回归通过）
QA-01/02（read_version 回退）、QA-03（save_state 返回 bool）、QA-04（版本比较）、QA-05（非 str 进程名）、QA-09（DisplayIcon 引号+索引）、QA-10（v4 迁移不覆盖用户进程名）、QA-11（游戏名最长/精确反查）、QA-12（字符串进程名不按空白拆分）、QA-13（extra_args 只保留 str 并 strip）、QA-14（命令参数统一引号处理）、QA-15（clash 便携相对路径还原）——全部保持通过。

### 3.2 保留项（低风险/设计边界，不阻塞 v0.10.5）
- QA-06：目录扫描跳过 `data/resources/config/build/dist` 等名字（设计取舍，建议 README FAQ 说明）。
- QA-07：自定义卡片 exe 丢失后仍以相对路径加载、无 missing 提示（建议后续排期）。
- QA-08：`_portable(path==root)` → `"."`（仅异常输入触发）。

> 本轮未发现新增阻塞性缺陷；pre_game 计划/启动器规格/失败与停止清理/仅结束本次进程断言全部通过。

## 四、未覆盖点与测试限制

1. **真实启动器登录交互与等待窗口（需 Lead 实机验证）**：真实 `NTELauncher.exe` 拉起、用户登录并点击"开始游戏"、300 秒内游戏窗口出现/未出现的真实时序、UI 焦点/提示。
2. **真实进程生命周期**：真实启动器进程是否在游戏启动后退出、等待超时/用户停止时结束本次启动器进程的实际效果、真实 `MaaNTE --autostart --quit-after-run` 自动开始与进程退出。
3. **真实游戏窗口检测**：`_game_running` 在异环真实进程/窗口下的判定、启动器与游戏同进程/不同进程差异。
4. **真实 UAC/默认管理员**：真实 UAC 弹窗/取消回退、打包 exe manifest（沿用 v0.10.3 未覆盖点）。
5. **真实 GUI/其他脚本/自动更新/标题栏/字体/小工具/打包 `_MEIPASS` 路径/长时并发**：沿用前版未覆盖点。
6. **版本号**：`VERSION` 当前仍为 `0.10.4`，发布任务 bump 为 `0.10.5` 后建议再跑一次本套件（预期仍 239/239 全绿）。

## 五、结论与建议

- **v0.10.5 异环 pre_game 回归全绿：239/239 通过、0 失败/0 错误/0 跳过、exit 0（约 2.0–2.6 s）**；可重复执行、无副作用。
- 异环清日常"游戏未运行→启动器→等待 300s→MaaNTE autostart→进程退出"链路、超时/失败不启动 MXU、只结束本次进程、前置与旧分支清理均覆盖；游戏已运行跳过 pre_game。
- 未发现新增阻塞性缺陷；QA-15 保持修复；QA-06/07/08 仍为低风险/设计边界。
- 发布前建议：① Lead 实机验证真实启动器登录/开始游戏交互与 300s 等待、真实 MaaNTE autostart 与进程退出；② release 任务 bump `VERSION=0.10.5` 后重跑本套件（预期 239/239）；③ CI 增加 Windows runner 执行 `python tools/regression_test.py`（无需网络）。

## 附录：证据与约束遵守

- QA 只修改 `tools/regression_test.py`、`docs/qa-report.md`；未修改 `gamehub/`、`tools/test_*.py`（feature-dev 自测）、`README.md`、`CHANGELOG.md` 等；未 commit / push。
- 未启动 GUI/游戏、**未实际拉起启动器**、未发送真实热键、未联网；pre_game 用例全部 mock `_launch_pre_game`/`subprocess.Popen`/`_game_running`/时钟与临时夹具。
- 配置类用例全部使用临时目录 + `mock.patch` 隔离；真实 `config.json` mtime `19:56:54`（Lead GUI 验证写入 v4），QA 运行前后未变化。
- 交叉验证：`tools/test_daily.py`、`tools/test_ui_state.py`、`tools/test_elevation.py`、`tools/test_game_exe.py`、`tools/test_game_launch.py`、`tools/test_launch_spec.py` 均 rc=0 / FAILURES: none；`tools/test_detect_game.py` rc=0。
- 稳定性：本套件连续运行 2 次均 239/239 通过。
