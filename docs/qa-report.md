# GameHub 回归测试报告（v0.7.0 最终版）

| 项目 | 内容 |
| --- | --- |
| 仓库 | `D:\All MAA\GameHub`（GitHub: https://github.com/Diaohesi/ALL-MY-MAA ） |
| 被测版本 | GameHub Lite **v0.7.0**（功能快照：v0.6.0 + 鸣潮启动修复（launch spec）+ 一键清日常/顺序队列 + QA-13/14 修复；`gamehub.__init__.VERSION` 当前仍为 `0.6.0`，按发布流程由 release 任务 bump 为 `0.7.0`） |
| 代码基线 | `97d01db`（docs: refresh v0.6.0 screenshots and test counts，已发布 v0.6.0） |
| 工作区增量 | 新增 `gamehub/daily.py`（1228 行）、`tools/test_daily.py`、`tools/test_launch_spec.py`、`docs/daily-automation-research.md`；`gamehub/store.py` **+464 / -6**（launch spec、daily 配置、`load_state_full`/`daily_order`、QA-13 修复）、`gamehub/ui.py` **+670 / -11**（一键清日常工具栏/卡片链接/队列对话框/设置）、`gamehub/theme.py` +6/-5、`gamehub/detector.py` +2/-31（v0.7 适配）；`gamehub/daily.py` 含 QA-14 统一命令构建（`_build_command`/`_quote_arg`） |
| 测试脚本 | `tools/regression_test.py`（标准库 `unittest`，v0.7 最终版 **156 用例 / 27 个测试类**） |
| 执行命令 | `python tools/regression_test.py`（任意 CWD 可运行；`-v` 详细输出） |
| 执行时间 | 2026-10-18（最终快照：`gamehub/daily.py` mtime 16:10:02，`gamehub/store.py` mtime 16:08:43，`gamehub/ui.py` mtime 16:02:16） |
| 运行环境 | Windows 10/11 · Python 3.13.7 · Pillow 12.2.0 · 字体 msyh.ttc/msyhbd.ttc 存在 |
| 结果 | **156 个用例：156 通过 / 0 失败 / 0 错误 / 0 跳过；退出码 0（全绿）** |
| 耗时 | 约 1.5 s |

实际输出结尾：

```
----------------------------------------------------------------------
Ran 156 tests in 1.532s

OK

===== 汇总 =====
用例数: 156  失败: 0  错误: 0  跳过: 0
```

> **本版更新（111 → 156 用例，v0.7 新功能覆盖 + QA-13/14 修复复核）**
> - 新增 **45 条**用例（7 个测试类）：`LaunchSpecTests`（11）、`DailyPlanTests`（6）、`DailyPreconditionTests`（6）、`DailyStateMachineTests`（8）、`DailyQueueTests`（5）、`DailyLogConfigTests`（4）、`DailyQuotingTests`（5）。
> - QA-13/14 已修复并验证：`extra_args` 只保留 str 并 strip；ok-ww `-t`、MAA `--config`、MXU `--instance` 等参数统一经 `_build_command` 构建——ShellExecuteW 参数串正确加引号/转义，Popen argv 列表保留原始 token。
> - 原有 111 条（v0.4~v0.6 契约）全部继续通过；`tools/test_launch_spec.py`、`tools/test_daily.py` 复核均 rc=0 / FAILURES: none。
> - 全部使用 mock/临时目录：**不启动 GUI、不启动脚本/游戏、不弹 UAC、不发送真实热键**。

## 一、测试范围与覆盖矩阵

