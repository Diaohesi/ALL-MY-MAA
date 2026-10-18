# GameHub 回归测试报告（v0.5.0 最终版）

| 项目 | 内容 |
| --- | --- |
| 仓库 | `D:\All MAA\GameHub`（GitHub: https://github.com/Diaohesi/ALL-MY-MAA ） |
| 被测版本 | GameHub Lite **v0.5.0**（功能快照：v0.4.0 基线 + 游戏启动程序自动检测 + 缺陷修复；`gamehub.__init__.VERSION` 当前仍为 `0.4.0`，按发布流程由 release-engineer 在 task-6 统一 bump 为 `0.5.0`） |
| 基线提交 | `8d7a394`（docs: add maintainer release workflow） |
| 工作区增量 | `gamehub/store.py` **+440 / -7**、`gamehub/ui.py` **+227 / -29**（feature-dev task-1 交付），新增 `tools/test_detect.py`、`tools/regression_test.py` |
| 测试脚本 | `tools/regression_test.py`（标准库 `unittest`，无需 pytest） |
| 执行命令 | `python tools/regression_test.py`（任意 CWD 可运行；`-v` 详细输出） |
| 执行时间 | 2026-10-18（快照：`gamehub/store.py` mtime 13:59:11，`gamehub/ui.py` mtime 13:59:33） |
| 运行环境 | Windows 10/11 · Python 3.13.7 · Pillow 12.2.0 · 字体 msyh.ttc/msyhbd.ttc 存在 |
| 结果 | **57 个用例：57 通过 / 0 失败 / 0 错误 / 0 跳过；退出码 0（全绿）** |
| 耗时 | 约 1.25 s |

实际输出结尾：

```
----------------------------------------------------------------------
Ran 57 tests in 1.251s

OK

===== 汇总 =====
用例数: 57  失败: 0  错误: 0  跳过: 0
```

> **本版说明**：feature-dev 已交付 task-1（v0.5 自动检测 + QA-01/02/03/04/05/09 修复）。本报告为**最终回归版**：
> - 旧测试中断言"旧行为"的 1 条用例已改为期望行为（`_clean_procs([None]) == []`）；
> - 新增 2 条回归用例（`read_version` 非字符串版本回退、`_clean_icon_path` 引号+索引解析），并升级 `save_state`/`is_newer`/`version_key` 等断言；
> - 用例总数 55 → **57**，全部通过。

## 一、测试范围与覆盖矩阵

测试只做 **import + Pillow 内存渲染**，不创建 tkinter 窗口、不进入 `mainloop`、不重启正在运行的 Hub、不联网。
涉及配置读写的用例全部用 `unittest.mock.patch` 把 `store.CONFIG` / `store.SEARCH_ROOT` 指向临时目录，**不会读写仓库里的真实 `config.json`**。
v0.5 自动检测用例通过 mock 把「注册表 / 常见目录」两个数据源限制在临时目录，**不会扫描本机真实安装**，结果确定可重复；真实扫描由 `tools/test_detect.py` 单独验证（见第二节）。

