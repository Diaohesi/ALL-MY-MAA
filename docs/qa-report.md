# AllMyMaa 回归测试报告（v0.8.0 最终版）

| 项目 | 内容 |
| --- | --- |
| 仓库 | `D:\All MAA\GameHub`（GitHub: https://github.com/Diaohesi/AllMyMaa ） |
| 被测版本 | GameHub Lite / **AllMyMaa v0.8.0**（功能快照：v0.7.0 + 新 UI 三页 + AllMyMaa 品牌 + 设置页 + 清日常勾选/独立状态 + QA-15 修复；`gamehub.__init__.VERSION` 当前仍为 `0.7.0`，按发布流程由 release 任务 bump 为 `0.8.0`） |
| 代码基线 | `3a805e5`（docs: rebrand to AllMyMaa） |
| 工作区增量 | `gamehub/ui.py` **+1509 / -1196**（2363 行：三页导航/AllMyMaa 品牌/设置页/清日常勾选与独立状态展示）、`gamehub/daily.py` **+312**（1630 行：`DailyManager`/`ordered_daily_keys`/`enabled_daily_keys`/独立状态）、`gamehub/store.py` **+94 / -8**（`settings` 清洗/持久化、`daily_default_timeout`、`daily_explicit`、QA-15 clash 路径还原）、`gamehub/theme.py` +4；新增 `tools/test_ui_state.py`（260 行） |
| 测试脚本 | `tools/regression_test.py`（标准库 `unittest`，v0.8 最终版 **179 用例 / 33 个测试类**） |
| 执行命令 | `python tools/regression_test.py`（任意 CWD 可运行；`-v` 详细输出） |
| 执行时间 | 2026-10-18（最终快照：`gamehub/store.py` mtime 16:40:23，`gamehub/daily.py` mtime 16:33:56，`gamehub/ui.py` mtime 16:33:10） |
| 运行环境 | Windows 10/11 · Python 3.13.7 · Pillow 12.2.0 · 字体 msyh.ttc/msyhbd.ttc 存在 |
| 结果 | **179 个用例：179 通过 / 0 失败 / 0 错误 / 0 跳过；退出码 0（全绿）** |
| 耗时 | 约 1.4–1.6 s |

实际输出结尾：

```
----------------------------------------------------------------------
Ran 179 tests in 1.448s

OK

===== 汇总 =====
用例数: 179  失败: 0  错误: 0  跳过: 0
```

> **本版更新（156 → 179 用例，v0.8 设置/勾选/独立状态 + QA-15 修复复核）**
> - 新增 **23 条**用例（6 个测试类）：`SettingsTests`（4）、`SettingsConfigTests`（3）、`DailySelectionTests`（3）、`DailyManagerTests`（7）、`UiPureLogicTests`（3）、`ClashResolutionTests`（3）。
> - QA-15 已修复并验证：`load_state_full` 对顶层 `clash` 与 `settings.clash_exe` 均按 `root` 还原绝对路径，优先级 **顶层 > settings > 自动查找**；保存仍写便携相对路径。
> - 原有 156 条（v0.4~v0.7 契约）全部继续通过；`tools/test_ui_state.py`、`tools/test_daily.py`、`tools/test_launch_spec.py` 交叉复核均 rc=0 / FAILURES: none。
> - 全部使用 mock/临时目录/假时钟：**不启动 GUI、不启动脚本/游戏、不弹 UAC、不发送真实热键**。

## 一、测试范围与覆盖矩阵

