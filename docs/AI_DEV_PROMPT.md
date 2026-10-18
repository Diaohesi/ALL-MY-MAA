# All‑My‑Maa 项目「从零复刻」提示词套件

> 用途：把本项目的目标、架构、功能规格、集成细节、UI 规范、测试与发布流程、踩坑经验，整理成可直接交给另一个 AI（或 AI 团队）的提示词集合。
>
> 使用方式：把 **§0 总控提示词** 作为系统/首条消息，然后按 **§3 阶段提示词** 逐个阶段发给 AI；每阶段结束要求它自测并输出证据，再进入下一阶段。
>
> 项目名、图标、品牌可替换；文中路径/命令是「参考实现」，AI 应写成可配置/自动发现，不要硬编码。

---

## §0 总控提示词（直接复制）

```
你是一名资深 Windows 桌面应用工程师，同时具备 Python/tkinter、Win32 API、进程/窗口检测、GUI 自动化、GitHub Actions 与发布工程经验。请从零开发一个名为「All-My-Maa · 游戏脚本中心」的 Windows 桌面启动器（类似项目：https://github.com/Diaohesi/All-My-Maa）。

【项目目标】
一个窗口管理多款游戏脚本（至少 4 款）：
- 一键启动/唤出脚本软件；
- 一键启动/唤出对应游戏（按各脚本自身的启动方式）；
- 准确判断脚本/游戏是否在运行；
- 一键清日常（打开脚本并按玩家预设任务执行），支持勾选游戏、按玩家顺序串行执行、每个游戏独立状态；
- 可视化添加自定义游戏/脚本；
- 常规软件能力：设置、关于、检查脚本更新、Hub 自动检查/下载/更新、小工具；
- 深色、圆润、淡紫渐变风格 UI，支持自由缩放窗口、字体大小调节、自定义标题栏；
- 配套单元/回归测试、GitHub Pages 主页、GitHub Actions 自动构建 exe 与 Release 发布。

【硬性约束】
1. 技术栈：Python 3.10+（推荐 3.12/3.13）、tkinter（标准库）、Pillow；不引入重量级新依赖；Windows 10/11。
2. 所有路径必须可移植：配置里尽量存相对路径；换机器/换盘符可自动识别或重新配置。
3. 不修改用户脚本/游戏的安装文件；不绕过反作弊；自动化操作需提示账号风险并由用户确认。
4. 不自动下载/安装游戏；不静默执行清日常；不静默重启/覆盖程序。
5. 单实例运行；重复启动应唤出已有窗口。
6. 代码需模块化：store（配置/路径/更新/进程）、detector（游戏运行检测）、daily（清日常/队列）、launch（脚本/游戏启动）、ui（界面）、theme（设计令牌）、render（旧版图片渲染兼容）。
7. 必须提供可重复的回归测试（unittest、无网络、无 GUI 主循环、不启动真实游戏/脚本）。
8. 中文界面，UTF-8 无 BOM；Windows 下禁止用 PowerShell 的 Get-Content/Set-Content 重写中文 UTF-8 文件（会乱码），用 Python 或编辑器工具。
9. 先给设计与目录结构，再分阶段实现；每个阶段结束输出：改动文件、验证命令与结果、风险、下一步。
10. 发布流程：版本号语义化；打 tag 触发 GitHub Actions 构建 Windows exe；GitHub Pages 用 docs/ 目录部署；Release 附件含 exe + 源码 zip。

【参考实现版本】v0.10.1；界面：左侧 232px 侧边栏（主页/清日常/设置 + 小工具 + 关于与更新），内容区按钮式布局，圆角 16/13/10，默认强调色淡紫 #b98bff，自绘渐变标题栏（最小化/最大化/还原/关闭），支持 8 向缩放。
【参考配置】config.json version 4，含 apps（内置 4 + 自定义）、detect/detect_custom、daily、daily_order、settings、clash、root。
【参考质量】228 条回归测试；GitHub Actions Build Windows exe + Deploy GitHub Pages 成功；Release 资产 GameHub.exe + All-My-Maa-vX.Y.Z.zip。

请先输出：
A. 你对需求的理解与假设；
B. 目录结构与模块职责；
C. 分阶段开发计划（每阶段可验收）；
D. 需要我确认的问题（最多 5 个）。
确认后再按§3阶段提示词逐阶段实现，不要一次写完所有代码。
```

