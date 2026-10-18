# All-My-Maa 回归测试报告（v0.10.0 最终版）

| 项目 | 内容 |
| --- | --- |
| 仓库 | `D:\All MAA\GameHub`（GitHub: https://github.com/Diaohesi/All-My-Maa ） |
| 被测版本 | **All-My-Maa v0.10.0**（功能快照：v0.9.1 + 异环 HTGame 启动 + 游戏启动策略重构 + UI 圆润淡紫/渐变/自定义标题栏/字体大小 + 自动更新；`gamehub.__init__.VERSION` 当前仍为 `0.9.1`，按发布流程由 release 任务 bump 为 `0.10.0`） |
| 代码基线 | `0468d90`（docs: refresh All-My-Maa v0.9.1 icon screenshots） |
| 工作区增量 | `gamehub/store.py` **+646 / -6**（`resolve_game_exe`/HTGame 优先/迁移、`build_game_launch` 四款策略、`wait_game_launched`/`launch_game_with_wait`、`FONT_SCALES`/`auto_download_update`/`NEW_DEFAULT_ACCENT`）、`gamehub/ui.py` **+1141 / -137**（自定义标题栏/字体缩放/圆角渐变令牌应用/淡紫默认/自动更新资产选择与 updater 脚本）、`gamehub/theme.py` **+21 / -7**（v0.10 圆角/间距/标题栏/渐变/淡紫预设）、`tools/test_ui_state.py` +93；新增 `tools/test_game_exe.py`、`tools/test_game_launch.py`、`docs/game-launch-research.md`；`assets/hub.ico`/`hub.png` 换新；文档由文档任务更新 |
| 测试脚本 | `tools/regression_test.py`（标准库 `unittest`，v0.10 最终版 **222 用例 / 44 个测试类**） |
| 执行命令 | `python tools/regression_test.py`（任意 CWD 可运行；`-v` 详细输出） |
| 执行时间 | 2026-10-18（最终快照：`gamehub/store.py` mtime 18:00:19，`gamehub/ui.py` mtime 18:00:09，`gamehub/theme.py` mtime 17:45:20） |
| 运行环境 | Windows 10/11 · Python 3.13.7 · Pillow 12.2.0 · 字体 msyh.ttc/msyhbd.ttc 存在 |
| 结果 | **222 个用例：222 通过 / 0 失败 / 0 错误 / 0 跳过；退出码 0（全绿）** |
| 耗时 | 约 1.9–2.0 s |

实际输出结尾：

```
----------------------------------------------------------------------
Ran 222 tests in 1.944s

OK

===== 汇总 =====
用例数: 222  失败: 0  错误: 0  跳过: 0
```

