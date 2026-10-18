# All-My-Maa 回归测试报告（v0.9.1 最终版）

| 项目 | 内容 |
| --- | --- |
| 仓库 | `D:\All MAA\GameHub`（GitHub: https://github.com/Diaohesi/All-My-Maa ） |
| 被测版本 | **All-My-Maa v0.9.1**（功能快照：v0.9.0 + LinYuxia 品牌图标与四页面图标接入；`gamehub.__init__.VERSION` 当前仍为 `0.9.0`，按发布流程由 release 任务 bump 为 `0.9.1`） |
| 代码基线 | `3e87153`（docs: refresh All-My-Maa v0.9.0 screenshots） |
| 工作区增量 | `gamehub/ui.py` **+147 / -28**（`BRAND_ICON_FILE`/`PAGE_ICON_FILES`/`ICON_SIZES`/`ICON_FALLBACKS`、`icon_asset_file`/`icon_path`/`resolve_icon_path`、窗口/侧边栏/导航/页面标题/关于图标接入）、`tools/test_ui_state.py` **+51**（v0.9.1 图标断言）；新增 5 个资源：`assets/LinYuxia.png`、`assets/page_home.png`、`page_daily.png`、`page_settings.png`、`page_about.png`（均 192×192 PNG） |
| 测试脚本 | `tools/regression_test.py`（标准库 `unittest`，v0.9.1 最终版 **198 用例 / 38 个测试类**） |
| 执行命令 | `python tools/regression_test.py`（任意 CWD 可运行；`-v` 详细输出） |
| 执行时间 | 2026-10-18（最终快照：`gamehub/ui.py` mtime 17:19:35，`tools/test_ui_state.py` mtime 17:19:56） |
| 运行环境 | Windows 10/11 · Python 3.13.7 · Pillow 12.2.0 · 字体 msyh.ttc/msyhbd.ttc 存在 |
| 结果 | **198 个用例：198 通过 / 0 失败 / 0 错误 / 0 跳过；退出码 0（全绿）** |
| 耗时 | 约 1.7 s |

实际输出结尾：

```
----------------------------------------------------------------------
Ran 198 tests in 1.731s

OK

===== 汇总 =====
用例数: 198  失败: 0  错误: 0  跳过: 0
```

> **本版更新（195 → 198 用例，v0.9.1 图标接入复核）**
> - 新增 **3 条**用例（`V091IconTests`）：5 个图标资源存在且 192×192 PNG；逻辑名→文件/绝对路径映射与尺寸令牌；缺失回退（brand→hub.png、about→LinYuxia→hub、页面图标无回退、空目录不崩溃）。
> - 原有 195 条（v0.4~v0.9 契约）全部继续通过；`tools/test_ui_state.py`（含新增图标断言）、`test_daily.py`、`test_launch_spec.py`、`test_detect_game.py` 交叉复核均 rc=0。
> - 只读取 assets 图片（Pillow 内存打开），**不启动 GUI、不联网、不打开目录、不启动脚本/游戏**。

## 一、测试范围与覆盖矩阵

| 测试类 | 用例数 | 覆盖点 | 结果 |
| --- | --- | --- | --- |
| `VersionTests` / `PathHelperTests` / `CleanProcsTests` / `ProcNameTests` | 3 / 5 / 5 / 1 | 版本比较、路径转换、进程名清洗 | 14 通过 |
| `ConfigStateTests` | 13 | 配置往返/BOM/损坏 JSON/Clash、config v4、detect 往返、v3→v4 迁移 | 13 通过 |
| `FindAppExeTests` / `PickBestExeTests` / `ReadVersionTests` / `ProcessTests` | 4 / 3 / 8 / 3 | 路径扫描、版本读取、进程快照 | 18 通过 |
| `RenderSmokeTests` / `ImportSmokeTests` | 8 / 2 | 旧 Pillow 渲染尺寸、`import gamehub.ui`（含图标模块导入链） | 10 通过 |
| `GameCandidatesTests` | 8 | v0.5 游戏启动程序自动检测 | 8 通过 |
| `DetectRuleCleanTests` / `DetectorInterfaceRulesTests` / `BuiltinRuleTableTests` | 7 / 6 / 2 | v0.6 检测规则 schema、interface.json、内置规则表 | 15 通过 |
| `WindowMatchTests` / `ProcMatchTests` / `GameRulesSourceTests` | 8 / 3 / 7 | 窗口/进程匹配、规则优先级与字段往返 | 18 通过 |
| `DetectGameStateTests` / `DetectorSnapshotSmokeTests` | 11 / 4 | v0.6 检测状态分支、真实快照契约 | 15 通过 |
| `LaunchSpecTests` | 11 | v0.7 鸣潮启动规格/回退/路径判定/持久化 | 11 通过 |
| `DailyPlanTests` / `DailyPreconditionTests` | 6 / 6 | 四款 dry-run 命令、前置检查 | 12 通过 |
| `DailyStateMachineTests` / `DailyQueueTests` / `DailyLogConfigTests` / `DailyQuotingTests` | 8 / 5 / 4 / 5 | 状态机、队列、日志/配置、命令引号 | 22 通过 |
| `SettingsTests` / `SettingsConfigTests` | 4 / 3 | v0.8 settings 清洗/持久化/默认超时 | 7 通过 |
| `DailySelectionTests` / `DailyManagerTests` | 3 / 7 | 勾选过滤/顺序、每游戏独立状态 | 10 通过 |
| `UiPureLogicTests` / `ClashResolutionTests` | 3 / 3 | 刷新间隔/CHANGELOG 解析、clash 路径解析（QA-15） | 6 通过 |
| `V09ThemeTests` / `SoftwareUpdateTests` | 4 / 5 | v0.9 设计令牌/主题、软件更新纯逻辑 | 9 通过 |
| `SmallToolsTests` / `ChangelogFormatTests` | 4 / 3 | 小工具路径解析、更新日志纯文本渲染 | 7 通过 |
| **`V091IconTests`**（v0.9.1 新增） | 3 | 见 2.6 | 3 通过 |
| **合计** | **198** | | **198 通过 / 0 跳过** |