---

## §1 项目规格摘要（可单独发给 AI 作为上下文）

### 1.1 目标用户与场景

- 用户电脑上装了多个游戏脚本（明日方舟 MAA、异环 MaaNTE、鸣潮 ok-ww、终末地 MaaEnd 等）。
- 脚本各自的启动方式、任务配置、运行界面不同；用户希望一个 Hub 统一启动、查看状态、清日常。
- Hub 不是脚本的替代品，而是「启动器 + 编排器 + 状态面板」。

### 1.2 核心功能清单

1. **脚本管理**：添加/编辑/删除自定义游戏；内置 4 款；图标、官网、GitHub、更新地址、下载页、强调色。
2. **脚本启动**：未运行→启动；已运行→聚焦窗口；启动器/真实脚本分离（如 ok-ww 的 PyAppify 启动器 vs working/main.py）。
3. **游戏启动**：按脚本自身方式启动游戏本体/启动器；等待窗口/进程；失败回退；已运行→聚焦。
4. **运行状态**：复用脚本自身的检测规则（Win32 窗口类/标题正则、进程、可选 ADB），显示脚本/游戏状态与原因。
5. **一键清日常**：单游戏 + 勾选多游戏顺序队列；打开脚本软件并触发其预设任务；每个游戏独立状态；超时/停止/失败继续；dry-run 预览命令；前置条件检查；免责声明。
6. **设置**：外观（强调色、字体大小）、启动器（启动检查更新、自动下载更新、刷新间隔、关闭行为）、路径（根目录、Clash 路径）、清日常默认值、关于与更新。
7. **Hub 自更新**：启动检查 GitHub latest；确认后下载 exe 并原子替换/重启；源码模式用 git pull；失败降级。
8. **小工具**：打开 Clash Verge、脚本目录、日志目录、检查脚本更新。
9. **关于**：版本、License、GitHub/主页/Release、更新日志（最新在上）、检查软件更新。
10. **发布与文档**：README、CHANGELOG（最新在上）、GitHub Pages 主页、Issue 模板、Actions 构建/部署。

### 1.3 已知脚本（参考实现，路径自动发现）

| 脚本 | 脚本入口 | 运行状态识别 | 清日常方式 |
|---|---|---|---|
| 明日方舟 MAA | `MAA.exe` | PC：`UnityWndClass` + 标题 `明日方舟`/`Arknights`；模拟器：ADB 包名或模拟器进程 | 启动 MAA → 发 `LinkStart` 全局热键（或开启「启动后直接运行」）；监控 `debug\gui.log`「任务已全部完成！」 |
| 异环 MaaNTE（MXU） | `MaaNTE.exe` | `UnrealWindow` + 标题 `^\s*(异环|NTE)\s*$`；进程 `HTGame.exe` | 打开 MaaNTE 正常界面 → 发送其「开始任务」全局热键（默认 `Ctrl+F10`）；日志判定结束；热键不可用则提示手动 |
| 鸣潮 ok-ww | 启动器 `ok-ww.exe`（PyAppify）；真实脚本 `data\apps\ok-ww\working\main.py` + 自带 `python\pythonw.exe` | `UnrealWindow` + 标题 `^\s*鸣潮\s*$`；窗口进程 `Client-Win64-Shipping.exe`；脚本进程按 pythonw 完整路径 | `pythonw working\main.py -t DailyTask -e`（管理员，cwd=working）；完成=进程退出 + 日志 `Successfully Executed Task, Exiting Game and App!` |
| 终末地 MaaEnd（MXU） | `MaaEnd.exe` | `UnityWndClass` + 标题 `Endfield`；进程 `Endfield.exe` | `MaaEnd.exe --autostart --instance "<实例名>" --quit-after-run`；完成=进程退出；实例需预先配置 |

