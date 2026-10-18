# GameHub 回归测试报告（v0.6.0 最终版）

| 项目 | 内容 |
| --- | --- |
| 仓库 | `D:\All MAA\GameHub`（GitHub: https://github.com/Diaohesi/ALL-MY-MAA ） |
| 被测版本 | GameHub Lite **v0.6.0**（功能快照：v0.5.0 + 游戏运行检测机制 `gamehub/detector.py` + config v4 + QA-10/11/12 修复；`gamehub.__init__.VERSION` 当前仍为 `0.5.0`，按发布流程由 release 任务 bump 为 `0.6.0`） |
| 代码基线 | `f9bf316`（docs: refresh screenshots for v0.5.0，已发布 v0.5.0） |
| 工作区增量 | 新增 `gamehub/detector.py`（842 行）、`tools/test_detect_game.py`、`docs/game-detection-research.md`；`gamehub/store.py` **+203 / -5**（config v4、规则清洗、v3→v4 迁移、QA-10/11/12 修复）、`gamehub/ui.py` **+161 / -20**（检测规则输入框、状态展示、自动检测回填） |
| 测试脚本 | `tools/regression_test.py`（标准库 `unittest`，v0.6 最终版 **111 用例**） |
| 执行命令 | `python tools/regression_test.py`（任意 CWD 可运行；`-v` 详细输出） |
| 执行时间 | 2026-10-18（最终快照：`gamehub/store.py` mtime 14:40:58，`gamehub/detector.py` mtime 14:30:43，`gamehub/ui.py` mtime 14:30:22） |
| 运行环境 | Windows 10/11 · Python 3.13.7 · Pillow 12.2.0 · 字体 msyh.ttc/msyhbd.ttc 存在 |
| 结果 | **111 个用例：111 通过 / 0 失败 / 0 错误 / 0 跳过；退出码 0（全绿）** |
| 耗时 | 约 1.8 s |

实际输出结尾：

```
----------------------------------------------------------------------
Ran 111 tests in 1.776s

OK

===== 汇总 =====
用例数: 111  失败: 0  错误: 0  跳过: 0
```

> **本版更新（107 → 111 用例，QA-10/11/12 修复复核）**
> - QA-10 修复：v3→v4 迁移只在「`game_procs` 为空 / 全部是旧启动器误配（`NTELAUNCHER.EXE`、`LAUNCHER.EXE`）」时替换为游戏本体进程，用户自定义进程名（如 `MUMUPLAYER.EXE`）保留；新增 3 条回归断言。
> - QA-11 修复：`_game_profile` 按游戏名反查改为「精确/最长关键词优先」，「明日方舟终末地」→ `maaend`、「明日方舟」→ `maa`；新增/扩展 1 条断言。
> - QA-12 修复：进程名/包名字符串改用 `_detect_names`，只按逗号/分号/换行拆分，「Wuthering Waves.exe」不再被空白拆成两个；新增 1 条断言。
> - 原有 107 条全部继续通过；其中 QA-10 相关的旧迁移断言已按修复后的正确行为更新。

## 一、测试范围与覆盖矩阵

测试只做 **import + Pillow 内存渲染 + mock 窗口/进程快照**，不创建 tkinter 窗口、不进入 `mainloop`、不重启 Hub、不联网。配置类用例全部用 `unittest.mock.patch` 把 `store.CONFIG` / `store.SEARCH_ROOT` 指向临时目录，**不读写真实 `config.json`**。