| 测试类 | 用例数 | 覆盖点 | 结果 |
| --- | --- | --- | --- |
| `VersionTests` | 3 | `version_key`（带 v 前缀、多段、中文/空/None、前 4 段上限、1.10 数字比较、**-rc/+build 后缀忽略**）；`is_newer` 新旧/相等/空版本；**预发布不算更新 + 数字段零补齐**（QA-04 回归） | 3 通过 |
| `PathHelperTests` | 5 | `_portable` 根目录内→正斜杠相对路径、根外→保留绝对路径、`_portable`↔`_absolute` 往返；`_absolute` 空值/相对/绝对/不存在 | 5 通过 |
| `CleanProcsTests` | 5 | `_clean_procs` 英/中文逗号分号、空白、list/tuple、去空项、大写化、`fallback_exe` 兜底；**非 str 项（None/数字/嵌套）被跳过**（QA-05 回归） | 5 通过 |
| `ProcNameTests` | 1 | `proc_names_for_exe` 路径→大写进程名、空值/None→[] | 1 通过 |
| `ConfigStateTests` | 7 | `save_state`→`load_state` 往返（自定义卡片 game/script/accent/game_exe/game_procs/script_procs/download/fallback_version/icon/相对路径持久化）；内置卡片 accent/download 往返；v1/v2 纯路径格式兼容；UTF-8 BOM 配置兼容；损坏 JSON 回退默认；Clash 显式保存与自动探测；**保存失败返回 `False` 不静默**（QA-03 回归） | 7 通过 |
| `FindAppExeTests` | 4 | `find_app_exe` 递归、大小写不敏感、`SEARCH_SKIP` 目录与点目录跳过、`max_depth` 边界、空/不存在 root | 4 通过 |
| `PickBestExeTests` | 3 | 多版本按文件夹版本号择优、版本相同按 mtime 择优、空列表/None、不可读路径不崩溃 | 3 通过 |
| `ReadVersionTests` | 8 | `read_version`：MaaNTE/MaaEnd `interface.json`（含/不含 v 前缀）、MAA `cache/version/summary.json`、ok-ww `app.json`、文件缺失回退、JSON 损坏回退；**wuwa 缺 `current_version` 回退 fallback**（QA-01 回归）、**version 为 null/数组/布尔时回退 fallback**（QA-02 回归） | 8 通过 |
| `ProcessTests` | 3 | `snapshot_processes` 返回集合且包含当前进程名；`pids_for_procs` 含自身 PID；未知进程名→空集合 | 3 通过 |
| `RenderSmokeTests` | 8 | `render_window` 4 卡整页 **1200×560** RGB（悬停索引 2）、空页渲染；`render_script_button` 三态 **99×44**；`render_game_button` 两态 99×44；`render_dot` **22×22**（size=8→28×28，自定义颜色）；`render_page_arrow` 左右/悬停 **32×32**；`render_hub_icon` 256×256；`hex2rgb`/`accent_rgba` | 8 通过 |
| `ImportSmokeTests` | 2 | `import gamehub.ui` 通过（只导入模块，不创建窗口/mainloop）、`ui.run`/`GameHub` 存在；`gamehub.VERSION` 为 `x.y.z` 语义化格式 | 2 通过 |
| `GameCandidatesTests`（v0.5） | 8 | 短英文关键词按单词边界命中（`nte` 不命中 `center`）；`_game_profile` 按 key/游戏名/None 生成关键词与启动程序名提示；`_score_exe_path` 命中/无关 exe 排除/卸载类噪声排除；**`_clean_icon_path` 解析 `"path.exe",0` / `path.exe,0`（QA-09 回归）**；`_find_game_exes` 临时目录树扫描、`GAME_SCAN_SKIP` 跳过、噪声过滤、结果限定临时目录；`find_game_candidates` 常见目录来源（mock 数据源）、注册表 InstallLocation 来源、按 score 降序、`limit` 截断、返回结构 `{path,name,source,score}` | 8 通过 |
| **合计** | **57** | | **57 通过 / 0 跳过** |

## 二、v0.5「游戏启动程序自动检测」验证说明

### 2.1 自动化测试（确定性、无真实安装依赖）
- 覆盖评分/过滤/扫描/合并/排序/limit/来源标注/词边界/图标路径解析（8 条用例，见上表）。
- 注册表与常见目录数据源被 mock 到临时目录，**不依赖本机是否安装游戏**，可重复执行。

### 2.2 真实扫描验证（QA 独立执行，非编造）
QA 在任务中执行 `python tools/test_detect.py`（命令行自测，无 GUI、不启动 Hub），2026-10-18 本机实际结果如下（与 feature-dev 交付汇报一致）：

| 游戏 | 首选候选 | 来源 | 路径 | 候选数 | 耗时 |
| --- | --- | --- | --- | --- | --- |
| 明日方舟（maa） | MuMu模拟器 · **MuMuNxMain.exe** | 注册表 | `E:\MuMuPlayer-12.0\nx_main\MuMuNxMain.exe` | 6 | 274 ms |
| 异环（nte） | 异环 · **NTELauncher.exe** | 注册表 | `D:\Neverness To Everness\NTELauncher.exe` | 3 | 186 ms |
| 鸣潮（wuwa） | 鸣潮 · **Wuthering Waves.exe** | 注册表 | `E:\Wuthering Waves\Wuthering Waves Game\Wuthering Waves.exe` | 4 | 197 ms |
| 明日方舟终末地（maaend） | 鹰角启动器 · **Endfield.exe** | 注册表 | `E:\Hypergryph Launcher\games\Endfield Game\Endfield.exe` | 1 | 175 ms |

