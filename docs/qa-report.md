# All-My-Maa 回归测试报告（v0.10.3 最终版）

| 项目 | 内容 |
| --- | --- |
| 仓库 | `D:\All MAA\GameHub`（GitHub: https://github.com/Diaohesi/All-My-Maa ） |
| 被测版本 | **All-My-Maa v0.10.3**（功能快照：v0.10.2 + 默认管理员启动——源码 `pythonw.exe` + ShellExecuteW(runas) 自提权、取消 UAC 回退普通权限、PyInstaller `--uac-admin`、关于/设置显示权限、`--no-elevate`/`GAMEHUB_NO_ELEVATE` 跳过、`--elevation-check` 诊断；`gamehub.__init__.VERSION` 当前仍为 `0.10.2`，按发布流程由 release 任务 bump 为 `0.10.3`） |
| 代码基线 | `86eb6f3`（docs: refresh All-My-Maa v0.10.2 screenshots） |
| 工作区增量 | 新增 `gamehub/elevation.py`（94 行：`is_admin`/`should_elevate`/`pythonw_path`/`build_relaunch`/`relaunch_as_admin`/`not_admin_message`/`elevation_status`）、`tools/test_elevation.py`（126 行）；`hub.pyw` **+26**（提权决策前置于 Pillow/UI、`--elevation-check`、UAC 取消回退）；`gamehub/ui.py` **+13**（关于/设置显示当前权限）；`tools/build_exe.bat` 与 `.github/workflows/build-exe.yml` 增加 `--uac-admin` 并保留 `--onefile/--windowed/--icon/--add-data` |
| 测试脚本 | `tools/regression_test.py`（标准库 `unittest`，v0.10.3 最终版 **240 用例 / 47 个测试类**） |
| 执行命令 | `python tools/regression_test.py`（任意 CWD 可运行；`-v` 详细输出） |
| 执行时间 | 2026-10-18（最终快照：`gamehub/elevation.py` mtime 19:22:46，`hub.pyw` mtime 19:23:10，`gamehub/ui.py` mtime 19:23:26） |
| 运行环境 | Windows 10/11 · Python 3.13.7 · Pillow 12.2.0 · 字体 msyh.ttc/msyhbd.ttc 存在 |
| 结果 | **240 个用例：240 通过 / 0 失败 / 0 错误 / 0 跳过；退出码 0（全绿）** |
| 耗时 | 约 1.8–2.5 s |

实际输出结尾：

```
----------------------------------------------------------------------
Ran 240 tests in 2.462s

OK

===== 汇总 =====
用例数: 240  失败: 0  错误: 0  跳过: 0
```

> **本版更新（232 → 240 用例，默认管理员启动）**
> - 新增 **`V0103ElevationTests` 8 条**：`should_elevate` 全矩阵、`pythonw_path`、`build_relaunch` 重启命令、`elevation_status`、`hub.pyw --elevation-check` 短进程诊断、`not_admin_message`（mock 不弹窗）、打包 manifest 标志、UI 权限显示 + hub 提权流程。
> - 原有 232 条（v0.4~v0.10.2 契约）全部继续通过；`tools/test_elevation.py`（新增）、`test_ui_state.py`、`test_daily.py`、`test_game_exe.py`、`test_game_launch.py`、`test_launch_spec.py` 交叉复核均 rc=0 / FAILURES: none。
> - **不弹真实 UAC/GUI**：提权决策、重启命令、诊断输出、打包脚本均为纯逻辑/文本/短进程校验。

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
| `DailyPlanTests` / `DailyPreconditionTests` | 6 / 6 | 四款 dry-run 命令、前置检查（含 UIPI 分流） | 12 通过 |
| `DailyStateMachineTests` / `DailyQueueTests` / `DailyLogConfigTests` / `DailyQuotingTests` | 8 / 5 / 4 / 5 | 状态机、队列、日志/配置、命令引号 | 22 通过 |
| `SettingsTests` / `SettingsConfigTests` | 4 / 3 | settings 清洗/持久化/默认超时 | 7 通过 |
| `DailySelectionTests` / `DailyManagerTests` | 3 / 7 | 勾选过滤/顺序、每游戏独立状态 | 10 通过 |
| `UiPureLogicTests` / `ClashResolutionTests` | 3 / 3 | 刷新间隔/CHANGELOG、clash 路径（QA-15） | 6 通过 |
| `V09ThemeTests` / `SoftwareUpdateTests` | 4 / 5 | 设计令牌、软件更新纯逻辑 | 9 通过 |
| `SmallToolsTests` / `ChangelogFormatTests` | 4 / 3 | 小工具路径、更新日志纯文本 | 7 通过 |
| `V091IconTests` | 3 | 图标资产/映射/回退 | 3 通过 |
| `V010GameExeTests` / `V010GameLaunchTests` | 5 / 6 | 异环启动器优先、四款启动策略 | 11 通过 |
| `V010WaitLaunchTests` / `V010SettingsThemeTests` / `V010SettingsRoundTripTests` / `V010AutoUpdateTests` | 4 / 5 / 1 / 3 | 等待/字体标题栏/settings 往返/自动更新 | 13 通过 |
| `V0101MxuUiTests` / `V0102UipiTests` | 6 / 4 | 异环热键模式与 UIPI 四分流 | 10 通过 |
| **`V0103ElevationTests`**（v0.10.3 新增） | 8 | 见 2.1–2.5 | 8 通过 |
| **合计** | **240** | | **240 通过 / 0 跳过** |

