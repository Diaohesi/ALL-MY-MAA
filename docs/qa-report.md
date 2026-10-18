# All-My-Maa 回归测试报告（v0.9.0 最终版）

| 项目 | 内容 |
| --- | --- |
| 仓库 | `D:\All MAA\GameHub`（GitHub: https://github.com/Diaohesi/All-My-Maa ） |
| 被测版本 | **All-My-Maa v0.9.0**（功能快照：v0.8.0 + UI 美化（圆角/字体/分区/关于/软件更新/更新日志纯文本渲染）+ 小工具 + QA-15 修复；`gamehub.__init__.VERSION` 当前仍为 `0.8.0`，按发布流程由 release 任务 bump 为 `0.9.0`） |
| 代码基线 | `a223c03`（docs: rename project to All-My-Maa） |
| 工作区增量 | `gamehub/ui.py` **+1081 / -388**（圆角控件/设计令牌应用/侧边栏小工具/关于与软件更新对话框/更新日志纯文本渲染）、`gamehub/theme.py` **+48 / -12**（v0.9 设计令牌：字体、圆角、间距、深色 surface 色板）、`tools/test_ui_state.py` **+99**（v0.9 自测补充）、`tools/grab_hub.py` 小改；`CHANGELOG/README/docs/index.html` 由文档任务更新 |
| 测试脚本 | `tools/regression_test.py`（标准库 `unittest`，v0.9 最终版 **195 用例 / 37 个测试类**） |
| 执行命令 | `python tools/regression_test.py`（任意 CWD 可运行；`-v` 详细输出） |
| 执行时间 | 2026-10-18（最终快照：`gamehub/ui.py` mtime 17:07:35，`gamehub/theme.py` mtime 16:58:56，`gamehub/store.py` mtime 16:40:23） |
| 运行环境 | Windows 10/11 · Python 3.13.7 · Pillow 12.2.0 · 字体 msyh.ttc/msyhbd.ttc 存在 |
| 结果 | **195 个用例：195 通过 / 0 失败 / 0 错误 / 0 跳过；退出码 0（全绿）** |
| 耗时 | 约 1.5–1.7 s |

实际输出结尾：

```
----------------------------------------------------------------------
Ran 195 tests in 1.581s

OK

===== 汇总 =====
用例数: 195  失败: 0  错误: 0  跳过: 0
```

> **本版更新（179 → 195 用例，v0.9 UI/软件更新/小工具覆盖）**
> - 新增 **16 条**用例（4 个测试类）：`V09ThemeTests`（4）、`SoftwareUpdateTests`（5）、`SmallToolsTests`（4）、`ChangelogFormatTests`（3）。
> - 覆盖：设计令牌/字体/色板/项目链接、软件更新纯逻辑（版本比较 / `parse_release_payload` / 无网络错误 / 链接构造 / `check_latest` mock）、小工具路径解析（脚本/日志/License/更新日志/Clash 候选，打开动作 mock）、更新日志纯文本渲染（标题/列表/粗体/链接/多版本/截断/空文本）。
> - 原有 179 条（v0.4~v0.8 契约）全部继续通过；`tools/test_ui_state.py`、`test_daily.py`、`test_launch_spec.py`、`test_detect_game.py` 交叉复核均 rc=0。
> - 全部使用 mock/临时目录：**不启动 GUI、不联网、不实际下载更新、不打开目录、不启动脚本/游戏**。

## 一、测试范围与覆盖矩阵

| 测试类 | 用例数 | 覆盖点 | 结果 |
| --- | --- | --- | --- |
| `VersionTests` / `PathHelperTests` / `CleanProcsTests` / `ProcNameTests` | 3 / 5 / 5 / 1 | 版本比较、路径转换、进程名清洗 | 14 通过 |
| `ConfigStateTests` | 13 | 配置往返/BOM/损坏 JSON/Clash、config v4、detect 往返、v3→v4 迁移 | 13 通过 |
| `FindAppExeTests` / `PickBestExeTests` / `ReadVersionTests` / `ProcessTests` | 4 / 3 / 8 / 3 | 路径扫描、版本读取、进程快照 | 18 通过 |
| `RenderSmokeTests` / `ImportSmokeTests` | 8 / 2 | 旧 Pillow 渲染尺寸、`import gamehub.ui`（含 v0.9 导入链） | 10 通过 |
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
| **`V09ThemeTests`**（v0.9 新增） | 4 | 见 2.2 | 4 通过 |
| **`SoftwareUpdateTests`**（新增） | 5 | 见 2.1 | 5 通过 |
| **`SmallToolsTests`**（新增） | 4 | 见 2.3 | 4 通过 |
| **`ChangelogFormatTests`**（新增） | 3 | 见 2.4 | 3 通过 |
| **合计** | **195** | | **195 通过 / 0 跳过** |

## 二、v0.9 新功能覆盖说明