- 四个游戏全部命中，首选候选均为游戏/启动器主程序；单游戏耗时 **175–274 ms**，远低于 `GAME_DETECT_BUDGET = 1.8s` 预算。
- 候选排序合理（如明日方舟首选 MuMuNxMain.exe，其次 Launcher/Arknights.exe；鸣潮首选游戏本体，其次 launcher/Client-Win64-Shipping）。

### 2.3 UI 集成（代码走查，GUI 手工验证由 Lead 集成阶段完成）
- 「编辑卡片」对话框的「游戏启动程序」行提供「浏览 / **自动检测**」；点击后按当前编辑的游戏名/关键词调用 `find_game_candidates`，无候选时 `messagebox` 提示"未检测到…可手动浏览"，有候选时弹出候选选择对话框，选中后回填 `game_exe` 输入框（代码：`ui.py` `_auto_detect_game` / `GameCandidateDialog`）。
- 右键「启动游戏」时若 `game_exe` 未配置或文件不存在：先提示"正在自动检测…"→ 有候选弹选择框 → 选中后写入 `game_exe`/`game_procs` 并 `_save_config()` 再启动；无候选回退系统文件选择框；取消则不启动（代码：`ui.py` `launch_game`）。
- 以上 GUI 交互**未在自动化中覆盖**（约束禁止启动 GUI/mainloop），由 Lead 集成验证。

## 三、缺陷状态（v0.5.0 最终）

| ID | 原级别 | 状态 | 说明 / 验证方式 |
| --- | --- | --- | --- |
| QA-01 | 低 | ✅ **已修复并验证** | `read_version` 异环 `app.json` 缺 `current_version` 时回退 `fallback_version`；`ReadVersionTests.test_wuwa_missing_current_version_falls_back` 断言 `v0.0.1` |
| QA-02 | 低 | ✅ **已修复并验证** | `interface.json` 的 `version` 为 `null`/数组/布尔时经 `_version_text` 过滤并回退 `fallback_version`；`test_non_string_version_falls_back` 覆盖 3 种脏值 |
| QA-03 | 中 | ✅ **已修复并验证** | `save_state` 返回 `bool`（成功 `True`/失败 `False`），UI 可提示；`test_custom_app_roundtrip` 断言 `True`，`test_save_state_reports_write_failure` 断言写失败返回 `False` 且不生成文件 |
| QA-04 | 低 | ✅ **已修复并验证** | `version_key` 先按 `-`/`+` 截断（`v1.0.0-rc1 → (1,0,0)`），`is_newer` 对数字段零补齐（`v6.19 == v6.19.0`，不再误判）；`test_version_key` / `test_is_newer_prerelease_and_zero_padding` |
| QA-05 | 低 | ✅ **已修复并验证** | `_clean_procs` 跳过非 `str` 项（`[None, 3, ["x"]]` 不再产生 `"NONE"`），保留 `fallback_exe` 兜底；旧断言已更新为 `[]` |
| QA-06 | 低/风险 | ⏳ **保留（未修复）** | `SEARCH_SKIP`（v0.4）与 `GAME_SCAN_SKIP`（v0.5）仍跳过 `data/resources/config/build/dist` 等常见目录名；属"避免误报/深扫"的设计取舍，未在本次改动中调整。建议后续在 README 常见问题说明，或按"脚本专用跳过表"与"通用扫描"拆分排期 |
| QA-07 | 低 | ⏳ **保留（未修复）** | `load_state` 对已丢失 exe 的自定义卡片仍以相对路径加载（无 missing 标记），启动时提示"文件不存在"；建议后续加载时标记 `missing` 并在编辑弹窗引导重新选择（低优先级） |
| QA-08 | 信息 | ℹ️ **保留（设计边界）** | `_portable(path, root)` 在 `path == root` 时返回 `"."`，仅把目录当 exe 路径的异常输入会触发，不排期 |
| QA-09 | 低 | ✅ **已修复并验证** | `_clean_icon_path` 现在支持 `"C:\x\game.exe",0` / `C:\x\game.exe,0` / 纯路径 / 纯引号路径，非 exe 返回 `""`；`GameCandidatesTests.test_clean_icon_path_quoted_index` |