| 测试类 | 用例数 | 覆盖点 | 结果 |
| --- | --- | --- | --- |
| `VersionTests` | 3 | `version_key` / `is_newer`（含 `-rc`/零补齐语义） | 3 通过 |
| `PathHelperTests` | 5 | `_portable` / `_absolute` 路径转换与往返 | 5 通过 |
| `CleanProcsTests` | 5 | `_clean_procs` 分隔符/大小写/非 str 跳过/fallback | 5 通过 |
| `ProcNameTests` | 1 | `proc_names_for_exe` | 1 通过 |
| `ConfigStateTests` | 13 | 配置往返/内置字段/BOM/损坏 JSON/Clash；config v4 与自定义 detect 往返；**v3→v4 迁移：仅旧启动器/空值迁移、自定义/混合进程名保留、空值填默认**（QA-10 修复验证） | 13 通过 |
| `FindAppExeTests` | 4 | `find_app_exe` 递归/skip/max_depth | 4 通过 |
| `PickBestExeTests` | 3 | `pick_best_exe` 版本/mtime 择优 | 3 通过 |
| `ReadVersionTests` | 8 | `read_version` interface.json / app.json / cache / 回退 | 8 通过 |
| `ProcessTests` | 3 | `snapshot_processes` / `pids_for_procs` | 3 通过 |
| `RenderSmokeTests` | 8 | `render_window` 1200×560、按钮/dot/page_arrow 尺寸等 | 8 通过 |
| `ImportSmokeTests` | 2 | `import gamehub.ui`（含 detector 导入链）不建窗口；VERSION 语义化格式 | 2 通过 |
| `GameCandidatesTests` | 8 | v0.5 游戏启动程序自动检测（mock 注册表/常见目录） | 8 通过 |
| `DetectRuleCleanTests` | 7 | config v4 规则 schema：`type` 别名、必填字段、非法规则丢弃、文本清洗、`proc_class_check`、`launcher`/`cloud`、`min_client_size`/`title_optional`/`match`/`require_visible` 边界；**字符串进程名含空格不被拆分**（QA-12 修复验证） | 7 通过 |
| `DetectorInterfaceRulesTests` | 6 | `interface.json` controller[].win32 提取：多 controller 并集、去重、cloud 单列、非 win32 忽略、缺失/损坏回退内置表、深拷贝隔离、**按游戏名最长/精确反查（明日方舟终末地→maaend）**、缓存 mtime 失效 | 6 通过 |
| `BuiltinRuleTableTests` | 2 | 四款内置游戏规则表结构校验与关键目标 | 2 通过 |
| `WindowMatchTests` | 8 | 窗口匹配纯函数：大小写/空白/正则、`title_optional`、any/all、空/非法规则、最小客户区、最小化不过滤、`require_visible`、多 controller 并集、窗口+进程双重校验与路径降级 | 8 通过 |
| `ProcMatchTests` | 3 | 进程名大小写、`path_re` 命中/不命中、路径不可读降级 | 3 通过 |
| `GameRulesSourceTests` | 7 | 规则优先级 user > auto > legacy > none、非法用户规则回退 auto、字段⇄规则往返、`rules_equal` | 7 通过 |
| `DetectGameStateTests` | 11 | `detect_game_state` 各 running/reason 分支（window/proc/adb/launcher/cloud/未运行/未配置/proc_class_check/仅 game_exe）与 `detect_game` 元组 | 11 通过 |
| `DetectorSnapshotSmokeTests` | 4 | 真实窗口快照字段/类型/缓存、`process_path` 自身 pid、真实 `detect_game_state` 契约 | 4 通过 |
| **合计** | **111** | | **111 通过 / 0 跳过** |

## 二、QA-10/11/12 修复验证（本轮重点）

| ID | 修复内容 | 回归断言（已通过） |
| --- | --- | --- |
| **QA-10** | `load_state` 的 v4 迁移条件改为：仅当内置卡片 `game_procs` 为空，或**全部**命中旧启动器误配集合 `LEGACY_GAME_PROCS = {NTELAUNCHER.EXE, LAUNCHER.EXE}` 时才替换为 `BUILTIN_GAME_PROCS`；用户自定义进程名与混合列表保留 | ① v3 `maa: ["LAUNCHER.EXE"]` → `["ARKNIGHTS.EXE"]`、`nte: ["NTELAUNCHER.EXE","LAUNCHER.EXE"]` → `["HTGAME.EXE"]`；② v3 `wuwa: ["MUMUPLAYER.EXE"]` 升级后**保留** `["MUMUPLAYER.EXE"]`；③ 空列表/缺失字段才填默认（`nte []` → `["HTGAME.EXE"]`、`wuwa 缺失` → `["CLIENT-WIN64-SHIPPING.EXE"]`）；④ 混合 `["LAUNCHER.EXE","MUMUPLAYER.EXE"]` 整体保留（迁移语义为「全部旧启动器才迁移」） |
| **QA-11** | `store._game_profile` 反查改为「完整名称精确命中（1000+ 分）> 越长关键词越优先」，并新增游戏名归一化（去空格/中英文标点）与宽泛名 stop 词表；`detector.read_auto_rules` 经此不再把「明日方舟终末地」识别为 MAA | `read_auto_rules({"game":"明日方舟终末地"}) == BUILTIN_RULES["maaend"]`；`{"game":"明日方舟：终末地"}` → `maaend`；`{"game":"明日方舟"}` → `maa`；`_game_profile` 直接断言同结果 |
| **QA-12** | 规则清洗新增 `store._detect_names`：字符串只按 `,，;；\n` 拆分，单个值含空格也整体保留；`proc_names` / `names` / adb `pkg` 均改用该函数 | `_clean_detect_rule({"type":"proc","names":"Wuthering Waves.exe"})["names"] == ["Wuthering Waves.exe"]`；`"A.exe, Wuthering Waves.exe"` 正确拆成 2 个；win 规则 `proc_names` 与 adb `pkg` 同理；`_detect_names` 直接断言 |

