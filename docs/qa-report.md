# All-My-Maa 回归测试报告（v0.10.2 最终版）

| 项目 | 内容 |
| --- | --- |
| 仓库 | `D:\All MAA\GameHub`（GitHub: https://github.com/Diaohesi/All-My-Maa ） |
| 被测版本 | **All-My-Maa v0.10.2**（功能快照：v0.10.1 + 异环清日常 UIPI 提权分流——提权走 Ctrl+F10；非提权未运行走 `--autostart --instance`；非提权 + 高权限 MaaNTE 走手动/管理员重启提示；普通权限 MaaNTE 仍可发热键；`gamehub.__init__.VERSION` 当前仍为 `0.10.1`，按发布流程由 release 任务 bump 为 `0.10.2`） |
| 代码基线 | `0f998e5`（docs: add AI project recreation prompt suite） |
| 工作区增量 | `gamehub/daily.py` **+189 / -63**（`mxu_autostart_instance`/`mxu_target_elevated`/`mxu_ui_hint`、`_plan_mxu_ui` 四分流、`_run_mxu_ui` autostart/手动分支）、`gamehub/store.py` **+47 / -0**（`hub_is_elevated`/`process_is_elevated` 权限判定）、`gamehub/ui.py` +20/-1（异环行提示按提权/目标权限切换）；`tools/test_daily.py` 同步更新；文档由文档任务更新 |
| 测试脚本 | `tools/regression_test.py`（标准库 `unittest`，v0.10.2 最终版 **232 用例 / 46 个测试类**） |
| 执行命令 | `python tools/regression_test.py`（任意 CWD 可运行；`-v` 详细输出） |
| 执行时间 | 2026-10-18（最终快照：`gamehub/daily.py` mtime 19:06:32，`gamehub/store.py` mtime 19:06:28，`gamehub/ui.py` mtime 19:06:35） |
| 运行环境 | Windows 10/11 · Python 3.13.7 · Pillow 12.2.0 · 字体 msyh.ttc/msyhbd.ttc 存在 |
| 结果 | **232 个用例：232 通过 / 0 失败 / 0 错误 / 0 跳过；退出码 0（全绿）** |
| 耗时 | 约 1.8–2.2 s |

实际输出结尾：

```
----------------------------------------------------------------------
Ran 232 tests in 2.133s

OK

===== 汇总 =====
用例数: 232  失败: 0  错误: 0  跳过: 0
```

> **本版更新（228 → 232 用例，UIPI 提权分流）**
> - 按 UIPI 新行为更新 **6 条**旧断言（保持测试目的，未弱化覆盖）：`DailyPlanTests.test_dry_run_four_commands`、`DailyPlanTests.test_mxu_plan_instance_auto_and_override`、`V0101MxuUiTests.test_mxu_ui_plan_launch_attach_manual`、`test_run_mxu_ui_finished`、`test_run_mxu_ui_manual_and_stop`、`test_run_mxu_ui_timeout_missing_log_window`。
> - 新增 **`V0102UipiTests` 4 条**：权限判定 helpers、autoStart 实例/提示文案、计划四分流、非提权 autostart/attach 手动执行。
> - 原有 222 条其余用例全部继续通过；`tools/test_ui_state.py`、`test_daily.py`、`test_game_exe.py`、`test_game_launch.py`、`test_launch_spec.py` 交叉复核均 rc=0 / FAILURES: none；`test_detect_game.py` rc=0。
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
| `LaunchSpecTests` | 11 | 鸣潮启动规格/回退/路径判定/持久化 | 11 通过 |
| `DailyPlanTests` / `DailyPreconditionTests` | 6 / 6 | 四款 dry-run 命令、前置检查（含异环 UIPI 分流） | 12 通过 |
| `DailyStateMachineTests` / `DailyQueueTests` / `DailyLogConfigTests` / `DailyQuotingTests` | 8 / 5 / 4 / 5 | 状态机、队列、日志/配置、命令引号 | 22 通过 |
| `SettingsTests` / `SettingsConfigTests` | 4 / 3 | settings 清洗/持久化/默认超时 | 7 通过 |
| `DailySelectionTests` / `DailyManagerTests` | 3 / 7 | 勾选过滤/顺序、每游戏独立状态 | 10 通过 |
| `UiPureLogicTests` / `ClashResolutionTests` | 3 / 3 | 刷新间隔/CHANGELOG、clash 路径（QA-15） | 6 通过 |
| `V09ThemeTests` / `SoftwareUpdateTests` | 4 / 5 | v0.9 设计令牌、软件更新纯逻辑 | 9 通过 |
| `SmallToolsTests` / `ChangelogFormatTests` | 4 / 3 | 小工具路径、更新日志纯文本 | 7 通过 |
| `V091IconTests` | 3 | 图标资产/映射/回退 | 3 通过 |
| `V010GameExeTests` / `V010GameLaunchTests` | 5 / 6 | 异环启动器优先、四款启动策略 | 11 通过 |
| `V010WaitLaunchTests` / `V010SettingsThemeTests` / `V010SettingsRoundTripTests` / `V010AutoUpdateTests` | 4 / 5 / 1 / 3 | 等待/字体标题栏/settings 往返/自动更新 | 13 通过 |
| `V0101MxuUiTests` | 6 | 异环热键模式（提权路径，含 attach/manual/超时） | 6 通过 |
| **`V0102UipiTests`**（v0.10.2 新增） | 4 | 见 2.2–2.4 | 4 通过 |
| **合计** | **232** | | **232 通过 / 0 跳过** |