> 说明：QA-01/02/03/05/09 的修复由 feature-dev 在 task-1 内完成，QA 已将回归断言从"记录旧行为"升级为"期望行为"；其中唯一一条旧断言（`_clean_procs([None]) == ["NONE"]`）已按 Lead 要求改为 `[]` 并补充"非 str 被跳过 + fallback 兜底"断言。

## 四、未覆盖点与测试限制

1. **GUI 交互（由 Lead 集成阶段手工验证）**：编辑对话框「自动检测」按钮、无候选提示、候选选择对话框（列表/双击/确定/取消）、`launch_game` 自动检测→保存配置→启动的完整链路、`GameCandidateDialog` 样式与深色主题。本任务禁止启动 GUI/mainloop，未覆盖。
2. **真实注册表/磁盘扫描的异常场景**：自动化测试 mock 数据源；真实扫描已用 `tools/test_detect.py` 在本机验证 4 款游戏（结果见 2.2），但未覆盖注册表权限受限、异常盘符/网络盘、扫描超时截断（`GAME_DETECT_BUDGET`）、`max_dirs=300` 上限、`--all` 全量模式。
3. **联网函数**：`http_get` / `final_url` / `github_latest_tag` / `check_latest` 未测（避免网络依赖与限流）。
4. **真实 PE 版本资源**：`file_version` 只测"空 exe 无版本→回退"路径，未构造带版本资源的 exe。
5. **会启动进程/抢焦点的函数**：`launch_exe` / `shell_launch` / `open_path` / `bring_to_front` / `focus_window` 未测（约束要求不启动进程、不影响用户运行中的 Hub）。
6. **其它**：BOM+自定义卡片组合、渲染回退路径（损坏图标/字体缺失）、UI 后台线程与配置保存并发、ACL 受限目录（`Program Files`）下 `save_state` 的真实表现未覆盖。

## 五、结论与建议

- **v0.5.0 最终回归全绿：57/57 通过、0 失败/0 错误/0 跳过、exit 0（约 1.25 s）**，可重复执行、无副作用。
- 6 项缺陷（QA-01/02/03/04/05/09）已修复并经**新断言**验证；QA-06/07/08 保留为低风险/设计边界项并已说明，不影响发布。
- 真实自动检测在本机 4 款游戏全部命中，首选候选正确，耗时远低于预算；GUI 集成（自动检测按钮/候选选择/启动游戏链路）由 Lead 在集成阶段手动验证。
- 发布流程建议：release-engineer 在 task-6 将 `VERSION` bump 为 `0.5.0` 后**再跑一次** `python tools/regression_test.py`（仅版本号变化，预期仍 57/57 全绿）；发布前完成 GUI 手工验证。
- CI 建议：在 `.github/workflows` 增加 Windows runner 执行 `python tools/regression_test.py`（无需网络）的步骤，守护纯函数/配置/渲染/检测核心回归。

## 附录：证据与约束遵守

- 测试全程未修改 `gamehub/`、`README.md`、`CHANGELOG.md`；只写 `tools/regression_test.py`、`docs/qa-report.md`。
- 未 commit / push；未启动 GUI/mainloop；未重启用户正在运行的 Hub。
- QA 测试全程用临时目录 + `mock.patch` 隔离配置，未写真实 `config.json`（QA 历次运行前后其 mtime 保持 `13:44:43`；最终检查时 mtime 为 `14:02:40`，来自其它成员并行进行的 GUI/集成验证，与 QA 用例无关）。
- 自动化用例不联网；自动检测测试的注册表/常见目录数据源已 mock 到临时目录。