## 二、v0.10.3 默认管理员启动覆盖说明

### 2.1 提权决策 `should_elevate`（纯逻辑矩阵）
- 普通权限 + 源码模式 → **需要提权**；已是管理员 → 不提权；frozen（打包版由 manifest 负责）→ 不提权。
- `--no-elevate`、`--elevated`（自重启子进程标记）、环境变量 `GAMEHUB_NO_ELEVATE` 真值（`1/true/YES/on`，含空白/大小写）→ **跳过提权**；假值/空串/其它参数 → 仍提权。
- `_env_flag` 归一：大小写、前后空白、`TRUE` 等。

### 2.2 自重启命令 `build_relaunch` / `pythonw_path`
- `verb=runas`；`file` 优先 `pythonw.exe`（同目录存在则用；已是 pythonw 原样；不存在回退原解释器）。
- `params` = `"<hub 绝对路径>" --elevated [extra_args...]`——**hub 路径始终加引号**（含空格也安全）；`cwd` 默认 app_dir 或 hub 所在目录；`show=1`。
- 空/None 路径时 `pythonw_path` 仍优先返回解释器同目录的 pythonw.exe。

### 2.3 状态 / 诊断
- `elevation_status`：返回 `{admin, frozen, would_elevate, pythonw}`；管理员 true 时不重复提权；`--no-elevate`/env 让 `would_elevate=false`；frozen 时 false。
- `hub.pyw --elevation-check` 短进程（subprocess，**不启动 GUI/UAC**）：rc=0、输出末行合法 JSON、含 admin/frozen/would_elevate/pythonw、无 Traceback；env `GAMEHUB_NO_ELEVATE=1` 与 `--no-elevate` 均使 `would_elevate=false`。
- `not_admin_message`（mock `ctypes`，**不弹真实窗口**）：调用 MessageBoxW(0, 文案,「All-My-Maa · 权限提示」, 0x40)，文案含「未获得管理员权限」「普通权限」及异环热键/脚本功能提示。

### 2.4 打包 manifest 标志
- `tools/build_exe.bat` 与 `.github/workflows/build-exe.yml` 均含 `--uac-admin`，并保留 `--onefile`、`--windowed`、`--icon`（`assets\hub.ico` / `assets/hub.ico`）、`--add-data "assets;assets"`、入口 `hub.pyw`、名称 `GameHub`。
- `hub.pyw`：提权决策在 Pillow 检查与 `gamehub.ui` 导入**之前**；`relaunch_as_admin` 返回 >32 视为成功并以管理员子进程继续；否则调用 `not_admin_message` 后**以普通权限继续启动**（UAC 取消回退）。

### 2.5 UI 权限显示
- 关于对话框与设置页均显示「当前权限：管理员 / 普通用户」，并提示「默认以管理员身份启动（UAC）；取消 UAC 会以普通权限运行，异环清日常热键/部分脚本功能可能受限」；源码使用 `store.hub_is_elevated()` 判断。

### 2.6 交叉验证与既有回归
- `tools/test_elevation.py`（feature-dev 新增）rc=0 / FAILURES: none；`tools/test_ui_state.py`、`test_daily.py`、`test_game_exe.py`、`test_game_launch.py`、`test_launch_spec.py` 均 **rc=0 / FAILURES: none**。
- 其余 232 条既有契约（v0.4~v0.10.2）全部继续通过，无回归。
- 稳定性：本套件连续运行 2 次均 240/240 通过。

## 三、缺陷清单与状态