## 二、v0.10.2 UIPI 提权分流覆盖说明

### 2.1 权限判定 helpers（`V0102UipiTests.test_elevation_helpers`）
- `store.hub_is_elevated`：`IsUserAnAdmin()` 返回真/假正确映射；调用异常时安全回退 `False`。
- `store.process_is_elevated`：非法 pid（`0`/`None`）不崩溃、返回 `None`。
- `daily.mxu_target_elevated`：读不到 MaaNTE pid → **保守视为高权限**；任一 pid 提权 → True；全部普通权限 → False；权限未知/混合 → True；自定义 `script_procs` 正确传给 `pids_for_procs`。

### 2.2 计划四分流（`test_plan_four_branches`）
1. **Hub 提权** → `elevated=True`、`use_hotkey=True`、`args=[]`、热键 `Ctrl + F10`、无 `--autostart`；
2. **非提权 + MaaNTE 未运行** → `--autostart --instance "<autoStart 实例>"`（参数串实例名带引号、**无 `--quit-after-run`**、`use_hotkey=False`、`manual_start=False`、无错误）；
3. **非提权 + MaaNTE 已运行 + 高权限** → `attach=True`、`manual_start=True`、`use_hotkey=False`，`manual_reason` 含「非管理员」「管理员身份重启」；
4. **非提权 + MaaNTE 已运行 + 普通权限** → `attach=True`、`use_hotkey=True`、`manual_start=False`（普通权限可发热键）；
- 附加：非提权未运行且无可用实例 → `manual_start=True`（reason 含「未找到可用 MXU 实例」）、`args=[]`。

### 2.3 autoStart 实例与 UI 提示（`test_autostart_instance_and_hint`）
- `mxu_autostart_instance`：优先按 `settings.autoStartInstanceId` 匹配实例 `id`/`uuid`/`name`；否则取第一个有启用任务的实例名；无实例/无启用任务 → `""`。
- `mxu_ui_hint` 四分支文案：提权或「attach + 普通权限」→ Ctrl+F10；非提权 attach 高权限 → 「无法发送热键…管理员身份重启」；非提权未运行 → 「自动开始任务（不发送热键）」。

### 2.4 执行分流（`test_run_nonadmin_autostart_and_attach_manual`）
- **非提权 autostart**：launcher 收到的参数含 `--autostart --instance "挂机任务"`、不含 `--quit-after-run`；**不发送热键**；日志出现完成标记 → `finished`；进程句柄正常关闭。
- **非提权 attach 高权限**：不启动 MaaNTE、不发送热键；结果为 `failed`，reason 含「非管理员」「管理员身份重启」，`pid=None`（不结束用户自己的实例）。
- 提权路径沿用并继续通过：启动 → 等窗口 → 焦点 → `Ctrl+F10` → 监控日志；完成/失败/超时/无日志/无窗口；停止时非 attach 只结束本次进程、attach 不结束用户实例；热键不可用手动提示。

### 2.5 交叉验证与既有回归
- `tools/test_ui_state.py`、`tools/test_daily.py`、`tools/test_game_exe.py`、`tools/test_game_launch.py`、`tools/test_launch_spec.py` 均 **rc=0 / FAILURES: none**；`tools/test_detect_game.py` rc=0（只读）。
- 其余 222 条既有契约（v0.4~v0.10.1：detector/launch spec/清日常/settings/勾选/独立状态/图标/软件更新/标题栏/字体/自动更新等）全部继续通过，无回归。
- 稳定性：本套件连续运行 2 次均 232/232 通过。