> 以上均为「参考实现」，实际版本可能变化；AI 应先调研本机脚本/官方 GitHub 源码，再决定命令与检测规则。

### 1.4 游戏启动方式（按脚本自身逻辑，参考）

- **异环**：启动器 `NTELauncher.exe`（登录后用户点开始游戏）；**不要直启 `HTGame.exe`**（会报 UE map 错误）。
- **鸣潮**：直启游戏根 `...\Wuthering Waves Game\Wuthering Waves.exe`（参考参数 `-krqlv=hd`，cwd=exe 目录，不依赖 launcher），等待 `Client-Win64-Shipping.exe`/窗口；失败回退 launcher。
- **终末地**：启动鹰角启动器 `Launcher.exe`（按注册表 InstallLocation 区分），等待 `UnityWndClass+Endfield`；脚本默认不直启 `Endfield.exe`（可能白屏），直启只作快速回退并提示。
- **明日方舟**：MAA PC 模式用 `PcClientPath`（或从鹰角 InstallLocation\games\Arknights Game\Arknights.exe 解析）；模拟器模式校验 EmulatorPath/ADB，`adb shell am start -n com.hypergryph.arknights/com.u8.sdk.U8UnityContext`；MAA 本身只 attach 窗口，不负责启动游戏。
- 通用：启动后轮询检测「窗口/进程」出现，超时 120–180s；失败回退启动器或让用户手动选择；非阻塞、可取消；已运行则聚焦窗口。

---

## §2 架构、数据与质量要求

### 2.1 推荐目录结构

```
hub.pyw / main.py          # 入口：单实例、Pillow 检查、启动 UI
gamehub/
  __init__.py              # VERSION
  theme.py                 # 颜色/圆角/间距/字体/窗口尺寸/渐变令牌
  store.py                 # 配置读写、路径识别、进程、更新检查、游戏启动规格、设置清洗
  detector.py              # 窗口/进程/ADB 检测，detect_game_state()
  daily.py                 # 清日常计划/执行/队列/日志监控/热键
  ui.py                    # 主窗口/侧栏/三页/对话框/标题栏/设置/关于/更新
  render.py                # （可选）Pillow 渲染旧版卡片/背景
assets/                    # 图标、hub.ico/hub.png
tools/                     # 打包、截图、自测、回归测试
docs/                      # GitHub Pages、截图、QA/调研报告
.github/workflows/         # build-exe.yml、pages.yml
config.json                # 运行时生成（不入库）
README.md / CHANGELOG.md / LICENSE
```

### 2.2 配置 schema（version 4）

```json
{
  "version": 4,
  "clash": "",
  "root": "",
  "daily_order": ["maa", "nte", "wuwa", "maaend"],
  "settings": {
    "accent": "#b98bff",
    "font_scale": 1.0,
    "check_update_on_start": true,
    "auto_download_update": false,
    "refresh_interval": 1.5,
    "close_action": "exit",
    "clash_exe": "",
    "daily_default_timeout": 120,
    "daily_show_preview": true,
    "adb_enabled": false,
    "daily_close_after": false
  },
  "apps": {
    "wuwa": {
      "key": "wuwa", "game": "鸣潮", "script": "ok-ww", "builtin": true,
      "script_exe": "WuwaMAA/ok-ww/ok-ww.exe",
      "game_exe": "E:/Wuthering Waves/Wuthering Waves Game/Wuthering Waves.exe",
      "script_procs": ["OK-WW.EXE"],
      "game_procs": ["CLIENT-WIN64-SHIPPING.EXE"],
      "icon": "assets/wuwa.png", "site": "", "github": "", "release": "", "download": "",
      "accent": "#5ee7c7",
      "detect": {"any_of": [
        {"type": "win", "class_re": "^UnrealWindow$", "title_re": "^\\s*鸣潮\\s*$"},
        {"type": "proc", "names": ["Client-Win64-Shipping.exe"]}
      ]},
      "detect_custom": false,
      "launch": {"type": "python", "exe": "…pythonw.exe", "script": "…working/main.py", "cwd": "…working",
                 "env": {"PYTHONIOENCODING": "utf-8"}, "clear_env": ["PYTHONHOME", "PYTHONPATH"],
                 "fallback": "launcher"},
      "daily": {"enabled": true, "task": "DailyTask", "timeout_min": 90, "close_after": true}
    }
  }
}
```