### 2.1 软件更新纯逻辑（`SoftwareUpdateTests` 5）
- 版本比较：`version_key("v0.9.0")==(0,9,0)`；`v0.9.0 > v0.8.0`、`v0.10.0 > v0.9.9`、`V0.9.0 > v0.8.0`；相同版本/更低版本不提示更新。
- `ui.parse_release_payload`：支持 JSON 字符串 / bytes / dict 输入；`tag_name` 带/不带 `v` 前缀、`tag_name` 缺失时用 `name` 兜底；返回 `version/current/newer/changelog/url/name/published_at`；`html_url` 缺失时回退 `RELEASE_PAGE`。
- 错误处理：坏 JSON → `解析 release 信息失败：…`；非 dict → `release 信息格式不正确`；无版本号（`{}` / `"v"`）→ `release 信息缺少版本号`；无法识别版本（`release-latest`）→ `无法识别版本号：…`；坏字节序列不抛异常。
- `store.check_latest`（全部 mock，无真实网络）：GitHub release 正常返回版本、网络异常返回 `None`、无 release 地址不调用网络；MAA 的 `api.maa.plus` 分支 mock `http_get` 返回版本、异常时回退失败返回 `None`。
- 链接常量：`GITHUB_REPO="Diaohesi/All-My-Maa"`、`PROJECT_GITHUB`、`PROJECT_PAGES`、`RELEASE_API`/`RELEASE_PAGE` 与仓库一致。

### 2.2 UI 设计令牌 / 主题（`V09ThemeTests` 4）
- 字体：`UI_FONT="Microsoft YaHei UI"`；字号 title 20–22、page 16、aux 最小 10（全部 ≥10）。
- 圆角/间距：`RADIUS` 10–12、`RADIUS_SM=8`；间距体系 8/12/16/20/24；主窗口 1180×760、最小 1000×640、侧边栏 232。
- 兼容性：旧 Pillow 渲染尺寸 `W,H=1200,560`、`BTN_W/H=99,44`、卡片坐标保持；旧常量别名 `HEX_*` 与新 `UI_*` 一致。
- 色板：所有 `UI_*` 颜色均为合法 `#rrggbb`；8 个 accent 预设有效且不重复；`TITLE="All-My-Maa · 游戏脚本中心"`。
- `ui._mix` 颜色混合：0/1/0.5 比例、红绿混合结果正确，异常输入原样返回。

### 2.3 小工具路径解析（`SmallToolsTests` 4，打开动作 mock）
- `ui._script_directory`：绝对路径原样、空/None 回退 `store.APP_DIR`、相对路径按 CWD 转绝对（测试内临时切换 CWD 后恢复）。
- `ui._log_directory`：优先 `<app>/logs`，其次 `<app>/log`，都没有回退 app 目录。
- `ui._find_license` / `_license_label`：能找到仓库 LICENSE，识别为 `License：MIT License`。
- `ui._find_changelog` / `_changelog_preview_text`：能定位 CHANGELOG，预览非空、最新版本在最上面（以 `v` 开头）。
- `store.open_path`（mock `subprocess.Popen`）：有效目录 → `["explorer", folder]`；不存在目录 → False 且不启动进程。
- Clash 候选解析：`CLASH_CANDIDATES` 中第一个存在的路径被选中（前面的失效候选被跳过）。

### 2.4 更新日志纯文本渲染（`ChangelogFormatTests` 3）
- `format_changelog_text`：`## vX.Y.Z (日期)` → `vX.Y.Z · 日期` 单独一行；多版本按版本号从新到旧（最新在最上面）；`limit_entries` 只保留最新 N 个版本且不残留旧版本内容。
- Markdown 清理：`#` 标题、`-`/`*`/数字列表、`>` 引用、`**粗体**`/`__`/反引号/`~~删除~~`、`[文字](链接)`、`![图](链接)`、`<url>` 均转为纯文本；分隔线丢弃；条目换行保留；空/纯空白 → ""。
- `_markdown_to_plain` / `_markdown_body_to_plain` 单元断言：图片/链接保留文字、粗体下划线代码删除线去除、标题/列表/引用前缀去除、分隔线 → ""、连续空行折叠、尾部空行清理。

### 2.5 关于 / 软件更新入口（代码走查 + 纯逻辑）
- 关于对话框展示 `_license_label()`、`_find_changelog()`、`_changelog_preview_text()`（纯文本、最新在上）与项目链接（GitHub/项目主页）。
- 软件更新检查使用 `RELEASE_API` 获取 latest release，经 `parse_release_payload` 得到版本/更新说明/发布页链接，再用 `format_changelog_text` 纯文本展示；**只检查/展示，不自动下载安装**（无真实网络请求被测试）。
- 对话框、圆角控件、字体等 Tk 视觉部分需 GUI，未在自动化中覆盖（见未覆盖点）。

### 2.6 交叉验证与既有回归
- QA 独立运行 feature-dev 自测：`python tools/test_ui_state.py`、`tools/test_daily.py`、`tools/test_launch_spec.py` 均 **rc=0 / FAILURES: none**；`tools/test_detect_game.py` rc=0（只读检测，输出「本机正在运行的游戏: 无」）。
- 原有 179 条（v0.4~v0.8 契约，含 settings/勾选/DailyManager 独立状态、clash 路径、detector、launch spec、清日常）全部继续通过，无回归。
- 稳定性：本套件连续运行 3 次均 195/195 通过（含多线程 `DailyManager` 用例）。