> **本版更新（198 → 222 用例，v0.10 异环/启动策略/标题栏/自动更新覆盖）**
> - 新增 **24 条**用例（6 个测试类）：`V010GameExeTests`（5）、`V010GameLaunchTests`（6）、`V010WaitLaunchTests`（4）、`V010SettingsThemeTests`（5）、`V010SettingsRoundTripTests`（1）、`V010AutoUpdateTests`（3）。
> - 覆盖：`resolve_game_exe` HTGame 优先/glob/迁移、`build_game_launch` 四款启动策略（wuwa 直启/nte HTGame/maaend 启动器/MAA PC 与模拟器）、等待器成功/超时/提前退出与回退、font_scale/淡紫默认/圆角渐变/自定义标题栏纯逻辑、自动更新资产选择/updater 脚本引号/门控。
> - 原有 198 条（v0.4~v0.9.1 契约）全部继续通过；`tools/test_ui_state.py`、`tools/test_game_exe.py`、`tools/test_game_launch.py`、`test_daily.py`、`test_launch_spec.py` 交叉复核均 rc=0 / FAILURES: none；`test_detect_game.py` rc=0。
> - 全部使用 mock/临时目录/假时钟：**不启动 GUI、不启动游戏、不联网、不实际下载/替换 exe**。

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
| `DailyPlanTests` / `DailyPreconditionTests` | 6 / 6 | 四款 dry-run 命令、前置检查 | 12 通过 |
| `DailyStateMachineTests` / `DailyQueueTests` / `DailyLogConfigTests` / `DailyQuotingTests` | 8 / 5 / 4 / 5 | 状态机、队列、日志/配置、命令引号 | 22 通过 |
| `SettingsTests` / `SettingsConfigTests` | 4 / 3 | settings 清洗/持久化/默认超时 | 7 通过 |
| `DailySelectionTests` / `DailyManagerTests` | 3 / 7 | 勾选过滤/顺序、每游戏独立状态 | 10 通过 |
| `UiPureLogicTests` / `ClashResolutionTests` | 3 / 3 | 刷新间隔/CHANGELOG、clash 路径（QA-15） | 6 通过 |
| `V09ThemeTests` / `SoftwareUpdateTests` | 4 / 5 | v0.9 设计令牌、软件更新纯逻辑 | 9 通过 |
| `SmallToolsTests` / `ChangelogFormatTests` | 4 / 3 | 小工具路径、更新日志纯文本 | 7 通过 |
| `V091IconTests` | 3 | v0.9.1 图标资产/映射/回退 | 3 通过 |
| **`V010GameExeTests`**（v0.10 新增） | 5 | 见 2.1 | 5 通过 |
| **`V010GameLaunchTests`**（新增） | 6 | 见 2.2 | 6 通过 |
| **`V010WaitLaunchTests`**（新增） | 4 | 见 2.3 | 4 通过 |
| **`V010SettingsThemeTests`**（新增） | 5 | 见 2.4 | 5 通过 |
| **`V010SettingsRoundTripTests`**（新增） | 1 | 见 2.5 | 1 通过 |
| **`V010AutoUpdateTests`**（新增） | 3 | 见 2.6 | 3 通过 |
| **合计** | **222** | | **222 通过 / 0 跳过** |

## 二、v0.10 新功能覆盖说明

### 2.1 异环游戏本体解析（`V010GameExeTests` 5）
- `resolve_game_exe`：异环卡片优先解析 `HTGame.exe`——已指向 HTGame 直接返回；从 `game_exe` 安装根/脚本目录按已知相对路径查找；再做 ≤4 层、限时 glob；找到后写回 `game_exe` 且 `game_procs=["HTGAME.EXE"]`；找不到保留原值，不误改；非异环游戏原样返回。
- `GAME_EXE_HINTS["nte"][0] == "htgame.exe"`；`_score_exe_path` 中 HTGame 分数高于 NTELauncher；`find_game_candidates` 在标准布局下候选首位为 HTGame（v0.10 特殊优先规则）。
- `load_state_full` 加载迁移：配置里异环指向 `NTELauncher.exe` 且能找到 HTGame 时自动纠正并保存到 config；找不到时保留启动器，不改写。
- 交叉：`tools/test_game_exe.py` rc=0 / FAILURES: none。

### 2.2 四款游戏启动策略（`V010GameLaunchTests` 6）
- **鸣潮**：`strategy=exe`，直启 `Wuthering Waves Game\Wuthering Waves.exe`，args `["-krqlv=hd"]`、cwd=游戏目录、不提权；wait 120s，窗口 `^UnrealWindow$` / 进程 `Client-Win64-Shipping.exe`；fallback 先启动器（提示点击开始游戏）；ok-ww `devices.json` 的 `pc_full_path` 也可发现。
- **异环**：优先 `HTGame.exe`，args `[]`，wait 180s（`UnrealWindow` / `HTGame.exe`），fallback 启动器。
- **终末地**：默认走启动器（Launcher.exe），cwd=安装根，wait 180s（`UnityWndClass` / `Endfield.exe`），fallback 直启 Endfield（附白屏提示）。
- **明日方舟**：读 `gui.new.json` 分支——PC 客户端（`PcClientPath`/`PcClientWaitSeconds` → `maa_pc`，wait 标题「明日方舟」、超时 90s）；模拟器（`EmulatorPath`/`AdbPath`/`AdbSerial` → `maa_adb`，adb path/serial/默认包名 `com.hypergryph.arknights`、超时 45s）。
- **缺失兜底**：找不到 exe 时 wuwa/nte/maaend fallback 为 `user_pick`；自定义游戏保持现有 `game_exe` 直接启动。
- 交叉：`tools/test_game_launch.py` rc=0 / FAILURES: none。