要求：
- 加载时做清洗/迁移（v3→v4 等），非法字段静默回退默认；保存失败返回 bool 并提示。
- 自定义卡片的 `detect` 优先于自动读取；无规则时回退旧 `game_procs`。
- 配置相对路径基于 root 还原，移动目录后仍可用。

### 2.3 检测 schema（detector）

```json
{"any_of": [
  {"type": "win", "class_re": "…", "title_re": "…", "title_optional": false,
   "match": "all", "require_visible": false, "min_client_size": [100, 100],
   "proc_names": ["…"], "proc_path_re": "…"},
  {"type": "proc", "names": ["…"], "path_re": "…"},
  {"type": "adb", "pkg": ["…"], "activity": "…", "serial_re": "…"}
]}
```

- 一次 `EnumWindows` 快照供所有卡片复用（缓存 1s），限制窗口数/异常保护；允许最小化、同名多窗口、标题尾随空格。
- `detect_game_state(app)` 返回 running/reason/label/hwnd/source/rules；ADB 默认关闭，避免卡顿。
- 自动规则：MaaNTE/MaaEnd 读 `interface.json` controller[].win32；ok-ww/MAA 用内置表；launcher/cloud 只做文案不计运行。

### 2.4 清日常 schema（daily）

```json
{"enabled": true, "task": "DailyTask", "instance": "", "config": "",
 "timeout_min": 120, "extra_args": [], "close_after": true}
```

- 每个游戏一个 action；模式：
  - `exe`（普通命令行，如 ok-ww）
  - `mxu`（`--autostart --instance … --quit-after-run`）
  - `mxu_ui`（打开 MXU 界面 + 发开始任务热键，如异环）
  - `maa`（启动 MAA + LinkStart 热键/日志判定）
- 状态机：idle → starting → running → finished/failed/timeout/stopped/skipped。
- 队列：按 `daily_order` 串行，只执行勾选项；失败默认继续；停止后剩余项 stopped；每项独立状态，非当前项不得显示运行中。
- 完成判定：进程退出 / 日志关键字 / 窗口消失；必须有超时与取消；只结束本次启动的 pid，绝不杀用户实例。
- 前置检查：脚本/实例/任务/热键/游戏是否就绪，不满足给明确提示。
- dry-run：只输出将执行的命令/步骤，供 UI 预览与测试。

### 2.5 UI 规范（v0.10 参考）

- 窗口：默认 1180×760，最小 1000×640，可自由缩放；侧边栏 232 固定，内容区自适应、可滚动。
- 主题：深色 surface 分层；默认强调色淡紫 `#b98bff`；圆角 面板16/按钮13/输入10；字体 Microsoft YaHei UI；标题 21/页面16/名称13/正文11/辅助10，支持 0.9/1.0/1.12/1.25 字体缩放。
- 渐变：标题栏、页面标题区、主按钮、侧栏品牌区轻微渐变。
- 自定义标题栏：隐藏原生标题栏，自绘图标+标题+最小化/最大化(还原)/关闭；拖动移动、双击最大化、8 向边缘缩放；任务栏/Alt+Tab 正常；关闭遵循设置。
- 页面：
  - 主页：游戏行（图标/名称/版本/脚本+游戏状态），主按钮「打开脚本」（运行中→唤到前台），次按钮「启动游戏/清日常/更多▾」；点击行/图标也打开脚本；添加/检查更新/重新识别路径。
  - 清日常：全选/取消、↑↓排序、开始选中项、停止、dry-run、免责声明；每行勾选框+图标+独立状态+独立开始/停止+行内设置；底部日志。
  - 设置：外观（强调色/字体大小）、启动器（启动检查更新/自动下载更新/刷新间隔/关闭行为）、路径（根目录/Clash）、清日常默认值、关于与更新。