> 说明：`_detect_texts` 作为历史兼容 helper 仍保留（仍按空白拆分），供旧调用/既有测试使用；v0.6 规则清洗路径已全部改用 `_detect_names`。QA-10 的「混合列表整体保留」为修复后的确定语义：若列表中仍有 `LAUNCHER.EXE` 残留，需用户编辑检测规则清理（低风险，不影响发布）。

## 三、v0.6 游戏运行检测（detector）验证说明

### 3.1 规则与匹配（自动化、确定性）
- **规则 schema**：config v4 规则清洗覆盖 `type` 别名、非法/空规则丢弃、文本分割（进程名不再按空白拆分）、`proc_class_check`、`launcher`/`cloud`、`min_client_size`、`title_optional`、`match`、`require_visible`。
- **规则来源**：MaaNTE/MaaEnd 读取脚本 `interface.json` 的 `controller[].win32`（多 Win32 controller 取并集、去重、云 controller 进 `cloud`），缺失/损坏回退内置表；ok-ww/MAA 使用内置表；按游戏名最长/精确反查；缓存按 interface mtime 失效。
- **窗口匹配**：class/title 正则大小写不敏感、`title_optional`、`match any/all`、最小客户区、最小化窗口不过滤、`require_visible`、多 controller 并集；窗口+进程双重校验（`proc_names` + `proc_path_re`）在路径不可读时降级用同名进程 PID 集合核对。
- **进程匹配**：进程名大小写不敏感；`path_re` 命中/不命中；PID/路径读不到时降级只比进程名。
- **优先级与回退**：用户自定义 `detect`（`source=user`）> interface/内置自动规则（`auto`）> 旧 `game_procs`（`legacy`）> 无规则（`none`）。
- **状态分支**：`running/reason/label` 覆盖 window/proc/adb/launcher/cloud/未运行/未配置；`launcher`/`cloud` 只影响文案不计入 `running`；ADB 默认关闭，开启时才调用 `adb_snapshot`。

### 3.2 真实检测证据（QA 独立执行，非编造）
QA 运行只读 CLI `python tools/test_detect_game.py`（读取真实 config / 脚本 interface / 当前桌面窗口与进程，**不启动、不关闭任何游戏，不写文件**），最终结果：

```
窗口快照: 88 个顶层窗口；进程快照: 158 个进程
ADB 检测: 关闭（默认）

== 明日方舟（maa）==   规则来源: auto；当前状态: 未运行
  窗口类 ^UnityWndClass$；标题 ^\s*(明日方舟|Arknights)；进程 Arknights.exe；ADB 6 个包名
== 异环（nte）==       规则来源: auto；当前状态: 运行中（窗口），hwnd=1971636
  窗口类 UnrealWindow；标题 ^\s*(异环|NTE)\s*$；进程 HTGame.exe
== 鸣潮（wuwa）==      规则来源: auto；当前状态: 未运行
  窗口类 ^UnrealWindow$；标题 ^\s*(鸣潮|Wuthering Waves)\s*$；进程 Client-Win64-Shipping.exe, Wuthering Waves.exe
== 明日方舟终末地（maaend）== 规则来源: auto；当前状态: 未运行
  窗口类 UnityWndClass；标题 Endfield；进程 Endfield.exe；ADB 5 个包名

本机正在运行的游戏: 异环
```

- 与 Lead 手工观察一致（本机当前异环正在运行）；自动化测试只断言快照/状态**契约**，不断言具体游戏一定在运行，避免依赖本机状态。
- ADB 默认关闭且本机未连接模拟器，ADB 分支仅用 mock 验证。

### 3.3 config v4 与真实配置
- 真实 `config.json` 当前为 **version 4**（由 Lead 的 GUI 验证运行时写入，mtime `14:34:13`；QA 测试全部使用临时配置，运行前后该文件未被 QA 修改）。
- 迁移表 `store.BUILTIN_GAME_PROCS`：maa→`ARKNIGHTS.EXE`、nte→`HTGAME.EXE`、wuwa→`CLIENT-WIN64-SHIPPING.EXE`、maaend→`ENDFIELD.EXE`；仅对「内置卡片且无自定义 detect，且原 `game_procs` 为空或全部为旧启动器」生效（QA-10 修复后）。

## 四、缺陷清单与状态