| 测试类 | 用例数 | 覆盖点 | 结果 |
| --- | --- | --- | --- |
| `VersionTests` / `PathHelperTests` / `CleanProcsTests` / `ProcNameTests` | 3 / 5 / 5 / 1 | 版本比较、`_portable`/`_absolute`、进程名清洗 | 14 通过 |
| `ConfigStateTests` | 13 | 配置往返/BOM/损坏 JSON/Clash、config v4、detect 往返、v3→v4 game_procs 迁移 | 13 通过 |
| `FindAppExeTests` / `PickBestExeTests` / `ReadVersionTests` / `ProcessTests` | 4 / 3 / 8 / 3 | 路径扫描、版本读取、进程快照 | 18 通过 |
| `RenderSmokeTests` / `ImportSmokeTests` | 8 / 2 | 界面渲染尺寸、`import gamehub.ui`（含 daily 导入链） | 10 通过 |
| `GameCandidatesTests` | 8 | v0.5 游戏启动程序自动检测 | 8 通过 |
| `DetectRuleCleanTests` / `DetectorInterfaceRulesTests` / `BuiltinRuleTableTests` | 7 / 6 / 2 | v0.6 检测规则 schema、interface.json 提取、内置规则表 | 15 通过 |
| `WindowMatchTests` / `ProcMatchTests` / `GameRulesSourceTests` | 8 / 3 / 7 | 窗口/进程匹配、规则优先级与字段往返 | 18 通过 |
| `DetectGameStateTests` / `DetectorSnapshotSmokeTests` | 11 / 4 | v0.6 检测状态机分支、真实快照契约 | 15 通过 |
| **`LaunchSpecTests`**（v0.7 新增） | 11 | 见 2.1 | 11 通过 |
| **`DailyPlanTests`**（新增） | 6 | 见 2.2 | 6 通过 |
| **`DailyPreconditionTests`**（新增） | 6 | 见 2.3 | 6 通过 |
| **`DailyStateMachineTests`**（新增） | 8 | 见 2.4 | 8 通过 |
| **`DailyQueueTests`**（新增） | 5 | 见 2.5 | 5 通过 |
| **`DailyLogConfigTests`**（新增） | 4 | 见 2.6 | 4 通过 |
| **`DailyQuotingTests`**（新增，QA-14） | 5 | 见 2.7 | 5 通过 |
| **合计** | **156** | | **156 通过 / 0 跳过** |

## 二、v0.7 新功能覆盖说明

### 2.1 启动规格（`LaunchSpecTests`，11 条）
- `build_okww_launch` 从 ok-ww 安装布局推导规格：`type=python`、`exe=<...>\python\pythonw.exe`、`script=<...>\working\main.py`、`cwd=working`、`launcher_exe=ok-ww.exe`、`fallback=launcher`、进程名 `["pythonw.exe","python.exe"]`、进程目录仅 bundled python 目录；
- 环境变量：`LAUNCH_ENV_SET` 注入、`clear_env` 含 `PYTHONHOME/PYTHONPATH/PYAPPIFY_PID`、`app.json` 的 `current_version/current_profile` 写入 `PYAPPIFY_APP_VERSION/PROFILE`、`PYAPPIFY_APP_JSON_PATH`/`PYAPPIFY_EXECUTABLE`；
- `_launch_env`：清理父进程 Python 污染变量（`PYTHONHOME/PYTHONPATH/PYAPPIFY_PID`）、`PATH` 替换为 PyAppify 包装器默认 PATH、保留无关环境变量；
- `launch_app`：正式脚本存在时命令为 `[pythonw.exe, main.py, *args]`、`cwd=working`、注入清理后的 env，返回 `(True,"","script")`；
- 回退：`working/main.py` 缺失时回退启动器 `ok-ww.exe`（`mode=launcher`），回退也失败返回回退错误；`fallback=none` 时不回退；普通 exe（MAA 等）仍走 `launch_exe`（`mode=exe`）；
- 进程判定：按 exe **完整路径**判断正式脚本是否运行——只认 ok-ww pythonw 目录内的进程，用户其它 python、`ok-ww.exe` 启动器均不算；路径读不到时不判定运行（避免误判）；`launch_updater` 仍走启动器；
- 持久化：启动规格写入 config v4（路径写成相对 root 的便携格式），重载还原 exe/script/cwd；旧 v3 配置没有 `launch` 字段时内置鸣潮自动补齐；`_clean_launch` 非法/缺字段处理、`refresh_launch_spec` 重推导。