- 关于：All-My-Maa、版本、License、GitHub、项目主页、Release、更新日志（最新在上）、检查软件更新。
- 反馈：Toast、保存失败提示、网络失败提示、空状态提示；不使用阻塞式长任务（后台线程 + 主线程轮询）。

### 2.6 自动更新（self-update）

- 启动后后台检查 GitHub `/releases/latest`（可配置开关）；发现新版本弹窗（说明/下载并更新/打开发布页）。
- `frozen`（PyInstaller）：下载新 exe → 校验 → 生成 updater 脚本（等待当前 PID 退出 → 备份旧 exe → 原子替换 → 启动新 exe）。
- 源码模式：干净 git 仓库可确认后 `git pull --ff-only` 并重启；否则打开发布页/下载 zip，不覆盖本地修改。
- 安装前必须用户确认；失败保留旧版本；不静默重启。

### 2.7 质量与发布

- 测试：unittest，`tools/regression_test.py`，无网络/无 GUI/不启动游戏；覆盖配置迁移/清洗、路径识别、检测规则匹配、启动规格、daily 计划/状态机/队列/超时、设置、图标回退、更新解析/更新器脚本、纯 UI 逻辑；每个测试脚本可独立 `python tools/xxx.py` 运行（FAILURES: none / 退出码 0）。
- 构建：PyInstaller `--onefile --windowed --name GameHub --icon assets/hub.ico --add-data "assets;assets" hub.pyw`。
- CI：tag `v*` 构建 exe 并创建 Release；push main（docs/**）部署 GitHub Pages（configure-pages/upload-pages-artifact/deploy-pages）。
- 发布：Release 名称「All-My-Maa vX.Y.Z」，附件 `GameHub.exe` + `All-My-Maa-vX.Y.Z.zip`；README/CHANGELOG 版本同步；CHANGELOG 最新在上。
- 验证：repo/Release/Pages 200；Actions success；exe 能启动；打包内包含 assets 图标。

---

## §3 分阶段开发提示词

> 每阶段把对应代码块发给 AI；要求它先读当前代码/文档，再实现，最后自测并给出证据。

### 阶段 1：项目骨架 + 脚本启动/唤出

```
实现阶段 1：项目骨架与脚本启动器（不要做游戏检测/清日常/复杂 UI）。

要求：
1) 创建 Python + tkinter + Pillow 项目：hub.pyw 入口、gamehub/{__init__,theme,store,ui}.py、assets/、tools/、docs/、.github/workflows/。
2) 配置 config.json（version 4）：内置 4 款（MAA/MaaNTE/ok-ww/MaaEnd），字段见规格；加载/保存/迁移/清洗；相对路径可移植。
3) 路径自动识别：按可执行名在 root 下查找（多版本择优），支持用户浏览；脚本/游戏路径独立配置。
4) 启动脚本：普通 exe 启动；ok-ww 区分 PyAppify 启动器与真实 `pythonw working\main.py`（更新仍用启动器）；已运行→聚焦窗口；单实例互斥；启动失败提示。
5) 基础 UI：侧边栏 + 主页行（图标/名称/版本/脚本状态/打开脚本按钮/更多菜单）；添加/编辑卡片对话框。
6) 测试：路径识别、配置迁移、启动规格、单实例逻辑（mock）。
验收：python hub.pyw 启动；4 款卡片显示；打开脚本可启动/聚焦；配置可保存；测试通过。
```

### 阶段 2：游戏运行检测（复用脚本自身规则）

```
实现阶段 2：准确的游戏运行检测（复用脚本自己的检测方法）。

要求：
1) 调研 4 款脚本如何判断游戏运行：MaaNTE/MaaEnd 读 interface.json controller[].win32（class_regex/window_regex）；ok-ww 从其 config.py/ok 源码取 UnrealWindow + Client-Win64-Shipping.exe；MAA PC 用窗口标题 明日方舟/Arknights、模拟器用 ADB 包名。输出 docs/game-detection-research.md（证据+规则）。
2) 新建 gamehub/detector.py：
   - 一次 EnumWindows 快照 + 进程快照；窗口类/标题正则、进程、可选 ADB；允许最小化/同名多窗口/标题空白；缓存 1s；异常保护。
   - detect_game_state(app) → running/reason/label/hwnd/source；自定义规则优先；无规则回退 game_procs。
3) UI：卡片显示「运行中（窗口/进程/ADB）/启动器已开/云游戏运行中/未运行/未配置」；编辑卡片支持自定义检测字段。
4) 工具 tools/test_detect_game.py 只读打印四款规则/状态；回归测试覆盖匹配/优先级/回退。
验收：真实桌面能正确识别正在运行的游戏；无误报（启动器不算游戏）；测试通过。
```

### 阶段 3：一键清日常 + 顺序队列 + 勾选/独立状态

```
实现阶段 3：一键清日常。

要求：
1) 调研每款脚本自动执行方式：ok-ww `-t DailyTask -e`；MaaEnd `--autostart --instance … -q`；MAA LinkStart 热键/gui.log；异环 MaaNTE 打开 UI + 发送开始任务热键（Ctrl+F10）。输出 docs/daily-automation-research.md（命令/前置/完成判定/日志路径）。
2) gamehub/daily.py：计划（dry-run 输出命令）、执行、状态机、超时/停止、日志监控、队列；只结束本次 pid；单项失败继续；队列只执行勾选项（daily_order 排序）。
3) UI 清日常页：勾选/全选、↑↓排序、开始选中项、停止、dry-run、每行独立状态与独立开始/停止、行内设置（实例/任务/超时/额外参数）、日志、免责声明。
4) 每款前置检查：脚本/实例/任务/热键/游戏状态；不满足给明确提示；热键不可用→提示手动，不静默成功。
5) 测试：计划/状态机/超时/停止/队列/前置/日志；全部 mock，不启动真实脚本/游戏。
验收：勾选后按顺序执行；每个游戏状态独立；dry-run 命令正确；测试通过。
```

### 阶段 4：UI 重做（圆润淡紫渐变 + 自定义标题栏 + 字体大小 + 设置/关于/自动更新）

```
实现阶段 4：UI 与常规软件能力。

要求：
1) 设计令牌 theme.py：深色分层、默认强调色淡紫 #b98bff、圆角 面板16/按钮13/输入10、间距 8–24、字体 YaHei UI 与字号档、渐变令牌。
2) 自绘控件：圆角按钮 5 态（默认/hover/press/disabled/主按钮）、圆角面板/输入框；图标用 PIL+LANCZOS+ImageTk（保存引用）。
3) 自定义标题栏：隐藏原生标题栏，自绘图标+标题+最小化/最大化(还原)/关闭；拖动、双击最大化、8 向缩放（min 1000×640）；任务栏/Alt+Tab 正常；关闭遵循设置。
4) 三页：主页按钮式（打开脚本=启动/唤前台、启动游戏、清日常、更多）、清日常页（勾选/独立状态/顺序/日志）、设置页（外观/启动器/路径/清日常/关于与更新）；字体大小立即生效并持久化。
5) 关于/更新日志：版本、License、GitHub/主页/Release、更新日志纯文本渲染（最新在上）。
6) 自动更新：启动检查 latest；确认后下载 exe 并原子替换/重启；源码模式 git pull；失败降级；不静默安装。
7) 小工具：打开 Clash/脚本目录/日志目录/检查脚本更新。
8) 测试：settings/字体缩放/圆角令牌/更新解析/updater 脚本/标题栏状态纯逻辑；回归保持全绿。
验收：窗口可自由缩放、标题栏可用；三页可用；字体大小切换生效；自动更新流程有 dry-run/单元测试；截图交付。
```

### 阶段 5：游戏启动重构（按脚本方式）

```
实现阶段 5：按各脚本自身方式启动游戏。

要求：
1) 调研 docs/game-launch-research.md：ok-ww 直启 Wuthering Waves.exe（-krqlv=hd）；异环启动 NTELauncher（不要直启 HTGame，UE map 错误）；终末地启动鹰角启动器等待 Endfield；MAA PC/模拟器 ADB；统一 schema。
2) store.build_game_launch(app)：strategy/exe/args/cwd/elevated/wait/fallback/discover；launch_game_with_wait：启动→轮询窗口/进程→成功/超时回退→提示；不阻塞 UI。
3) 路径解析：从脚本配置/注册表/已知相对路径推导，保存便携路径；已运行→聚焦；失败回退启动器/手动选择。
4) 测试：四款策略/等待/超时/回退/模拟器分支；mock 不启动游戏。
验收：dry-run 命令正确；真实启动由用户验证；测试通过。
```

### 阶段 6：测试、打包、GitHub Pages、发布

```
实现阶段 6：质量与发布。

要求：
1) 整理 tools/：regression_test.py（unittest，≥200 条量级）、test_* 自测脚本、grab_hub.py 截图、build_exe.bat、verify_exe.ps1。
2) GitHub Pages：docs/index.html + site.css + 图标/截图；深色风格与 App 一致；下载 latest；页脚 License/GitHub。
3) GitHub Actions：build-exe.yml（tag 触发 PyInstaller，创建 Release 附 exe）；pages.yml（push docs 部署）。
4) README/CHANGELOG（最新在上）/LICENSE/.gitignore（config、dist/build、用户素材）；Issue 模板。
5) 发布：bump VERSION → commit → tag → 等 Actions → 更新 Release 名称/说明/源码 zip → 验证 repo/Release/Pages 200、exe 能启动、打包含 assets。
验收：全部 Actions success；Release 附件正确；Pages 可访问；回归测试全绿。
```

---

## §4 已知坑与防坑提示词

```
开发时必须注意以下坑（来自真实项目）：

1) Windows 编码：禁止用 PowerShell Get-Content/Set-Content 重写中文 UTF-8 文件（会乱码）；用 Python encoding='utf-8' 或编辑器工具。PyInstaller 打包时把 assets 加进去（--add-data "assets;assets"），运行时路径区分源码 APP_DIR 与 sys._MEIPASS。
2) 启动器 ≠ 脚本本体：ok-ww.exe 是 PyAppify 启动器/更新器，真实脚本是 working\main.py + 自带 pythonw；更新走启动器，启动走真实脚本；进程检测用 exe 完整路径。
3) 游戏启动器 ≠ 游戏本体：直启异环 HTGame.exe 会 UE map 报错，必须走 NTELauncher；鸣潮/终末地/明日方舟按各自脚本逻辑；启动后等待窗口/进程，超时回退。
4) 管理员权限：MAA/MaaNTE/MaaEnd/ok-ww 多数需要管理员；Hub 启动它们需 ShellExecuteW(runas) 或逐项 UAC；游戏本体通常不提权；权限 740 需 runas 重试或提示。
5) 检测误报：不要只靠进程名（launcher.exe/Client-Win64-Shipping.exe 通用名）；窗口类+标题正则+进程路径组合；启动器/云游戏单独处理；路径读不到不要退化为同名进程。
6) 清日常完成判定：尽量用脚本自身信号（进程退出/日志固定关键字）；没有信号就用超时+人工确认，不要静默成功；只杀自己启动的 pid，不杀用户实例。
7) GUI 自动化风险：优先用脚本官方 CLI/热键/配置；必须点击时用全局热键或窗口消息，坐标点击要固定窗口位置+DPI；提醒账号风险。
8) 单实例：命名互斥体；重复启动聚焦已有窗口（注意窗口标题变化后旧进程匹配）。
9) 便携路径：配置保存相对路径；加载时基于 root 还原；换盘符/换机器可重新识别。
10) 自动更新：exe 更新需 updater 等待退出→备份→替换→重启；源码模式 git pull 需干净仓库；确认后执行，失败不破坏旧版本。
11) 测试隔离：单测不得启动真实游戏/脚本/网络；用 mock/临时 config/临时目录；防止测试写真实 config.json。
12) 视觉：不要过密小字；圆角/间距/字重统一；深色对比；窗口缩放/滚动；字体缩放后布局不溢出。
```

---

## §5 验收清单（交给 AI 自检）

```
A. 启动与单实例：首次运行生成 config；重复启动唤出已有窗口；关闭行为符合设置。
B. 四款内置 + 自定义卡片：添加/编辑/删除/图标/版本/官网链接；相对路径可移植。
C. 脚本启动：未运行启动、已运行聚焦；ok-ww 启动真实脚本而非启动器；更新走启动器。
D. 游戏状态：四款真实运行/未运行判断正确；无误报；编辑自定义检测规则可生效。
E. 游戏启动：异环走 NTELauncher；鸣潮直启 Wuthering Waves.exe；终末地走鹰角启动器；MAA PC/模拟器分支；等待窗口/超时/回退正确。
F. 清日常：勾选/顺序/单游戏/队列；每项独立状态；dry-run 命令正确；前置检查明确；超时/停止安全；日志完成判定。
G. UI：淡紫圆润渐变；自定义标题栏拖动/最大化/缩放/关闭；三页布局；字体大小切换立即生效并持久化；1000×640 不溢出。
H. 设置：强调色/字体/检查更新/自动下载/刷新间隔/关闭行为/Clash/清日常默认值；保存并生效。
I. 关于/更新日志：版本/License/链接；更新日志最新在上；软件更新检查/下载/安装流程（mock/实机）。
J. 质量：regression_test 全绿；打包 exe 可启动；GitHub Actions Build/Pages success；Release 附件 exe+zip；README/CHANGELOG 最新在上。
K. 安全：无用户数据上传；不修改脚本/游戏安装；不绕过反作弊；自动化前免责声明。
```

---

## §6 多智能体协作提示词（可选，用于 Agent Teams）

```
你是一个项目的 Team Lead，配置 4 个 durable teammates（同一 workspace）：
- feature-dev：按任务实现代码，跑自测，不 commit/push。
- qa-tester：只写回归测试与测试报告，不修产品代码；发现缺陷交 Lead。
- docs-maintainer：README/CHANGELOG/Pages/图标文档，不改代码。
- release-engineer：构建/发布/GitHub Actions/Release/Pages，只在 Lead 批准后 push。
- （可选）detector-researcher：只做调研报告，不改代码。

流程：
1) Lead 拆任务（共享 task board，写清依赖/写作用域/验收），同一文件同一时间只给一个 agent。
2) 并行任务分派给不同文件作用域；先后依赖用 blocked_by。
3) 每个任务完成 → 汇报 Lead：改动、测试、截图/证据、风险。
4) Lead 集成验证（真实 UI/配置/回归）→ 批准 release → release-engineer 执行；发布后 Lead 刷新截图并推 docs。
5) 安全红线：不自动启动游戏/清日常、不实际下载替换 exe、不打印 token、不 force push、不删历史。
```

---

## §7 一次性短提示词（如果你只想给一句）

```
从零开发一个 Windows 游戏脚本 Hub（Python/tkinter/Pillow，项目名 All-My-Maa）：一个窗口管理 4 款游戏脚本（MAA/MaaNTE/ok-ww/MaaEnd），支持一键启动/唤出脚本与游戏、复用脚本自身规则判断游戏运行状态、一键清日常（勾选游戏、按顺序队列、每游戏独立状态、打开脚本并触发其预设任务）、可视化添加游戏、设置/关于/自动更新；UI 深色淡紫渐变、圆角、自定义标题栏、可自由缩放、字体大小可调；配置可移植；提供 unittest 回归、PyInstaller 构建、GitHub Actions exe Release 与 docs/ Pages 主页；先给设计与分阶段计划，再逐阶段实现并自测，最后按验收清单交付。
```

---

*本提示词套件基于 All-My-Maa v0.10.1 的真实开发过程整理；替换品牌/图标后即可复用。*
