# All-My-Maa 回归测试报告（v0.10.4 最终版）

| 项目 | 内容 |
| --- | --- |
| 仓库 | `D:\All MAA\GameHub`（GitHub: https://github.com/Diaohesi/All-My-Maa ） |
| 被测版本 | **All-My-Maa v0.10.4**（功能快照：v0.10.3 + 异环清日常回退为终末地同款 `MaaNTE.exe --autostart --instance "<实例>" --quit-after-run`（按进程退出完成，删除旧 Ctrl+F10 热键/UIPI 分支）；`gamehub.__init__.VERSION` 当前仍为 `0.10.3`，按发布流程由 release 任务 bump 为 `0.10.4`） |
| 代码基线 | `8ccac24`（release: v0.10.3） |
| 工作区增量 | `gamehub/daily.py` **+18 / -406**（删除 `mxu_ui_hotkey`/`mxu_latest_log`/`mxu_autostart_instance`/`mxu_target_elevated`/`mxu_ui_hint`/`_plan_mxu_ui`/`_run_mxu_ui`/`MXU_UI_*`；异环归入 `_plan_mxu`/`_run_mxu`；`_suggest_mxu_instance` 支持 `autoStartInstanceId`（id/uuid/name）与"首个有启用任务实例"）、`gamehub/ui.py` **+1 / -19**（删除异环热键/UIPI 提示，改为显示计划 reason）；`tools/test_daily.py` 同步更新；`tools/regression_test.py` 已按新语义精简旧 mxu_ui/UIPI 用例 |
| 测试脚本 | `tools/regression_test.py`（标准库 `unittest`，v0.10.4 最终版 **234 用例 / 46 个测试类**） |
| 执行命令 | `python tools/regression_test.py`（任意 CWD 可运行；`-v` 详细输出） |
| 执行时间 | 2026-10-18（最终快照：`gamehub/daily.py` mtime 19:48:29，`gamehub/ui.py` mtime 19:46:30） |
| 运行环境 | Windows 10/11 · Python 3.13.7 · Pillow 12.2.0 · 字体 msyh.ttc/msyhbd.ttc 存在 |
| 结果 | **234 个用例：234 通过 / 0 失败 / 0 错误 / 0 跳过；退出码 0（全绿）** |
| 耗时 | 约 1.9–2.6 s |

实际输出结尾：

```
----------------------------------------------------------------------
Ran 234 tests in 1.993s

OK

===== 汇总 =====
用例数: 234  失败: 0  错误: 0  跳过: 0
```

> **本版更新（231 → 234 用例，异环回 MXU autostart 复核）**
> - v0.10.3 的 240 条中包含 10 条旧 mxu_ui/UIPI 用例（`V0101MxuUiTests` 6 + `V0102UipiTests` 4），随功能回退已删除；按新语义更新既有异环/终末地断言并新增 1 条"异环与终末地命令形状一致"用例（feature-dev 完成，回归 231/231）。
> - QA 新增 **`V0104RevertTests` 3 条**复核：旧 mxu_ui/UIPI 无残留、实例推断（autoStartInstanceId id/uuid/name、首个启用任务实例、显式覆盖）、异环与终末地计划形状一致性 + 清日常勾选/顺序无回归 → **234 用例**。
> - 原有其余用例全部继续通过；`tools/test_daily.py`、`test_ui_state.py`、`test_elevation.py`、`test_game_exe.py`、`test_game_launch.py`、`test_launch_spec.py` 交叉复核均 rc=0 / FAILURES: none；`test_detect_game.py` rc=0。
> - 全部 mock/假时钟/临时目录：**不启动 GUI/游戏、不发送真实热键、不联网**。

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
| `DailyPlanTests` / `DailyPreconditionTests` | 7 / 6 | 四款 dry-run 命令、前置检查（异环/终末地同款 MXU） | 13 通过 |
| `DailyStateMachineTests` / `DailyQueueTests` / `DailyLogConfigTests` / `DailyQuotingTests` | 8 / 5 / 4 / 5 | 状态机、队列、日志/配置、命令引号 | 22 通过 |
| `SettingsTests` / `SettingsConfigTests` | 4 / 3 | settings 清洗/持久化/默认超时 | 7 通过 |
| `DailySelectionTests` / `DailyManagerTests` | 3 / 7 | 勾选过滤/顺序、每游戏独立状态 | 10 通过 |
| `UiPureLogicTests` / `ClashResolutionTests` | 3 / 3 | 刷新间隔/CHANGELOG、clash 路径（QA-15） | 6 通过 |
| `V09ThemeTests` / `SoftwareUpdateTests` | 4 / 5 | 设计令牌、软件更新纯逻辑 | 9 通过 |
| `SmallToolsTests` / `ChangelogFormatTests` | 4 / 3 | 小工具路径、更新日志纯文本 | 7 通过 |
| `V091IconTests` | 3 | 图标资产/映射/回退 | 3 通过 |
| `V010GameExeTests` / `V010GameLaunchTests` | 5 / 6 | 异环启动器优先、四款启动策略 | 11 通过 |
| `V010WaitLaunchTests` / `V010SettingsThemeTests` / `V010SettingsRoundTripTests` / `V010AutoUpdateTests` | 4 / 5 / 1 / 3 | 等待/字体标题栏/settings 往返/自动更新 | 13 通过 |
| `V0103ElevationTests` | 8 | 默认管理员启动/提权/打包 manifest/权限显示 | 8 通过 |
| **`V0104RevertTests`**（v0.10.4 新增） | 3 | 见 2.1–2.3 | 3 通过 |
| **合计** | **234** | | **234 通过 / 0 跳过** |