| 测试类 | 用例数 | 覆盖点 | 结果 |
| --- | --- | --- | --- |
| `VersionTests` / `PathHelperTests` / `CleanProcsTests` / `ProcNameTests` | 3 / 5 / 5 / 1 | 版本比较、路径转换、进程名清洗 | 14 通过 |
| `ConfigStateTests` | 13 | 配置往返/BOM/损坏 JSON/Clash、config v4、detect 往返、v3→v4 game_procs 迁移 | 13 通过 |
| `FindAppExeTests` / `PickBestExeTests` / `ReadVersionTests` / `ProcessTests` | 4 / 3 / 8 / 3 | 路径扫描、版本读取、进程快照 | 18 通过 |
| `RenderSmokeTests` / `ImportSmokeTests` | 8 / 2 | 界面渲染尺寸、`import gamehub.ui`（含 settings/daily 导入链） | 10 通过 |
| `GameCandidatesTests` | 8 | v0.5 游戏启动程序自动检测 | 8 通过 |
| `DetectRuleCleanTests` / `DetectorInterfaceRulesTests` / `BuiltinRuleTableTests` | 7 / 6 / 2 | v0.6 检测规则 schema、interface.json 提取、内置规则表 | 15 通过 |
| `WindowMatchTests` / `ProcMatchTests` / `GameRulesSourceTests` | 8 / 3 / 7 | 窗口/进程匹配、规则优先级与字段往返 | 18 通过 |
| `DetectGameStateTests` / `DetectorSnapshotSmokeTests` | 11 / 4 | v0.6 检测状态机分支、真实快照契约 | 15 通过 |
| `LaunchSpecTests` | 11 | v0.7 鸣潮启动规格/回退/路径判定/持久化 | 11 通过 |
| `DailyPlanTests` / `DailyPreconditionTests` | 6 / 6 | 四款 dry-run 命令、前置检查 | 12 通过 |
| `DailyStateMachineTests` / `DailyQueueTests` / `DailyLogConfigTests` / `DailyQuotingTests` | 8 / 5 / 4 / 5 | 状态机、旧队列、日志/配置、命令引号（QA-13/14） | 22 通过 |
| **`SettingsTests`**（v0.8 新增） | 4 | 见 2.1 | 4 通过 |
| **`SettingsConfigTests`**（新增） | 3 | 见 2.1 | 3 通过 |
| **`DailySelectionTests`**（新增） | 3 | 见 2.2 | 3 通过 |
| **`DailyManagerTests`**（新增） | 7 | 见 2.3 | 7 通过 |
| **`UiPureLogicTests`**（新增） | 3 | 见 2.4 | 3 通过 |
| **`ClashResolutionTests`**（新增，QA-15） | 3 | 见 2.5 | 3 通过 |
| **合计** | **179** | | **179 通过 / 0 跳过** |

## 二、v0.8 新功能覆盖说明

### 2.1 设置（`SettingsTests` 4 + `SettingsConfigTests` 3）
- `store._clean_settings`：缺省值（accent `#4fc3ff`、refresh 1.5、close_action `exit`、daily_default_timeout 120、`check_update_on_start=True`、`adb_enabled=False`、`daily_show_preview=True`、`daily_close_after=True`）；非 dict 输入回退默认。
- accent 校验：仅接受 `#RRGGBB` 十六进制，去空白并小写归一（`#B98BFF` → `#b98bff`），`red`/`#12345`/`#GGGGGG`/空值/非字符串一律回退默认。
- `refresh_interval` 仅接受 1.0 / 1.5 / 2.0（含 `2.0` 浮点），其它值（7、`"1.5"`、`True`）回退 1.5；`ui._refresh_delay_ms` 映射 1000/1500/2000，非法回退 1500。
- `close_action` 仅接受 `exit`/`minimize`（大小写归一小写），非法值回退 `exit`；`daily_default_timeout` 限 1~600，负数/0.5 → 1、9999 → 600、字符串 → 120。
- 布尔字段只接受真 bool（字符串 `"false"` 不生效）；clash_exe 字符串 strip。
- 持久化往返：`save_state(..., settings=...)` 写入 config v4 `settings` 字段，`load_state_full` 的 `meta.settings` 还原 accent/refresh/close_action/daily_default_timeout/布尔项；`settings.clash_exe` 按 root 写成便携相对路径，读取时还原为绝对路径（见 2.5）。
- 旧配置无 `settings` → 自动补默认；`daily_default_timeout` 只作用于**用户写过 daily 但没有写 `timeout_min`** 的卡片（内置卡片完全没写 daily 时保持各游戏内置默认 120/90/150），并正确设置 `daily_explicit` 标记。