## 二、v0.9.1 图标接入覆盖说明

### 2.1 软件更新纯逻辑（`SoftwareUpdateTests` 5，沿用 v0.9）
版本比较、`parse_release_payload`（JSON/bytes/dict、`v` 前缀、name 兜底、`newer/changelog/url`）、无网络/坏 JSON/缺版本号错误处理、`check_latest` mock（GitHub/MAA）、发布页链接常量。

### 2.2 UI 设计令牌 / 主题（`V09ThemeTests` 4，沿用 v0.9）
字体/字号（最小 10）、圆角 8/12、间距 8/12/16/20/24、主窗口 1180×760/最小 1000×640/侧边栏 232、旧 Pillow 渲染尺寸 1200×560 保持；UI_* 色板合法 hex 与 HEX_* 兼容别名；标题/项目链接；`_mix` 颜色混合。

### 2.3 小工具路径解析（`SmallToolsTests` 4，沿用 v0.9）
`_script_directory` / `_log_directory`（logs>log>app）、License 识别 MIT、CHANGELOG 定位与预览、`store.open_path` mock（explorer/无效目录不启动）、Clash 候选解析。

### 2.4 更新日志纯文本渲染（`ChangelogFormatTests` 3，沿用 v0.9）
`format_changelog_text` 标题+日期、多版本最新在上、`limit_entries` 截断、Markdown 清理、空文本；`_markdown_to_plain` / `_markdown_body_to_plain`。

### 2.5 关于 / 软件更新入口（沿用 v0.9，代码走查 + 纯逻辑）
关于对话框使用 `_license_label`/`_changelog_preview_text`；软件更新使用 `RELEASE_API` + `parse_release_payload` + `format_changelog_text`，只检查/展示不自动下载；真实网络/GUI 渲染未覆盖。

### 2.6 图标资源（`V091IconTests` 3，v0.9.1 新增）
- **资产存在且尺寸正确**：`assets/LinYuxia.png`（品牌）与 `page_home.png`/`page_daily.png`/`page_settings.png`/`page_about.png` 均存在、非空、格式 PNG、尺寸 **192×192**（Pillow 只读打开，不弹窗）。
- **逻辑名映射**：`BRAND_ICON_FILE="LinYuxia.png"`；`PAGE_ICON_FILES` 四页映射精确；`icon_asset_file("brand"/"home"/"daily"/"settings"/"about")` 与常量一致；未知名称返回空。
- **路径解析**：`icon_path(name)` 返回 `store.ASSETS/<file>` 绝对路径且文件存在；未知名称 → `""`。
- **尺寸令牌**：`ICON_SIZES` window=64、window_small=32、brand 44–48、nav 20–22、page 28–32、about≥48。
- **缺失回退**：空 assets 目录下 `icon_path`/`resolve_icon_path` 均为空且不崩溃；品牌缺失回退 `hub.png`；关于页回退顺序 `page_about → LinYuxia → hub.png`；页面图标无回退。
- 交叉：`tools/test_ui_state.py` 的 v0.9.1 图标断言（品牌/页面映射、尺寸档、缺资源回退、关于回退顺序）运行 **rc=0 / FAILURES: none**。