### 2.3 等待/启动回退（`V010WaitLaunchTests` 4）
- `wait_game_launched`：状态立即满足 → 成功且不 sleep；超时按 `timeout_s` 返回「等待游戏窗口超时」；启动进程提前退出（`process.poll()` 非 None）→ 「启动进程提前退出」。
- `launch_game_with_wait`（spawn mock）：成功返回 ok + pid，spawn 参数为 spec 的 exe/args/cwd；超时后自动 spawn fallback 启动器并返回 fallback hint；spawn 本身失败直接返回失败原因，不进入等待。

### 2.4 字体缩放 / 淡紫默认 / 圆角渐变 / 标题栏（`V010SettingsThemeTests` 5）
- `font_scale`：`FONT_SCALES=(0.9,1.0,1.12,1.25)`，默认 1.0；合法值保留，非法（2.0/0.8/字符串/True）回退 1.0；`ui.window_scale_value` 同一映射，非法回退默认（可自定义 default）。
- `ui._scaled_font`：按全局 `_FONT_SCALE` 缩放像素字号（1.0: -11→-11；1.12: -11→-12、10→-11；1.25: -11→-14），非法 size 回退 11。
- 淡紫默认：`store.NEW_DEFAULT_ACCENT="#b98bff"`、`theme.UI_ACCENT="#b98bff"`、`ACCENT_PRESETS[0]==("淡紫","#b98bff")` 且紫系预设 ≥3（旧 `DEFAULT_SETTINGS.accent` 保留 `#4fc3ff` 供旧测试/渲染兼容，UI 在无显式 accent 时使用新默认）。
- 新令牌：`RADIUS_PANEL=16`/`RADIUS_BUTTON=13`/`RADIUS_INPUT=10`、`SPACE_UI_*` 10/14/18/22/26、`TITLEBAR_H=44`、渐变令牌合法且与底色不同。
- 自定义标题栏纯逻辑：`titlebar_buttons(False/True)`（最大化/还原字符 `□`/`❐`、最小化 `—`、关闭 `✕`、maximized 标记）；关闭行为映射 `close_action` 清洗（minimize/exit/非法→exit）；最小窗口 1000×640。
- `auto_download_update`：默认 False；仅接受真 bool（字符串/数字忽略）。

### 2.5 settings 新增字段往返（`V010SettingsRoundTripTests` 1）
- `font_scale=1.12`、`auto_download_update=True`、`accent=#b98bff` 写入 config v4 settings 并原样读回；旧配置无新增字段时回退默认（font_scale 1.0、auto False）。

### 2.6 自动更新纯逻辑（`V010AutoUpdateTests` 3）
- `select_update_asset`：优先 exe（`GameHub`/`AllMyMaa` 名称优先），其次 zip（品牌名优先）；坏项/无资产/非 dict → None；size 字符串转 int。
- `build_updater_script`：生成 `Wait-Process -Id <pid> -Timeout 60` → 备份 `.bak` → 覆盖 `.new` → `Move-Item` → `Start-Process` 的 PowerShell 脚本；路径含空格/单引号时用单引号包裹并把 `'` 写成 `''`；非法 pid → 0；CRLF 行尾。
- 门控：`can_auto_update(frozen, writable)`、`should_source_update(is_git, clean)` 组合；`update_available(current, latest)` 版本门（v 前缀/相同/更低均正确）。

### 2.7 交叉验证与既有回归
- QA 独立运行：`tools/test_ui_state.py`、`tools/test_game_exe.py`、`tools/test_game_launch.py`、`tools/test_daily.py`、`tools/test_launch_spec.py` 均 **rc=0 / FAILURES: none**；`tools/test_detect_game.py` **rc=0**（只读检测，本机运行游戏: 无）。
- 原有 198 条（v0.4~v0.9.1 契约）全部继续通过，无回归。
- 稳定性：本套件连续运行 2 次均 222/222 通过。

## 三、缺陷清单与状态

### 3.1 已修复项（持续回归通过）
QA-01/02（read_version 回退）、QA-03（save_state 返回 bool）、QA-04（版本比较）、QA-05（非 str 进程名）、QA-09（DisplayIcon 引号+索引）、QA-10（v4 迁移不覆盖用户进程名）、QA-11（游戏名最长/精确反查）、QA-12（字符串进程名不按空白拆分）、QA-13（extra_args 只保留 str 并 strip）、QA-14（命令参数统一引号处理）、QA-15（clash 便携相对路径还原）——全部保持通过。