## 二、v0.10.4 异环清日常回 MXU 覆盖说明

### 2.1 命令形状与旧分支清理（`test_mxu_ui_and_uipi_removed` / `test_nte_maaend_plan_parity`）
- 异环计划与终末地同款：`mode="mxu"`、`args=["--autostart", "--instance", "<实例>", "--quit-after-run"]`、`params` 中实例名强制加引号、`argv=[MaaNTE.exe, --autostart, --instance, <实例>, --quit-after-run]`、超时 120 分钟（终末地 150）、无错误；`command_text` 含 `MaaNTE.exe` / `MaaEnd.exe`。
- **旧 mxu_ui/UIPI 无残留**：`daily` 不再导出 `mxu_ui_hotkey`/`mxu_latest_log`/`mxu_autostart_instance`/`mxu_target_elevated`/`mxu_ui_hint`/`_plan_mxu_ui`/`_run_mxu_ui`/`_mxu_ui_window`/`MXU_UI_*`；计划中不再出现 `hotkey/use_hotkey/manual_start/manual_reason/elevated/target_elevated/attach/autostart_instance` 字段；`gamehub/daily.py`、`gamehub/ui.py` 源码不再含 `mxu_ui`/`Ctrl+F10`/`UIPI` 等旧分支。

### 2.2 实例推断与覆盖（`test_instance_inference_autostart_and_override`）
- `autoStartInstanceId` 优先：按实例 `id`、`uuid`、`name` 匹配 → 对应实例名。
- 未配置 autoStart：取**第一个有启用任务**的实例（跳过 0 任务实例）；无实例/全部未启用 → `""`（计划报"未选择实例/没有可用实例"错误）。
- 用户 `daily.instance` 显式设置覆盖 autoStart 推断（命令中 `--instance` 使用用户值）。
- 默认建议保持不变：异环「挂机任务」、终末地「全套日常」。

### 2.3 前置检查 / 完成判定 / 队列与独立状态
- **前置**（异环与终末地同一条路径，两 key 均覆盖）：MXU 配置缺失 → 错误；实例名不存在 → 错误并列出可用实例；实例 0 启用任务 → 错误；脚本已在运行 → 错误（不再 attach）；实例无 `LaunchGamePC` 且游戏未运行 → 错误/警告，含 `LaunchGamePC` 前置则通过。
- **完成判定**：MXU 进程退出 → `finished`（`--quit-after-run`，不区分成败）；超时 → `timeout` 并结束本次进程；两者均已有断言（`DailyStateMachineTests`，异环与终末地各覆盖）。
- **队列/独立状态**：`DailyManager` 每游戏独立状态、start/stop、队列顺序/禁用跳过/失败继续/停止剩余、`daily_order` 勾选顺序等 v0.8 用例继续通过；`enabled_daily_keys` 仍包含异环与终末地。

### 2.4 交叉验证与既有回归
- `tools/test_daily.py`、`tools/test_ui_state.py`、`tools/test_elevation.py`、`tools/test_game_exe.py`、`tools/test_game_launch.py`、`tools/test_launch_spec.py` 均 **rc=0 / FAILURES: none**；`tools/test_detect_game.py` rc=0（只读）。
- 其余历史契约（v0.4~v0.10.3：detector/launch spec/清日常其余逻辑/settings/勾选/独立状态/图标/软件更新/标题栏/字体/自动更新/默认管理员启动等）全部继续通过，无回归。
- 稳定性：本套件连续运行 2 次均 234/234 通过。