## 三、缺陷清单与状态

### 3.1 已修复项（持续回归通过）
QA-01/02（read_version 回退）、QA-03（save_state 返回 bool）、QA-04（版本比较）、QA-05（非 str 进程名）、QA-09（DisplayIcon 引号+索引）、QA-10（v4 迁移不覆盖用户进程名）、QA-11（游戏名最长/精确反查）、QA-12（字符串进程名不按空白拆分）、QA-13（extra_args 只保留 str 并 strip）、QA-14（命令参数统一引号处理）、QA-15（clash 便携相对路径还原）——全部保持通过。

### 3.2 保留项（低风险/设计边界，不阻塞 v0.9）
- QA-06：目录扫描跳过 `data/resources/config/build/dist` 等名字（设计取舍，建议 README FAQ 说明）。
- QA-07：自定义卡片 exe 丢失后仍以相对路径加载、无 missing 提示（建议后续排期）。
- QA-08：`_portable(path==root)` → `"."`（仅异常输入触发）。

> 本轮未发现新增阻塞性缺陷；v0.9 纯逻辑（更新解析/日志渲染/令牌/小工具路径）断言全部通过。

## 四、未覆盖点与测试限制

1. **真实 GUI 视觉/交互（Lead 已完成视觉验收，需在发布前复核）**：圆角控件观感、字体/字号/分区、侧边栏小工具点击、关于对话框、软件更新对话框、更新日志纯文本渲染的实际显示、窗口缩放/DPI、hover/按下/禁用等按钮状态。本任务不启动 GUI/mainloop。
2. **真实软件更新网络**：`RELEASE_API` 真实请求、GitHub API 限流/无网络、真实 release body 的 Markdown 渲染、发布页打开、下载页跳转。自动化全部 mock，未发起真实网络请求。
3. **小工具实际打开**：打开脚本目录/日志目录/Clash Verge（`explorer`/启动器/进程置前）只测试路径解析并把 `Popen` mock 掉，未真实打开窗口；真实 Clash 路径/自动查找依赖本机安装。
4. **真实清日常/UAC/热键/日志端到端**：真实启动 ok-ww/MAA/MXU、UAC、LinkStart 热键、真实日志标记、超时/停止等需 Lead 受控实测（沿用 v0.7/v0.8 的 mock 覆盖）。
5. **真实安装布局/环境差异**：ok-ww/MAA/MXU 不同版本配置结构、打包版 `_MEIPASS` 路径下的 LICENSE/CHANGELOG 定位未在本机验证。
6. **长时/并发**：跨天运行、长时间监控、并发点击/重复启动、系统休眠唤醒未覆盖。
7. **联网函数 / 真实 PE 版本资源 / 权限受限目录**：沿用前版报告，未测。
8. **版本号**：`VERSION` 当前仍为 `0.8.0`，发布任务 bump 为 `0.9.0` 后建议再跑一次本套件（预期仍 195/195 全绿）。

## 五、结论与建议

- **v0.9.0 功能快照回归全绿：195/195 通过、0 失败/0 错误/0 跳过、exit 0（约 1.5–1.7 s）**；可重复执行、无副作用。
- 原有 179 条无回归；新增 16 条覆盖软件更新纯逻辑、设计令牌/主题、小工具路径解析、更新日志纯文本渲染。
- 未发现新增阻塞性缺陷；QA-15 保持修复；QA-06/07/08 仍为低风险/设计边界。
- 发布前建议：① Lead 已完成 v0.9 UI 视觉验收，发布前再复核关于/软件更新/更新日志的实际渲染与小工具点击；② release 任务 bump `VERSION=0.9.0` 后重跑本套件（预期 195/195）；③ CI 增加 Windows runner 执行 `python tools/regression_test.py`（无需网络）。

## 附录：证据与约束遵守

- QA 只修改 `tools/regression_test.py`、`docs/qa-report.md`；未修改 `gamehub/`、`README.md`、`CHANGELOG.md` 等；未 commit / push。
- 未启动 GUI、未联网、未实际下载更新、未打开目录/启动器、未启动脚本/游戏、未发送真实热键；相关用例全部 mock（`http_get`/`github_latest_tag`/`Popen`/`subprocess.Popen`）或纯函数断言。
- 配置类用例全部使用临时目录 + `mock.patch` 隔离；真实 `config.json` mtime `16:54:59`（Lead GUI 验证写入 v4），QA 运行前后未变化。
- 交叉验证：`tools/test_ui_state.py`、`tools/test_daily.py`、`tools/test_launch_spec.py` 均 rc=0 / FAILURES: none；`tools/test_detect_game.py` rc=0。
- 稳定性：本套件连续运行 3 次均 195/195 通过。