### 2.2 一键清日常 dry-run 命令拼装（`DailyPlanTests`，6 条）
- **鸣潮 ok-ww**：`"<working>\main.py" -t DailyTask -e`（任务名可配、`.rstrip().endswith("-e")`、可追加 extra_args），`cwd=working`，默认超时 90 分钟；
- **明日方舟 MAA**：`--skip-startup-auto-run` + 可选 `--config "<配置名>"` + extra_args；从 `gui.new.json` 解析 `LinkStart` 热键（`Alt, Control, Shift + L`）与已勾选任务队列；
- **异环 MaaNTE / 终末地 MaaEnd**：`--autostart --instance "<实例名>" --quit-after-run`；实例名未配置时自动建议（MaaNTE→「挂机任务」、MaaEnd→「全套日常」优先），可被设置覆盖；
- dry-run 四款计划顺序 = `DEFAULT_DAILY_ORDER`，全程不启动进程（`launch_elevated` 被 mock 为抛错仍通过）；`describe_plan` 含命令/超时/错误标记；不支持的卡片明确报错；超时/extra_args 设置生效。

### 2.3 前置检查（`DailyPreconditionTests`，6 条）
- ok-ww：正式脚本/pythonw/main.py/working 缺失 → 明确错误；`DailyTask.json` 缺失仅警告（提示先在 ok-ww 配置每日任务）；脚本已在运行 → 错误；
- MAA：未读到 `LinkStart` 热键 → 错误（提示设置热键）；任务队列没有已勾选任务 → 错误；MAA 已在运行 → `attach` 模式（只发热键、不启动进程、notes 说明）；
- MXU：无实例配置 → 错误；实例名不存在 → 错误并列出可用实例；实例 0 个启用任务 → 错误；
- 异环：实例无 `LaunchGamePC` 前置且游戏未运行 → 错误；有前置任务则不再要求游戏运行；终末地无前置且游戏未运行 → 警告；
- 不支持一键清日常的卡片 → 明确错误。

### 2.4 单游戏状态机（`DailyStateMachineTests`，8 条）
- ok-ww：进程退出前出现成功标记 → `finished`（记录 PID/日志摘要）；无成功标记 → `failed`；超时 → `timeout` 且结束本次进程；用户停止 → `stopped` 且结束本次进程；
- MXU：进程退出 → `finished`（`--quit-after-run` 不区分成败，日志启发式备注）；超时 → `timeout` 并结束进程；
- MAA：热键发送成功 + `gui.log` 出现「任务已全部完成！」→ `finished`；出现「任务出错:」→ `failed`；已在运行 → attach 只发热键且不启动；热键发送失败 → `failed`（提示检查热键占用）；窗口未就绪 → `failed`；`close_after=True` 时成功完成后结束本次启动的 MAA（句柄 terminate/close，已有断言）；
- `run`：前置检查失败 → 直接 `failed` 且不启动；`dry_run=True` → `dry-run/预演` 且不启动；状态中文标签齐全（idle/starting/running/finished/failed/timeout/stopped/skipped/dry-run）。

### 2.5 顺序队列（`DailyQueueTests`，5 条）
- 按 `order` 串行执行，结果顺序与快照一致；未启用项记录 `skipped` 且不执行；单项 `failed` 不中断后续（继续执行）；请求停止后第一项标记 `stopped`、剩余项全部 `stopped`、队列终态 `stopped`；`dry_run=True` 传递给每个单项执行。

### 2.6 日志与配置（`DailyLogConfigTests`，4 条）
- `LogWatcher`：初始不重复读历史、增量读取、tail 保留历史、文件截断/轮转后重新读取、空路径安全；
- `_clean_daily` 内置默认值（wuwa `task=DailyTask`/90min；maa 120min；maaend 150min；自定义卡片默认禁用；`close_after` 各游戏默认）、`timeout_min` 上下限（600/1）、`extra_args` 字符串 → 参数列表；
- `_clean_daily_order`：过滤未知 key、去重、补齐缺失、空值回退默认顺序；
- config v4 往返：`daily` 字段与 `daily_order` 写入/读回一致；旧 v4 配置无 `daily` 字段时自动补内置默认；`load_state_full` 返回的 `meta.daily_order` 覆盖内置 key。