## 三、缺陷清单与状态

### 3.1 已修复项（持续回归通过）
QA-01/02（read_version 回退）、QA-03（save_state 返回 bool）、QA-04（版本比较）、QA-05（非 str 进程名）、QA-09（DisplayIcon 引号+索引）、QA-10（v4 迁移不覆盖用户进程名）、QA-11（游戏名最长/精确反查）、QA-12（字符串进程名不按空白拆分）、QA-13（extra_args 只保留 str 并 strip）、QA-14（命令参数统一引号处理）、QA-15（clash 便携相对路径还原）——全部保持通过。

### 3.2 保留项（低风险/设计边界，不阻塞 v0.10.4）
- QA-06：目录扫描跳过 `data/resources/config/build/dist` 等名字（设计取舍，建议 README FAQ 说明）。
- QA-07：自定义卡片 exe 丢失后仍以相对路径加载、无 missing 提示（建议后续排期）。
- QA-08：`_portable(path==root)` → `"."`（仅异常输入触发）。

> 本轮未发现新增阻塞性缺陷；旧 mxu_ui/UIPI 分支代码与测试均已清理，无残留断言。

## 四、未覆盖点与测试限制

1. **真实 `--autostart --instance` 自动开始与进程退出（需 Lead 实机验证）**：真实 MaaNTE 以 `--autostart --instance "<实例>" --quit-after-run` 启动后是否自动开始任务、任务完成后是否自动退出、`--quit-after-run` 实际行为与失败场景。
2. **真实 MXU 实例配置/日志**：不同 MaaNTE/MaaEnd 版本的实例 `id`/`uuid`/`autoStartInstanceId` 结构、启用任务判定、真实日志/进程退出时序。
3. **真实队列/独立状态**：真实逐游戏执行、停止后剩余队列、脚本已运行报错在真实进程上的表现。
4. **真实 UAC/默认管理员**：真实 UAC 弹窗/取消回退、打包 exe manifest（沿用 v0.10.3 未覆盖点）。
5. **真实 GUI/游戏启动/自动更新/标题栏/字体/小工具/打包 `_MEIPASS` 路径/长时并发**：沿用前版未覆盖点。
6. **版本号**：`VERSION` 当前仍为 `0.10.3`，发布任务 bump 为 `0.10.4` 后建议再跑一次本套件（预期仍 234/234 全绿）。

## 五、结论与建议

- **v0.10.4 异环回 MXU autostart 回归全绿：234/234 通过、0 失败/0 错误/0 跳过、exit 0（约 1.9–2.6 s）**；可重复执行、无副作用。
- 异环与终末地清日常命令形状一致（`--autostart --instance "<实例>" --quit-after-run`），实例推断/覆盖、前置检查、进程退出完成、超时、队列/独立状态均覆盖；旧热键/UIPI 分支代码与测试无残留。
- 未发现新增阻塞性缺陷；QA-15 保持修复；QA-06/07/08 仍为低风险/设计边界。
- 发布前建议：① Lead 实机验证真实 `--autostart --instance` 自动开始与 `--quit-after-run` 进程退出；② release 任务 bump `VERSION=0.10.4` 后重跑本套件（预期 234/234）；③ CI 增加 Windows runner 执行 `python tools/regression_test.py`（无需网络）。

## 附录：证据与约束遵守

- QA 只修改 `tools/regression_test.py`、`docs/qa-report.md`；未修改 `gamehub/`、`tools/test_*.py`（feature-dev 自测）、`README.md`、`CHANGELOG.md` 等；未 commit / push。
- 未启动 GUI/游戏、未发送真实热键、未联网；清日常用例全部 mock 进程/日志/时钟，仅做纯逻辑与临时夹具断言。
- 配置类用例全部使用临时目录 + `mock.patch` 隔离；真实 `config.json` mtime `19:43:04`（Lead GUI 验证写入 v4），QA 运行前后未变化。
- 交叉验证：`tools/test_daily.py`、`tools/test_ui_state.py`、`tools/test_elevation.py`、`tools/test_game_exe.py`、`tools/test_game_launch.py`、`tools/test_launch_spec.py` 均 rc=0 / FAILURES: none；`tools/test_detect_game.py` rc=0。
- 稳定性：本套件连续运行 2 次均 234/234 通过。