### 3.1 已修复项（持续回归通过）
QA-01/02（read_version 回退）、QA-03（save_state 返回 bool）、QA-04（版本比较）、QA-05（非 str 进程名）、QA-09（DisplayIcon 引号+索引）、QA-10（v4 迁移不覆盖用户进程名）、QA-11（游戏名最长/精确反查）、QA-12（字符串进程名不按空白拆分）、QA-13（extra_args 只保留 str 并 strip）、QA-14（命令参数统一引号处理）、QA-15（clash 便携相对路径还原）——全部保持通过。

### 3.2 保留项（低风险/设计边界，不阻塞 v0.10.3）
- QA-06：目录扫描跳过 `data/resources/config/build/dist` 等名字（设计取舍，建议 README FAQ 说明）。
- QA-07：自定义卡片 exe 丢失后仍以相对路径加载、无 missing 提示（建议后续排期）。
- QA-08：`_portable(path==root)` → `"."`（仅异常输入触发）。

> 本轮未发现新增阻塞性缺陷；提权决策/重启命令/打包标志/权限显示断言全部通过。

## 四、未覆盖点与测试限制

1. **真实 UAC 弹窗/取消回退（需 Lead 实机验证）**：双击源码 hub.pyw 触发真实 UAC、用户取消后以普通权限继续启动并显示提示、确认提权后管理员子进程正常进入 GUI；测试只验证决策/命令/回退分支，**不弹真实 UAC**。
2. **打包 exe 的真实 manifest**：`--uac-admin` 生成的 GameHub.exe 在双击时是否弹出 UAC、manifest requestedExecutionLevel 实际生效、取消后的行为需在打包产物上验证（当前仅校验构建脚本/工作流文本）。
3. **真实权限显示**：关于/设置页 GUI 文案的实际渲染与提权前后切换（自动化只校验源码字符串与 `store.hub_is_elevated` 调用）。
4. **真实提权后的功能收益**：异环清日常 Ctrl+F10 热键、脚本输入/截图等在高完整性下的实际效果需实机确认。
5. **pythonw 路径异常安装**：特殊 Python 安装（无 pythonw.exe、Store 版 Python）下的重启命令未实测。
6. **其它沿用前版未覆盖点**：真实游戏启动/等待、自动更新下载替换、标题栏拖拽/最大化、模拟器/云游戏、打包 `_MEIPASS` 路径、长时/并发等。
7. **版本号**：`VERSION` 当前仍为 `0.10.2`，发布任务 bump 为 `0.10.3` 后建议再跑一次本套件（预期仍 240/240 全绿）。

## 五、结论与建议

- **v0.10.3 默认管理员启动回归全绿：240/240 通过、0 失败/0 错误/0 跳过、exit 0（约 1.8–2.5 s）**；可重复执行、无副作用、不弹真实 UAC/GUI。
- 原有 232 条无回归；新增 8 条覆盖提权决策/重启命令/诊断/打包标志/权限显示。
- 未发现新增阻塞性缺陷；QA-15 保持修复；QA-06/07/08 仍为低风险/设计边界。
- 发布前建议：① Lead 实机验证真实 UAC 弹窗与取消回退、打包 exe 的 `--uac-admin` manifest 生效、权限显示；② release 任务 bump `VERSION=0.10.3` 后重跑本套件（预期 240/240）；③ CI 增加 Windows runner 执行 `python tools/regression_test.py`（无需网络）。

## 附录：证据与约束遵守

- QA 只修改 `tools/regression_test.py`、`docs/qa-report.md`；未修改 `gamehub/`、`hub.pyw`、`tools/test_*.py`（feature-dev 自测）、构建脚本、`README.md`、`CHANGELOG.md` 等；未 commit / push。
- 未启动 GUI/游戏、**未实际弹 UAC**、未发送真实热键、未联网；提权相关断言全部为纯函数/文本/短进程 `--elevation-check` 校验，`not_admin_message` 通过 mock 不弹窗。
- 配置类用例全部使用临时目录 + `mock.patch` 隔离；真实 `config.json` mtime `19:25:23`（Lead GUI 验证写入 v4），QA 运行前后未变化。
- 交叉验证：`tools/test_elevation.py`、`tools/test_ui_state.py`、`tools/test_daily.py`、`tools/test_game_exe.py`、`tools/test_game_launch.py`、`tools/test_launch_spec.py` 均 rc=0 / FAILURES: none。
- 稳定性：本套件连续运行 2 次均 240/240 通过。