### 2.7 交叉验证与既有回归
- `python tools/test_ui_state.py`、`tools/test_daily.py`、`tools/test_launch_spec.py` 均 **rc=0 / FAILURES: none**；`tools/test_detect_game.py` **rc=0**（只读检测，输出「本机正在运行的游戏: 无」）。
- 原有 195 条（v0.4~v0.9 契约，含 settings/勾选/DailyManager 独立状态、clash 路径、detector、launch spec、清日常、软件更新/更新日志纯文本）全部继续通过，无回归。

## 三、缺陷清单与状态

### 3.1 已修复项（持续回归通过）
QA-01/02（read_version 回退）、QA-03（save_state 返回 bool）、QA-04（版本比较）、QA-05（非 str 进程名）、QA-09（DisplayIcon 引号+索引）、QA-10（v4 迁移不覆盖用户进程名）、QA-11（游戏名最长/精确反查）、QA-12（字符串进程名不按空白拆分）、QA-13（extra_args 只保留 str 并 strip）、QA-14（命令参数统一引号处理）、QA-15（clash 便携相对路径还原）——全部保持通过。

### 3.2 保留项（低风险/设计边界，不阻塞 v0.9.1）
- QA-06：目录扫描跳过 `data/resources/config/build/dist` 等名字（设计取舍，建议 README FAQ 说明）。
- QA-07：自定义卡片 exe 丢失后仍以相对路径加载、无 missing 提示（建议后续排期）。
- QA-08：`_portable(path==root)` → `"."`（仅异常输入触发）。

> 本轮未发现新增阻塞性缺陷；图标资产/映射/回退断言全部通过。

## 四、未覆盖点与测试限制

1. **真实窗口/任务栏图标视觉（Lead 已完成视觉验收）**：主窗口图标、任务栏大/小图标、侧边栏品牌、导航按钮、页面标题、关于对话框图标的实际渲染与 DPI 缩放（64/32/46/21/30 各档）需人工确认；自动化仅验证资源与路径。
2. **打包版图标路径**：PyInstaller `_MEIPASS/assets` 下的图标解析、exe 内嵌 `hub.ico` 任务栏小图标效果未在本机打包产物上验证。
3. **真实 GUI 视觉/交互**：圆角控件、字体、分区、关于/软件更新对话框、更新日志纯文本渲染、窗口缩放/DPI。
4. **真实软件更新网络**：GitHub API 真实请求/限流/无网络、真实 release body 渲染、发布页打开（全部 mock）。
5. **小工具实际打开**：打开脚本目录/日志目录/Clash 只测路径解析与 mock `Popen`，未真实打开窗口。
6. **真实清日常/UAC/热键/日志端到端**：需 Lead 受控实测（沿用 v0.7/v0.8 的 mock 覆盖）。
7. **其它**：长时/并发运行、真实安装布局差异、联网函数、真实 PE 版本资源、权限受限目录等沿用前版。
8. **版本号**：`VERSION` 当前仍为 `0.9.0`，发布任务 bump 为 `0.9.1` 后建议再跑一次本套件（预期仍 198/198 全绿）。

## 五、结论与建议

- **v0.9.1 功能快照回归全绿：198/198 通过、0 失败/0 错误/0 跳过、exit 0（约 1.7 s）**；可重复执行、无副作用。
- 原有 195 条无回归；新增 3 条覆盖 LinYuxia 品牌 + 四页面图标的资产尺寸、映射、尺寸令牌与缺失回退。
- 未发现新增阻塞性缺陷；QA-15 保持修复；QA-06/07/08 仍为低风险/设计边界。
- 发布前建议：① Lead 已完成 v0.9.1 图标视觉验收，发布前再复核真实窗口/任务栏各尺寸档；② release 任务 bump `VERSION=0.9.1` 后重跑本套件（预期 198/198）；③ CI 增加 Windows runner 执行 `python tools/regression_test.py`（无需网络）。

## 附录：证据与约束遵守

- QA 只修改 `tools/regression_test.py`、`docs/qa-report.md`；未修改 `gamehub/`、`assets/`、`README.md`、`CHANGELOG.md` 等；未 commit / push。
- 未启动 GUI、未联网、未实际下载更新、未打开目录/启动器、未启动脚本/游戏；图标断言仅用 Pillow 只读打开图片并检查尺寸/格式。
- 配置类用例全部使用临时目录 + `mock.patch` 隔离；真实 `config.json` mtime `17:18:27`（Lead GUI 验证写入 v4），QA 运行前后未变化。
- 交叉验证：`tools/test_ui_state.py`（含图标断言）、`tools/test_daily.py`、`tools/test_launch_spec.py` 均 rc=0 / FAILURES: none；`tools/test_detect_game.py` rc=0。
- 稳定性：本套件连续运行 3 次均全绿（含多线程 `DailyManager` 用例）。