### 2.7 命令参数引号处理（`DailyQuotingTests`，5 条，QA-14 修复验证）
- `_quote_arg`：无特殊字符原样输出；含空格/双引号/空串整体加引号；内部双引号 `\"` 转义；结尾反斜杠按 `2n` 转义（避免吞掉收尾引号）；`force=True` 强制加引号（脚本路径、`--config`/`--instance` 值）；
- `_build_command`：同时产出 `argv`（Popen 列表原始 token）、`params`（ShellExecuteW 参数字符串）、`command_text`（展示用）——两者一致；
- `_normalize_extra_arg` / `_extra_args`：去外层成对引号（兼容 UI 历史写入），空项丢弃；
- ok-ww：`task` 含空格/引号 → `params` 中为 `-t "Daily Task \"X\""`，`argv` 保留原始 token；
- MAA：`--config "My \"Daily\" Cfg"` + 含空格 extra_args 正确加引号，`argv` 原始 token 不受影响；
- MXU：`--instance "Full \"Daily\" Run"` + 含空格 extra_args 正确加引号；
- QA-13 一并验证：`_clean_daily` 的 `extra_args` 只保留 `str`、strip、丢弃 `None`/数字/空白/嵌套值，`'"--flag value"'`（字符串形式）解析为单个参数。

### 2.8 交叉验证与既有回归
- QA 独立运行 feature-dev 自测脚本（只读、mock，不启动脚本/游戏）：`python tools/test_launch_spec.py`、`python tools/test_daily.py` 均 **rc=0、FAILURES: none**（修复后复核）；
- v0.6 的 111 条用例（detector 规则/窗口/进程匹配、状态分支、config v4 迁移、渲染/导入/进程/版本等）全部继续通过，无回归。

## 三、缺陷清单与状态

| ID | 级别 | 状态 | 说明 |
| --- | --- | --- | --- |
| QA-01 / QA-02 | 低 | ✅ 已修复并持续通过 | `read_version` 缺失/非字符串版本回退 `fallback_version` |
| QA-03 | 中 | ✅ 已修复并持续通过 | `save_state` 返回 bool，写失败不再静默 |
| QA-04 | 低 | ✅ 已修复并持续通过 | `version_key` 忽略 `-rc`/`+build`，`is_newer` 零补齐 |
| QA-05 | 低 | ✅ 已修复并持续通过 | `_clean_procs` 跳过非 str 项 |
| QA-06 | 低/风险 | ⏳ 保留 | 目录扫描跳过 `data/resources/config/build/dist` 等名字（设计取舍）；建议 README FAQ 说明或后续拆分扫描表，不阻塞 v0.7 |
| QA-07 | 低 | ⏳ 保留 | 自定义卡片 exe 丢失后仍以相对路径加载、无 missing 提示；建议后续排期，不阻塞 v0.7 |
| QA-08 | 信息 | ℹ️ 保留（边界） | `_portable(path==root)` → `"."`，仅异常输入触发 |
| QA-09 | 低 | ✅ 已修复并持续通过 | `_clean_icon_path` 支持 `"path.exe",0` |
| QA-10 / QA-11 / QA-12 | 低 | ✅ 已修复并持续通过 | v4 迁移只纠正旧启动器误配、游戏名最长/精确反查、字符串进程名不再按空白拆分 |
| **QA-13** | 低/信息 | ✅ **已修复并验证**（task-21） | `extra_args` 只保留 str 并 strip，`None`/数字/空白/嵌套被丢弃；字符串形式按 `shlex(posix=True)` 解析。断言：`[None,3," --x ","",["nested"],"--y z"]` → `["--x","--y z"]`，`'"--flag value"'` → `["--flag value"]` |
| **QA-14** | 信息 | ✅ **已修复并验证**（task-21） | 新增 `_quote_arg`/`_build_command` 统一构建命令：ShellExecuteW 的 `params` 串对空格/引号/结尾反斜杠正确加引号与转义；Popen 的 `argv` 列表保留原始 token。ok-ww `-t`、MAA `--config`、MXU `--instance` 含空格/引号均正确（见 2.7） |