| ID | 级别 | 状态 | 说明 |
| --- | --- | --- | --- |
| QA-01 / QA-02 | 低 | ✅ 已修复并持续通过 | `read_version` 缺失/非字符串版本回退 `fallback_version` |
| QA-03 | 中 | ✅ 已修复并持续通过 | `save_state` 返回 bool，写失败不再静默 |
| QA-04 | 低 | ✅ 已修复并持续通过 | `version_key` 忽略 `-rc`/`+build`，`is_newer` 零补齐 |
| QA-05 | 低 | ✅ 已修复并持续通过 | `_clean_procs` 跳过非 str 项 |
| QA-06 | 低/风险 | ⏳ 保留 | 目录扫描跳过 `data/resources/config/build/dist` 等名字（设计取舍）；建议 README FAQ 说明或后续拆分扫描表，不阻塞 v0.6 |
| QA-07 | 低 | ⏳ 保留 | 自定义卡片 exe 丢失后仍以相对路径加载、无 missing 提示；建议后续排期，不阻塞 v0.6 |
| QA-08 | 信息 | ℹ️ 保留（边界） | `_portable(path==root)` → `"."`，仅异常输入触发 |
| QA-09 | 低 | ✅ 已修复并持续通过 | `_clean_icon_path` 支持 `"path.exe",0` |
| **QA-10** | 低 | ✅ **已修复并验证**（task-13） | v4 迁移不再一刀切覆盖用户自定义 `game_procs`；仅空值/全部旧启动器误配才迁移（回归断言见第二节） |
| **QA-11** | 低 | ✅ **已修复并验证**（task-13） | 游戏名反查改为精确/最长匹配；「明日方舟终末地」→ `maaend`（回归断言见第二节） |
| **QA-12** | 低/信息 | ✅ **已修复并验证**（task-13） | 字符串进程名/包名只按逗号/分号/换行拆分，含空格的名字保持完整（回归断言见第二节） |

## 五、未覆盖点与测试限制

1. **GUI 手工验证（Lead 集成阶段完成）**：编辑对话框「检测规则」4 个输入框的显示/保存/清空、自动检测选中启动程序后回填检测字段、`launch_game` 依据检测状态切换窗口（含最小化恢复）、状态点颜色（运行中/启动器已开/云游戏/未配置）与 1.5s 轮询缓存表现。本任务禁止启动 GUI/mainloop。
2. **真实游戏运行态**：本机当前仅**异环**在运行；明日方舟/鸣潮/终末地"运行中"的窗口/进程匹配只做了规则结构与真实快照 smoke，未在实际启动游戏时验证。**模拟器（MAA/ADB 模式）与云游戏窗口需 Lead 手工验证**（ADB 默认关闭且本机未连接模拟器）。
3. **会启动/聚焦进程的函数**：`launch_exe` / `focus_window` / `bring_to_front` 未测（约束要求不启动进程/不影响用户 Hub）；`adb_snapshot` 的真实 adb 调用未测（仅 mock）。
4. **联网函数**：`http_get` / `check_latest` 等未测。
5. **真实 PE 版本资源**：`file_version` 仅覆盖"空 exe 回退"路径。
6. **其它**：UI 后台线程并发、权限受限目录、异常盘符/网络盘、BOM 与自定义卡片的组合等（沿用 v0.5 报告）。
7. **版本号**：`VERSION` 当前仍为 `0.5.0`，发布任务 bump 为 `0.6.0` 后建议再跑一次本套件（预期仍 111/111 全绿）。

## 六、结论与建议

- **v0.6.0 最终回归全绿：111/111 通过、0 失败/0 错误/0 跳过、exit 0（约 1.8 s）**；可重复执行、无副作用。
- QA-10/11/12 三项修复均已用新增/更新的回归断言验证；QA-01~05、QA-09 无回归；QA-06/07/08 保留为低风险/设计边界项，不影响 v0.6 发布。
- 真实检测证据：异环被正确识别为「运行中（窗口）」，其余三款未运行、规则来源均为 auto，与 Lead 手工观察一致。
- 发布前建议：① Lead 完成 4 款游戏/模拟器/云游戏与检测规则编辑的 GUI 手工验证；② release 任务 bump `VERSION=0.6.0` 后重跑本套件（预期 111/111）；③ CI 增加 Windows runner 执行 `python tools/regression_test.py`（无需网络）。

## 附录：证据与约束遵守

- 真实检测证据由 `python tools/test_detect_game.py`（只读 CLI）采集，输出见 3.2；未启动任何游戏、未启动 GUI。
- QA 只修改 `tools/regression_test.py`、`docs/qa-report.md`；未修改 `gamehub/`、`README.md`、`CHANGELOG.md` 等文件；未 commit / push。
- 配置类用例全部使用临时目录 + `mock.patch` 隔离；真实 `config.json` mtime `14:34:13`（Lead GUI 验证写入 v4），QA 运行前后未变化。
- 测试不联网；v0.6 规则/匹配用例不枚举真实窗口（真实快照仅 smoke 契约），自动检测/注册表数据源在 v0.5 用例中已 mock 到临时目录。