### 3.2 保留项（低风险/设计边界，不阻塞 v0.10）
- QA-06：目录扫描跳过 `data/resources/config/build/dist` 等名字（设计取舍，建议 README FAQ 说明）。
- QA-07：自定义卡片 exe 丢失后仍以相对路径加载、无 missing 提示（建议后续排期）。
- QA-08：`_portable(path==root)` → `"."`（仅异常输入触发）。

> 本轮未发现新增阻塞性缺陷；v0.10 启动策略/等待/标题栏/字体/自动更新纯逻辑断言全部通过。

## 四、未覆盖点与测试限制

1. **真实游戏启动与等待（需 Lead 人工/受控实测）**：真实启动鸣潮/异环/终末地/明日方舟（PC/模拟器）并等待游戏窗口；HTGame 实际登录/加载耗时、MAA 模拟器 + ADB 启动、启动器回退提示的真实交互。自动化全部 mock/构造临时目录。
2. **真实自定义标题栏**：拖拽移动、双击最大化/还原、最小化/关闭按钮、任务栏行为、无边框窗口缩放/DPI；纯逻辑只覆盖按钮字符与状态。
3. **真实自动更新**：GitHub API 真实下载、`frozen` exe 自替换（UAC/文件占用/回滚）、源码模式 `git pull` 更新、更新包选择与下载进度、失败提示；自动化只测纯逻辑与脚本生成，未联网/未实际替换。
4. **真实字体缩放视觉**：0.9/1.0/1.12/1.25 四档在真实窗口的布局/圆角/渐变/淡紫主题观感（Lead 已做视觉验收）。
5. **打包版路径**：PyInstaller `_MEIPASS` 下 assets/图标、CHANGELOG/LICENSE、自动更新目标 exe 路径未在打包产物上验证。
6. **真实清日常/UAC/热键/日志端到端**：沿用 v0.7/v0.8 的 mock 覆盖，需 Lead 受控实测。
7. **长时/并发**：跨天运行、并发点击、系统休眠唤醒等未覆盖。
8. **版本号**：`VERSION` 当前仍为 `0.9.1`，发布任务 bump 为 `0.10.0` 后建议再跑一次本套件（预期仍 222/222 全绿）。

## 五、结论与建议

- **v0.10.0 功能快照回归全绿：222/222 通过、0 失败/0 错误/0 跳过、exit 0（约 1.9–2.0 s）**；可重复执行、无副作用。
- 原有 198 条无回归；新增 24 条覆盖异环 HTGame 解析/迁移、四款游戏启动策略、等待/回退、font_scale/淡紫/圆角渐变/标题栏、settings 新字段、自动更新纯逻辑。
- 未发现新增阻塞性缺陷；QA-15 保持修复；QA-06/07/08 仍为低风险/设计边界。
- 发布前建议：① Lead 完成真实游戏启动/等待、标题栏拖拽/最大化、自动更新下载替换的人工验证；② release 任务 bump `VERSION=0.10.0` 后重跑本套件（预期 222/222）；③ CI 增加 Windows runner 执行 `python tools/regression_test.py`（无需网络）。

## 附录：证据与约束遵守

- QA 只修改 `tools/regression_test.py`、`docs/qa-report.md`；未修改 `gamehub/`、`assets/`、`README.md`、`CHANGELOG.md` 等；未 commit / push。
- 未启动 GUI、未启动任何游戏/脚本、未联网、未实际下载或替换 exe；启动/等待/更新相关用例全部 mock（spawn/Popen/纯函数/临时目录）。
- 配置类用例全部使用临时目录 + `mock.patch` 隔离；真实 `config.json` mtime `17:58:18`（Lead GUI 验证写入 v4），QA 运行前后未变化。
- 交叉验证：`tools/test_ui_state.py`、`tools/test_game_exe.py`、`tools/test_game_launch.py`、`tools/test_daily.py`、`tools/test_launch_spec.py` 均 rc=0 / FAILURES: none；`tools/test_detect_game.py` rc=0。
- 稳定性：本套件连续运行 2 次均 222/222 通过。