## 三、缺陷清单与状态

### 3.1 已修复项（持续回归通过）
QA-01/02（read_version 回退）、QA-03（save_state 返回 bool）、QA-04（版本比较）、QA-05（非 str 进程名）、QA-09（DisplayIcon 引号+索引）、QA-10（v4 迁移不覆盖用户进程名）、QA-11（游戏名最长/精确反查）、QA-12（字符串进程名不按空白拆分）、QA-13（extra_args 只保留 str 并 strip）、QA-14（命令参数统一引号处理）、QA-15（clash 便携相对路径还原）——全部保持通过。

### 3.2 保留项（低风险/设计边界，不阻塞 v0.10.2）
- QA-06：目录扫描跳过 `data/resources/config/build/dist` 等名字（设计取舍，建议 README FAQ 说明）。
- QA-07：自定义卡片 exe 丢失后仍以相对路径加载、无 missing 提示（建议后续排期）。
- QA-08：`_portable(path==root)` → `"."`（仅异常输入触发）。

> 本轮未发现新增阻塞性缺陷；6 条旧断言已按 UIPI 新行为更新并全部通过。

## 四、未覆盖点与测试限制

1. **真实 UIPI 行为（需 Lead 实机验证）**：非管理员 Hub 向高权限 MaaNTE 发送 `Ctrl+F10` 被系统拦截的真实表现、`--autostart --instance` 自动开始任务的实际效果、真实日志完成/失败 marker 与超时/无日志分支。
2. **真实权限判定**：`hub_is_elevated`/`process_is_elevated` 在受保护进程、跨会话/不同完整性级别下的真实返回值；测试中 `hub_is_elevated` 用 mock、`process_is_elevated` 仅验证非法 pid 安全路径。
3. **真实 attach/手动场景**：用户自己打开的 MaaNTE（普通/高权限）停止时不结束用户实例的实机验证。
4. **真实 GUI/自动更新/标题栏/字体/小工具/清日常 UAC/日志端到端**：沿用前版未覆盖点。
5. **打包版路径**：PyInstaller `_MEIPASS` 下资源/配置路径未在打包产物上验证。
6. **长时/并发**：跨天运行、并发点击、系统休眠唤醒未覆盖。
7. **版本号**：`VERSION` 当前仍为 `0.10.1`，发布任务 bump 为 `0.10.2` 后建议再跑一次本套件（预期仍 232/232 全绿）。

## 五、结论与建议

- **v0.10.2 UIPI 分流回归全绿：232/232 通过、0 失败/0 错误/0 跳过、exit 0（约 1.8–2.2 s）**；可重复执行、无副作用。
- 6 条 v0.10.1 旧断言已按 UIPI 新行为更新（未弱化覆盖），新增 4 条权限分流断言；其余 222 条无回归。
- 未发现新增阻塞性缺陷；QA-15 保持修复；QA-06/07/08 仍为低风险/设计边界。
- 发布前建议：① Lead 实机验证真实 UIPI 场景（非管理员 Hub + 高权限 MaaNTE 手动提示、非管理员 + 未运行 `--autostart` 自动开始、普通权限热键）；② release 任务 bump `VERSION=0.10.2` 后重跑本套件（预期 232/232）；③ CI 增加 Windows runner 执行 `python tools/regression_test.py`（无需网络）。

## 附录：证据与约束遵守

- QA 只修改 `tools/regression_test.py`、`docs/qa-report.md`；未修改 `gamehub/`、`tools/test_*.py`（feature-dev 自测）、`README.md`、`CHANGELOG.md` 等；未 commit / push。
- 未启动 GUI/游戏、未发送真实热键、未联网；UIPI 分支全部 mock `store.hub_is_elevated`/`daily.mxu_target_elevated`/`pids_for_procs`/`process_is_elevated` 或纯函数断言，执行路径使用 FakeHandle + 假时钟。
- 配置类用例全部使用临时目录 + `mock.patch` 隔离；真实 `config.json` mtime `19:03:01`（Lead GUI 验证写入 v4），QA 运行前后未变化。
- 交叉验证：`tools/test_ui_state.py`、`tools/test_daily.py`、`tools/test_game_exe.py`、`tools/test_game_launch.py`、`tools/test_launch_spec.py` 均 rc=0 / FAILURES: none；`tools/test_detect_game.py` rc=0。
- 稳定性：本套件连续运行 2 次均 232/232 通过。
