# All-My-Maa · 游戏脚本中心

<p align="center">
  <a href="https://github.com/Diaohesi/All-My-Maa/releases/latest"><img alt="最新版本" src="https://img.shields.io/github/v/release/Diaohesi/All-My-Maa?label=release&color=4fc3ff"></a>
  <a href="https://github.com/Diaohesi/All-My-Maa/actions/workflows/build-exe.yml"><img alt="构建状态" src="https://github.com/Diaohesi/All-My-Maa/actions/workflows/build-exe.yml/badge.svg"></a>
  <img alt="Windows" src="https://img.shields.io/badge/platform-Windows-0078D7">
  <a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/license-MIT-green"></a>
</p>

**一个窗口管理 4 款游戏、5 个脚本，按自己的顺序一键清日常。**
All-My-Maa 是 Windows 桌面启动器，负责打开脚本、启动游戏、检查更新与串行调用已配置的日常任务；
它不是脚本合集，也不会替你配置账号或任务。

**[下载最新版](https://github.com/Diaohesi/All-My-Maa/releases/latest)** ·
[全部发布](https://github.com/Diaohesi/All-My-Maa/releases) ·
[在线主页](https://diaohesi.github.io/All-My-Maa/) ·
[更新日志](CHANGELOG.md) ·
[反馈问题](https://github.com/Diaohesi/All-My-Maa/issues)

> **v0.13.3 · MaaNTE 自动开始修复**
> 修正 Win32 `INPUT` ABI（x64 结构大小为 **40 字节**），并等待本次启动的热键注册与加载就绪后再发送一次开始热键。
> 用户已确认：**关闭 MaaNTE 后，直接在 Hub 点击「开始清日常」，能够真正开始任务。**
> 这不代表所有日常项目、所有游戏或不同脚本版本都已完成实测。

![All-My-Maa 主界面](docs/screenshot.png)

## 快速开始

### 1. 下载并启动 Hub

- 到 **[Latest Release](https://github.com/Diaohesi/All-My-Maa/releases/latest)** 下载发布资产 `GameHub.exe`，放在可写的独立文件夹中运行。
- **打包版不需要安装 Python 或 Pillow。** 如果同时下载了仓库，可将 exe 放到仓库根目录，双击 [启动游戏中心.bat](启动游戏中心.bat)；批处理会优先运行 exe。
- Hub 默认请求管理员权限，Windows 弹出 UAC 时请确认来源后选择「是」。权限说明见下文。
- 游戏及脚本需自行下载安装。本仓库与发布包**不捆绑第三方脚本程序、账号或用户配置**。

### 2. 找到自己的脚本

建议把 Hub 与脚本目录放在同一父目录，例如：

```text
D:\All MAA\
├─ GameHub\                     ← Hub
├─ MAA-v6.19.0-win-x64\         ← MAA
├─ MaaNTE\                      ← 异环 MaaNTE
├─ ok-nte\                      ← 异环 ok-nte（可选）
├─ WuwaMAA\ok-ww\               ← 鸣潮 ok-ww
└─ MaaEnd-win-x86_64-v2.33.0\    ← 终末地 MaaEnd
```

Hub 默认以自身上一级目录为脚本根目录，按可执行文件名识别，目录名不必照抄。
找不到时点击「重新识别路径」，或在卡片「更多 ▾ → 编辑卡片」中手动选择脚本 exe。
脚本放在其它位置时，可在本地配置的 `root` 字段指定根目录；已选路径会记住，尽量保存为相对路径。

### 3. 先配置任务，再交给 Hub

1. 在各脚本自己的界面中完成连接、实例、日常任务与热键设置，并保存。
2. 回到 Hub「清日常」页，填写实例名 / 任务名 / MAA 配置，设置超时并保存。
3. 勾选要执行的项，用「↑ / ↓」调整顺序；先用「查看命令（dry-run）」核对计划，再点「开始选中项」。
4. 只跑一个脚本时，直接点该行「开始清日常」；运行原因与结果看行内状态和下方日志。

> [!IMPORTANT]
> **MaaNTE 不要先点「打开脚本 / 启动脚本」（`launch_script`）再清日常。**
> 配置完成后先关闭 MaaNTE，然后**直接点「开始清日常」**。
> Hub 会自己打开 MaaNTE、等就绪并触发任务；已有 MaaNTE 运行时会被保护检查拦住。

## 支持哪些游戏？

| 游戏 | 内置脚本 | 卡片 key | 脚本路径选择 |
| --- | --- | --- | --- |
| 明日方舟 | MAA | `maa` | `MAA.exe` |
| 异环 | MaaNTE | `nte` | `MaaNTE.exe` |
| 异环 | ok-nte | `oknte` | `ok-nte.exe`（需完整安装目录） |
| 鸣潮 | ok-ww | `wuwa` | `ok-ww.exe`（需完整安装目录） |
| 明日方舟：终末地 | MaaEnd | `maaend` | `MaaEnd.exe` |

- MaaNTE 与 ok-nte 是**同一款游戏的两个独立脚本**，不互相替换；ok-nte 日常默认不勾选，建议同一队列只选一个异环脚本。
- ok-ww / ok-nte 的「打开脚本」使用随包 Python 直接运行正式脚本，不只打开更新启动器；「更新」仍交给各自启动器。
- 顶部「添加游戏」可添加自己的脚本、游戏路径、链接与图标；内置卡片可编辑，但不可删除。
- 卡片支持打开 / 唤到前台、启动游戏、清日常，以及官网、GitHub、下载页与更新入口。

## 一键清日常

Hub **使用脚本里已经保存的任务**，不会替你生成任务队列。多个脚本串行执行，同一时刻只跑一项，避免争抢鼠标和前台。

### 每个脚本如何执行

| 脚本 | 运行前准备 | Hub 的执行方式 | 完成判定与边界 |
| --- | --- | --- | --- |
| **MAA** | 勾好任务队列，配置 LinkStart 热键；可填 MAA 配置名 | `--skip-startup-auto-run` 启动，等待就绪后发送 LinkStart；已运行则只发热键、不接管原进程 | 读取 GUI 日志的完成 / 出错 / 停止标记 |
| **MaaNTE** | 配好实例与启用任务、开始任务全局热键；**先关闭脚本** | 打开正常 UI → 等本次启动就绪 → **发送一次**开始热键 → 等任务结束 | 本地 HTTP `/maa/state`，不可用时回退 debug 日志；**完成后保留窗口** |
| **ok-nte** | 保存日常设置；任务名为 **`DailyRoutineTask`** | 随包 Python 执行 `main.py -t DailyRoutineTask -e` | 进程退出与日志；已知失败优先于外层结束标记，仍需检查各项报告 |
| **ok-ww** | 保存「每日任务」（`DailyTask`）设置 | 随包 Python 执行 `main.py -t DailyTask -e` | 进程退出 + 完成日志标记 |
| **MaaEnd** | 配好 MXU 实例并填实例名；**先关闭脚本** | `MaaEnd.exe --autostart --instance "<实例名>" --quit-after-run` | MXU 进程退出；退出码不能证明所有任务成功 |

默认超时：MAA / MaaNTE 120 分钟，ok-ww 90 分钟，MaaEnd 150 分钟；以行内保存的设置为准。
每项可设置 1–600 分钟超时；ok-nte 请核对该行设置。

### MaaNTE：正确启动顺序

1. **首次准备**：在 MaaNTE 内建立实例、启用日常任务，并启用「开始任务」全局热键（默认 `Ctrl+F10`）。在 Hub 对应行填写实例名并保存。
2. **关闭 MaaNTE**：包括你刚为查看配置而打开的窗口。Hub 不接管已运行的 MaaNTE，遇到运行中提示应先关闭再重试。
3. **直接开始清日常**：无需提前点击主页「打开脚本」。Hub 会以管理员权限启动 MaaNTE 正常 UI。
4. **等待就绪**：v0.13.3 不再看到窗口就立即发键，而是等待**本次启动**的「全局快捷键已注册」和「加载完成」，不复用历史日志标记。
5. **只触发一次**：就绪后发送设置中的开始热键，随后等待任务结束；不会通过反复发键“碰运气”。
6. **核对结果**：正常完成后 MaaNTE 窗口保留，方便查看报告；下次执行前仍需先关闭它。

如果实例没有「启动游戏」前置任务，请先让游戏进入可执行任务的状态。
异环的「启动游戏」按钮打开 `NTELauncher.exe`，需登录并点击「开始游戏」；**不是**先打开 MaaNTE 脚本。

**本次修复解决了什么？** Win32 `SendInput` 要求正确的 `INPUT` 联合结构布局，x64 为 40 字节；
旧结构可能让系统拒绝输入。v0.13.3 同时修正结构与发送时机，用户已确认上述流程能实际触发开始。
热键缺失、发送失败或就绪等待失败会明确报告，不能把“窗口打开”当成“任务成功”。

### 停止、超时与结果

- 「停止」与超时只结束**本次由 Hub 启动的脚本进程**；原本已运行的 MAA 只停止监控。
- MaaNTE 正常完成保留窗口；停止 / 超时则结束本次启动的 MaaNTE。
- 单项失败 / 超时不会阻断后续队列；请根据每行状态和日志定位失败项。
- 清日常会请求管理员权限，可能出现 UAC；拒绝授权会使该项失败。
- **Hub 的完成状态不是所有内部任务成功的保证。** 尤其 ok-nte 外层结束和 MaaEnd 进程退出，都应结合脚本报告核对。

> [!WARNING]
> 自动化可能违反游戏条款并带来账号风险，请自行评估。执行期间脚本可能抢占鼠标键盘、切换前台，请勿同时操作电脑。
> Hub 只负责调用与等待，不修改游戏文件、不注入游戏进程。

## 启动游戏与路径

| 游戏 | 启动方式 |
| --- | --- |
| 明日方舟 | 按配置区分 PC 客户端与模拟器；模拟器使用 ADB 启动包名 |
| 异环（两张卡片） | 打开 `NTELauncher.exe`，登录后点「开始游戏」；不直接启动可能触发 UE map 错误的 `HTGame.exe` |
| 鸣潮 | 优先直启 `Wuthering Waves.exe`，找不到时回退启动器并提示 |
| 终末地 | 优先鹰角启动器，按提示进入游戏；回退失败时手动选择路径 |

「编辑卡片 → 自动检测」会扫描注册表和常见安装目录；便携版或自定义位置可能需要手动浏览。
游戏状态综合窗口、进程与可选 ADB 判断，**「启动器已开」和「云游戏运行中」不等于本体已运行**。
误判时可在编辑卡片中填写窗口类 / 标题正则、进程名或 ADB 包名；留空使用内置规则。

<details>
<summary>高级路径说明：ok-ww / ok-nte 与本地配置</summary>

两款 PyAppify 脚本需要完整安装，不能只复制外层 exe。直接启动使用以下相对布局：

```text
<脚本目录>\data\apps\<ok-ww 或 ok-nte>\python\pythonw.exe
<脚本目录>\data\apps\<ok-ww 或 ok-nte>\working\main.py
```

工作目录为 `working`，进程按随包 Python 的**完整路径**区分；更新仍通过 `ok-ww.exe` / `ok-nte.exe`。
ok-nte 当前任务名是 `DailyRoutineTask`，不要沿用 ok-ww 的 `DailyTask`。

本地 `config.json` 保存路径、卡片、`daily.enabled`、`daily_order` 和 `settings`，不随仓库分发。
搬动目录后可重新识别；恢复默认前请先自行备份配置，再移走本地配置并重启。
不要将含个人路径或账号相关内容的配置直接上传到 Issue。

</details>

## 设置、更新与窗口行为

「设置」修改后点击**保存设置**；强调色、字体大小与刷新间隔立即生效。

| 分组 | 常用选项 |
| --- | --- |
| 外观 | 强调色；小 / 标准 / 大 / 特大字号；窗口支持缩放、最大化与页面滚动 |
| 启动器 | 启动检查更新、自动下载更新（默认关闭）、状态刷新间隔、最小化到托盘 |
| 路径 | 查看脚本根目录、重新识别、配置 Clash Verge 路径 |
| 清日常 | 默认超时、执行前命令预览、ADB 检测（默认关闭）、完成后结束脚本默认值；各脚本特殊策略优先 |
| 关于与更新 | 当前版本与权限、更新日志、软件更新、项目链接 |

**更新分两类：**「检查脚本更新」检查各游戏脚本，实际安装交给脚本自身；「检查软件更新」只更新 Hub。
Hub 自动下载默认关闭，即使开启，**安装前仍需确认**。打包版替换 exe 后重启；源码模式仅在干净 Git 仓库中
执行 `git pull --ff-only`，不满足条件或失败时回退发布页手动更新。

**最小化不等于退出：**

- 标题栏「—」遵循托盘开关：开启时到系统托盘，关闭时到任务栏。
- 标题栏「✕」**每次都先选择**「最小化到任务栏 / 最小化到托盘 / 退出 / 取消」，旧 `close_action` 不会绕过选择。
- 托盘左键单击 / 双击恢复，右键可打开主界面或退出；托盘不可用时回退任务栏。
- 隐藏到托盘后禁用托盘功能，会先恢复窗口，避免找不回来。
- 清日常中退出会先请求停止并等待；等待超过 15 秒可选择保留窗口或仅退出 Hub，后者可能留下外部脚本继续运行。

### 管理员与 UAC

Hub 默认以管理员身份运行，便于脚本截图、输入模拟以及向高权限窗口发送热键。
设置与关于窗口会显示当前权限；普通权限可能受 Windows UIPI 限制。

- **源码模式**自动请求 UAC；取消时提示并回退普通权限，可用 `--no-elevate` 或 `GAMEHUB_NO_ELEVATE=1` 跳过自提权。
- **打包版**带 `requireAdministrator` manifest；取消 UAC 不会启动，命令行参数不能绕过该 manifest。
- 清日常脚本仍单独请求管理员权限。不要把跳过 Hub 提权理解为脚本一定可在普通权限下工作。

## 问题反馈与诊断隐私

侧栏「问题反馈 / Bug」、设置页或关于窗口都可打开表单。
填写发生时间、相关功能、复现步骤、预期与实际结果，预览后复制报告或打开 GitHub Issue。
**GitHub Issue 公开可见，程序不会代你提交**；需要登录并在浏览器中确认。报告过长时会复制完整正文供粘贴。

需要日志时：

1. 先复现问题，记录时间与清日常行内提示；可选附带 Hub、系统、架构和 Python 版本诊断。
2. 主动点击**导出日志 ZIP**，选择本地保存位置。
3. **自行检查**报告和 ZIP，再在 GitHub Issue 中**手动附加**并提交；也可以只发文字反馈。

Hub 结构化日志记录启动、UAC、异常、启动结果与日常阶段，包含时间、PID 和会话关联信息。
默认位置为 `APP_DIR/logs/hub.log`（Hub 程序目录），单文件最大 **2 MB**、保留 **4 份轮转备份**；
目录不可写时回退 `%LOCALAPPDATA%/All-My-Maa/logs`。侧栏「打开日志目录」可直接定位。

> **隐私边界：** ZIP 只包含 Hub 自身日志，不打包游戏脚本日志或配置，不自动收集账号、配置或环境变量作为反馈附件。
> 导出只是生成本地文件，**不会自动上传或附加到 GitHub**。敏感字段与个人路径会脱敏，但**不保证完全匿名**；
> 异常文本、自定义输入和手动粘贴内容仍可能敏感，分享前必须检查。脚本任务报告需自行检查、另行决定是否分享。

<details>
<summary>常见排查：路径、MaaNTE 就绪、游戏状态与更新失败</summary>

- **路径缺失**：重新识别，或编辑卡片选择正确 exe；ok-ww / ok-nte 还需确认随包 Python 与 working 目录完整。
- **MaaNTE 已在运行**：先关闭，再直接开始清日常；不要先点打开脚本。
- **MaaNTE 窗口出现却未开始**：检查实例有启用任务、开始任务全局热键已开启且无冲突，并确认 Hub 权限。
  v0.13.3 等待本次启动就绪；无日志标记时明确提示 15 秒兼容宽限，部分就绪超过 30 秒会失败，等待可被停止中断。
  失败后先看提示，勿反复发热键；必要时手动开始并查看脚本报告，但 Hub 不会因此静默判成功。
- **MaaNTE 等待结束异常**：本地 HTTP 端口取 `webServerPort`（默认 12701），不可用 10 秒后回退 debug 日志；检查脚本是否仍在运行。
- **游戏运行状态不准**：确认打开的是游戏本体而非启动器；检查权限、卡片检测规则，模拟器按需开启 ADB。
- **任务 / 实例未配置**：回到对应脚本保存任务，再核对 Hub 的实例名、任务名或 MAA 配置名；dry-run 只预览，不执行任务。
- **更新失败**：检查 GitHub / API 网络访问、代理和限流情况；安装目录需可写，源码更新需干净仓库，也可直接使用发布页。

</details>

## 开发与详细文档

README 只保留当前使用方式；版本演进见 [CHANGELOG](CHANGELOG.md)，历史研究中的旧方案不代表当前行为。

- [清日常与启动链调研](docs/daily-automation-research.md)
- [游戏运行检测调研](docs/game-detection-research.md) · [游戏启动方式调研](docs/game-launch-research.md)
- [回归测试报告与覆盖边界](docs/qa-report.md)
- [开发提示词与集成规格](docs/AI_DEV_PROMPT.md)

<details>
<summary>源码运行、打包与测试</summary>

安装 Python 3.10+（加入 PATH），然后：

```bat
git clone https://github.com/Diaohesi/All-My-Maa.git GameHub
cd GameHub
python -m pip install pillow
python hub.pyw
```

也可使用 [启动游戏中心.bat](启动游戏中心.bat)，或运行 [创建桌面快捷方式.bat](创建桌面快捷方式.bat)。
本地打包使用 [tools/build_exe.bat](tools/build_exe.bat)，产物为 `dist\GameHub.exe`。
自动构建见 [发布工作流](.github/workflows/build-exe.yml)，站点部署见 [Pages 工作流](.github/workflows/pages.yml)。

```bat
python tools/regression_test.py
python tools/test_daily.py
python tools/test_ui_state.py
python tools/test_launch_spec.py
```

上述测试不能替代真实游戏任务验收；修改后还需检查相关 UI 与实际启动流程，并记录未覆盖范围。
欢迎提交 Issue / Pull Request；请勿提交本地配置、日志或个人路径。

</details>

## 致谢与声明

本仓库代码使用 [MIT License](LICENSE)。MAA、MaaNTE、ok-nte、ok-ww、MaaEnd 及其图标归各自作者所有，
本项目不包含这些脚本的程序文件。展示素材仅用于启动器界面，公开再分发前请确认授权或替换为自己的素材。