### 2.2 清日常勾选与顺序（`DailySelectionTests` 3）
- `daily.ordered_daily_keys`：按 `daily_order` 过滤不存在的 key、去重，未列出的已存在卡片按 apps 顺序补在末尾（含自定义卡片）；`order=None` 时用默认顺序。
- `daily.enabled_daily_keys`：只返回 `daily.enabled=True` 的卡片且保持 `daily_order` 顺序；未写 daily 的内置卡片默认勾选；自定义卡片缺省默认禁用。
- 勾选状态切换后选择结果实时变化（`enabled` False 被过滤，恢复 True 重新纳入）。

### 2.3 每游戏独立状态（`DailyManagerTests` 7）
- 初始状态：所有卡片 `idle/空闲`，`busy=False`、`active=None`、队列 `idle`；`reset()` 可清空历史状态。
- `start_single(key)`：启动后仅该 key 进入 `starting/running`，**其它卡片保持自己的 idle 状态**（不会全部显示运行中）；运行中再次 `start_single` 被拒并给出「进行中」原因；`busy_reason` 正确提示；非当前项 `stop_single` 返回 False。
- `stop_single(key)`：把 `stop_event` 传递到 runner 并最终变为 `stopped`；空闲时 `stop_single`/`stop_all` 返回 False。
- `start_queue(keys)`：当前项 `running`，**非当前项及其它未参与卡片保持 idle**；队列完成后各项记录自己的 `finished` 与结果顺序；队列运行中 `start_single`/再次 `start_queue` 被拒。
- 队列停止：第一项停止后，剩余未执行项全部标记 `stopped`，队列终态 `stopped`；执行顺序与 `keys` 一致。
- 勾选过滤：用 `enabled_daily_keys` 作为队列输入后只执行勾选项（未勾选 nte 保持 idle）；无有效勾选/未知卡片时明确报错（"没有勾选任何游戏"/"卡片不存在"）。

### 2.4 UI 纯逻辑（`UiPureLogicTests` 3，无头可测部分）
- `ui._refresh_delay_ms`：1.0/1.5/2.0 → 1000/1500/2000，非法/缺失回退 1500。
- `ui._parse_changelog`：解析 `## vX.Y.Z (日期)` 分节、按版本号从新到旧排序、body/date 提取、非标题行忽略、空文本 → []。
- `ui._find_changelog`：源码运行时可定位仓库根目录 `CHANGELOG.md`。
- 页面切换/导航高亮、按钮状态映射等为 Tk 实例方法（需要 GUI），未在自动化中覆盖（见未覆盖点）。

### 2.5 clash 路径解析（`ClashResolutionTests` 3，QA-15 修复验证）
- 仅 `settings.clash_exe` 为**相对路径**且文件存在时：`load_state_full` 返回的运行期 clash 与 `meta.settings.clash_exe` 均还原为绝对路径；
- `settings.clash_exe` 为绝对路径时原样可用；
- 优先级：顶层 `clash` > `settings.clash_exe` > 自动探测；顶层绝对/相对路径都按 root 还原；顶层路径失效时回退 settings；
- 顶层与 settings 都无效时回退 `CLASH_CANDIDATES` 自动查找；settings 路径不存在时保留原值供 UI 显示（不报错）；
- 保存时仍写便携相对路径（`settings.clash_exe` + 顶层 `clash`），读取时统一还原。

### 2.6 交叉验证与既有回归
- QA 独立运行 feature-dev 自测：`python tools/test_ui_state.py`、`python tools/test_daily.py`、`python tools/test_launch_spec.py` 均 **rc=0 / FAILURES: none**。
- 原有 156 条（v0.4~v0.7 契约，含 detector/config v4/launch spec/一键清日常/命令引号）全部继续通过，无回归。

## 三、缺陷清单与状态

### 3.1 已修复项（持续回归通过）
QA-01/02（read_version 回退）、QA-03（save_state 返回 bool）、QA-04（版本比较）、QA-05（非 str 进程名）、QA-09（DisplayIcon 引号+索引）、QA-10（v4 迁移不覆盖用户进程名）、QA-11（游戏名最长/精确反查）、QA-12（字符串进程名不按空白拆分）、QA-13（extra_args 只保留 str 并 strip）、QA-14（命令参数统一引号处理）、**QA-15（clash 便携相对路径还原）**——全部保持通过。