> 说明：本轮未发现新增阻塞性缺陷；QA-13/14 由 feature-dev 在 task-21 修复，QA 已补 5 条 `DailyQuotingTests` + 扩展 `extra_args` 断言验证，全部通过。

## 四、未覆盖点与测试限制

1. **真实 UAC 提权 / 热键 / 进程句柄 / 日志端到端（需 Lead 受控实测）**：本任务不启动脚本/游戏，`launch_elevated`（ShellExecuteEx runas）、`send_hotkey`（SendInput）、`ProcessHandle`（WaitForSingleObject/TerminateProcess）、真实日志端到端均由 mock/FakeHandle 替代。真实的一键清日常、UAC 弹窗、MAA LinkStart 热键、含空格任务名的实际命令行解析、超时终止、停止后剩余队列、退出码等需要在受控环境实测。
2. **GUI（Lead 已在 task-17 验收）**：工具栏「一键清日常」、卡片「清日常」链接、队列对话框排序/设置/进度/免责声明、设置保存、错误提示文案。自动化不启动 GUI/mainloop，未覆盖。
3. **真实安装布局差异**：ok-ww 不同版本的 `data/apps/ok-ww` 结构、`app.json` 字段、MAA `gui.new.json`/旧 `gui.json` 的更多格式、MXU 不同版本的实例配置结构，仅用 fixtures 模拟。
4. **真实游戏/模拟器/云游戏状态**：v0.6 detector 契约已覆盖；真实运行态与 ADB（默认关闭）需人工/受控实测。
5. **长时运行**：跨天、长时间监控、日志轮转极端情况、进程异常退出码、并发点击/重复启动、系统休眠唤醒等未覆盖。
6. **联网函数 / 真实 PE 版本资源 / 权限受限目录**：沿用前版报告，未测。
7. **版本号**：`VERSION` 当前仍为 `0.6.0`，发布任务 bump 为 `0.7.0` 后建议再跑一次本套件（预期仍 156/156 全绿）。

## 五、结论与建议

- **v0.7.0 功能快照回归全绿：156/156 通过、0 失败/0 错误/0 跳过、exit 0（约 1.5 s）**；可重复执行、无副作用。
- v0.6 的 111 条用例无回归；新增 45 条覆盖「鸣潮启动规格」「一键清日常」的命令拼装、前置检查、状态机、队列、日志与配置持久化，以及 QA-13/14 的 extra_args 清洗与命令参数引号处理。
- QA-13/14 修复均已用断言验证（见 2.6/2.7）；未发现阻塞性缺陷，可进入发布流程。
- 发布前建议：① Lead 完成真实一键清日常/UAC/热键/队列的受控实测与 GUI 复核（task-17 已完成 UI 验收）；② release 任务 bump `VERSION=0.7.0` 后重跑本套件（预期 156/156）；③ CI 增加 Windows runner 执行 `python tools/regression_test.py`（无需网络）。

## 附录：证据与约束遵守

- QA 只修改 `tools/regression_test.py`、`docs/qa-report.md`；未修改 `gamehub/`、`README.md`、`CHANGELOG.md` 等；未 commit / push。
- 未启动 GUI、未启动任何脚本/游戏、未发送真实热键、未重启 Hub；清日常/启动相关用例全部 mock `launch_elevated`/`send_hotkey`/`Popen`/`launch_exe` 或使用 FakeHandle + 假时钟。
- 配置类用例全部使用临时目录 + `mock.patch` 隔离；真实 `config.json` mtime `16:02:50`（Lead GUI 验证写入 v4），QA 运行前后未变化。
- 测试不联网；真实窗口快照仅 v0.6 smoke 用例使用（只读契约）。
- 交叉验证：`tools/test_launch_spec.py`、`tools/test_daily.py` 在修复后复核均 rc=0 / FAILURES: none。