### 3.2 v0.8 修复验证
| ID | 级别 | 状态 | 说明 |
| --- | --- | --- | --- |
| **QA-15** | 低 | ✅ **已修复并验证**（task-29） | `load_state_full` 现在对顶层 `clash` 与 `settings.clash_exe` 都用 `_absolute(value, root)` 还原；优先级顶层 > settings > 自动查找；`ClashResolutionTests` 3 条断言覆盖：settings 相对/绝对路径、顶层优先（绝对/相对）、顶层失效回退 settings、双失效回退自动探测、settings 缺失保留原值。修复前"仅 settings 相对路径 → 运行期 clash 为空"的问题不再出现 |

### 3.3 保留项（低风险/设计边界，不阻塞 v0.8）
- QA-06：目录扫描跳过 `data/resources/config/build/dist` 等名字（设计取舍，建议 README FAQ 说明）。
- QA-07：自定义卡片 exe 丢失后仍以相对路径加载、无 missing 提示（建议后续排期）。
- QA-08：`_portable(path==root)` → `"."`（仅异常输入触发）。

> 本轮未发现新增阻塞性缺陷。

## 四、未覆盖点与测试限制

1. **真实 GUI 交互（需 Lead 人工验证）**：三页导航/高亮切换、首页卡片、清日常页勾选与每行独立状态展示、设置页控件绑定与保存提示、队列对话框、滚动/缩放/DPI、AllMyMaa 品牌视觉。本任务不启动 GUI/mainloop，未覆盖。
2. **真实清日常/UAC/热键/日志端到端**：真实启动 ok-ww/MAA/MXU、UAC 弹窗、MAA LinkStart 热键、真实日志成功/失败标记、超时终止、停止后剩余队列等需 Lead 受控实测（自动化全部 mock/FakeHandle）。
3. **真实安装布局/环境差异**：ok-ww 不同版本目录、MAA gui.new/gui.json 旧格式、MXU 实例配置结构变化仅用 fixtures 模拟。
4. **真实游戏/模拟器/云游戏状态**：v0.6 detector 契约已覆盖；真实运行态与 ADB（默认关闭）需人工/受控实测。
5. **长时/并发**：跨天运行、长时间监控、日志轮转极端情况、并发点击/重复启动、系统休眠唤醒未覆盖。
6. **联网函数 / 真实 PE 版本资源 / 权限受限目录**：沿用前版报告，未测。
7. **版本号**：`VERSION` 当前仍为 `0.7.0`，发布任务 bump 为 `0.8.0` 后建议再跑一次本套件（预期仍 179/179 全绿）。

## 五、结论与建议

- **v0.8.0 功能快照回归全绿：179/179 通过、0 失败/0 错误/0 跳过、exit 0（约 1.4–1.6 s）**；可重复执行、无副作用。
- 原有 156 条无回归；新增 23 条覆盖 settings 清洗/持久化、清日常勾选与顺序、`DailyManager` 每游戏独立状态/单游戏/队列/停止、UI 纯逻辑、clash 路径解析。
- QA-15 已修复并经 `ClashResolutionTests` 验证；未发现新增阻塞性缺陷。
- 发布前建议：① Lead 完成 v0.8 三页 UI/设置/勾选/独立状态的人工验证与截图（真实 GUI）；② release 任务 bump `VERSION=0.8.0` 后重跑本套件（预期 179/179）；③ CI 增加 Windows runner 执行 `python tools/regression_test.py`（无需网络）。

## 附录：证据与约束遵守

- QA 只修改 `tools/regression_test.py`、`docs/qa-report.md`；未修改 `gamehub/`、`README.md`、`CHANGELOG.md` 等；未 commit / push。
- 未启动 GUI、未启动任何脚本/游戏、未发送真实热键、未重启 Hub；settings/清日常相关用例全部使用 `mock.patch` / 临时配置 / 假时钟 / 事件同步。
- 配置类用例全部使用临时目录 + `mock.patch` 隔离；真实 `config.json` mtime `16:16:21`（Lead GUI 验证写入 v4），QA 运行前后未变化。
- 交叉验证：`tools/test_ui_state.py`、`tools/test_daily.py`、`tools/test_launch_spec.py` 在 v0.8 代码上复核均 rc=0 / FAILURES: none。
- 稳定性：本套件连续运行 3 次均全绿（含多线程 `DailyManager` 用例）。
