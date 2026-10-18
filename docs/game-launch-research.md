# v0.10 调研：四脚本「启动游戏」方式（供 Hub 复用）

- 任务：shared task `task-49` —— 研究 MaaNTE、MaaEnd、ok-ww、MAA 各自如何启动对应游戏，为 GameHub「启动游戏」按钮的实现提供依据。
- 仓库：`D:\All MAA\GameHub`（GitHub: https://github.com/Diaohesi/ALL-MY-MAA ），基线 v0.9.1。
- 方法：本地源码 / 配置 / 注册表 / 二进制字符串 + GitHub 官方源码与文档（`curl -x http://127.0.0.1:7897`）。**未启动任何游戏/脚本，未重启 Hub，未修改除本文件外的任何文件，未 commit。**
- 证据强度：★★★ 配置/可读源码/官方文档/运行时数据；★★ 二进制字符串/函数符号；★ 推断（待实测）。

---

## 0. 结论速览

1. **四款脚本没有一款是「统一启动器」，各自策略不同**：
   - **ok-ww（鸣潮）**：**绕过游戏启动器**，直接启动游戏根目录的 `Wuthering Waves.exe`（不是 `launcher.exe`，也不是窗口进程 `Client-Win64-Shipping.exe`），cwd=游戏根目录，args=`-krqlv=hd`（可选 DX11），自身以管理员运行；随后等待窗口出现、尺寸稳定 2s 再连接。
   - **MaaNTE（异环）**：MXU **前置程序（preAction）** 直接 `CreateProcess` 启动 `HTGame.exe`（同样绕过 `NTELauncher.exe`），默认 cwd=exe 目录、无参数、不等待退出；该 preAction 在本机配置里默认**未启用**，且 MaaNTE 的 MXU 版本**不支持 PI pretask**。
   - **MaaEnd（终末地）**：走 **鹰角启动器 + 图像识别点击**：pretask `LaunchGamePC` → go-service 从注册表卸载项找到「鹰角启动器」→ 启动 `Launcher.exe` → 等 Qt 启动器窗口 → 跑 MaaFramework 流水线（选终末地图标、点右下角「开始游戏」）→ 等 `UnityWndClass + Endfield` 窗口。**不直接启动 `Endfield.exe`**（其流水线有专门的「前置程序直接启动导致白屏」诊断节点）。
   - **MAA（明日方舟）**：**自己不启动游戏**。PC 模式只启动用户配置的 `PcClientPath`（exe 或 `.lnk`，可带 `PcClientAddCommand`，等待 `PcClientWaitSeconds`），MaaCore 的 Win32 控制单元明确「start_game is not supported on Win32Controller」；模拟器模式启动 `EmulatorPath`（exe/快捷方式 + `EmulatorAddCommand`，等待 `EmulatorWaitSeconds`），连上 ADB 后再由「开始唤醒」任务用 `am start -n <包名>/com.u8.sdk.U8UnityContext` 启动游戏。
2. **Hub 现状（v0.9.1）**：`resolve_game_exe` 只对异环做了 HTGame 纠正；`launch_exe` 仅 `Popen([exe])`，无 args/cwd/等待/超时；`config.json` 里 wuwa 仍指向 `E:\Wuthering Waves\launcher.exe`、maaend 指向 `E:\Hypergryph Launcher\Launcher.exe`、maa 为空 → 点「启动游戏」只开启动器。
3. **推荐统一策略**：每款游戏一份 `game_launch` 规格（`exe/args/cwd/elevated/wait/fallback`），Hub 启动后**轮询 v0.6 detector** 直到命中窗口/进程（超时 120–180s），失败再降级启动器并提示「请在启动器中点开始游戏」。具体 schema 见 §4。
4. **本机实测路径全部存在**（§3.5）：`Wuthering Waves.exe`(484KB bootstrap→`Client-Win64-Shipping.exe` 170MB)、`HTGame.exe`(273MB)、`Endfield.exe`(828KB，需启动器)、`Arknights.exe`(824KB)，以及两个「鹰角启动器」卸载项（`E:\Hypergryph Launcher`、`E:\Arknights bilibili`）——**同一台机器有两个鹰角启动器，必须按游戏子目录区分**。

---

## 1. 总表

| 脚本（游戏） | 启动目标（exe / 包名） | 参数 / cwd / 权限 | 是否绕过启动器 | 等待/检测方式 | 证据（文件:行 / 字符串） | 强度 |
| --- | --- | --- | --- | --- | --- | --- |
| **ok-ww**（鸣潮） | 游戏根 `…\Wuthering Waves Game\Wuthering Waves.exe`；窗口进程 `Client-Win64-Shipping.exe` | args：`-krqlv=hd`（Game Package，可选 `-dx11 -d3d11 -force-d3d11`）；cwd=exe 目录；**管理员**（脚本自身） | ✅ 绕过 `launcher.exe` | 自绘：窗口存在且 client 尺寸 ≥100×100 稳定 2s（轮询 0.2s），再等可截图/分辨率通过；总超时 120s | `config.py:114-118`；`ok/util/process.py:359-415`；`ok/core/start_controller.py:14-25,147-207`；`configs/devices.json:3`；`src/game_launcher.py:4-7` | ★★★ |
| **MaaNTE**（异环） | `…\Client\WindowsNoEditor\HT\Binaries\Win64\HTGame.exe` | args 空；cwd 默认=exe 目录；无等待（`waitForExit=false`）；权限跟随 MXU | ✅（preAction 直启；`NTELauncher.exe` 仅作替代） | 启动后由 controller 等 `UnrealWindow` + `^\s*(异环\|NTE)\s*$` 窗口；agent 另用 `HTGame.exe` 查窗口 | `config/mxu-MaaNTE.json:141-152`；MXU `system.rs:531-634`、`utils.rs build_launch_command`；MaaNTE.exe 无 pretask 命令；`agent/utils/win32_process.py:67` | ★★★（源码/配置）+ ★（直启可行性待验证） |
| **MaaEnd**（终末地） | 鹰角启动器 `Launcher.exe` → 启动器内「开始游戏」→ `Endfield.exe` | pretask 选项：`Region=CN`、`LauncherPath=Auto`、可选分辨率/语言等；cwd=安装根；权限跟随 MXU | ❌ 必须经启动器（图像识别点击） | go-service：等启动器 `^Qt\d+QWindowIcon$` 窗口 → 流水线选终末地/点「开始游戏」/等「游戏中」→ 等 `UnityWndClass`+`Endfield` 游戏窗口 | `tasks/pretasks/LaunchGamePC.json:2-18`；`resource/pipeline/nodes.json:47015-47109`；go-service 符号/字符串；本机注册表实测 | ★★★（流程/配置）+ ★★（二进制） |
| **MAA**（明日方舟） | PC：`PcClientPath`（exe 或 `.lnk`）；模拟器：`EmulatorPath`（exe/快捷方式）→ 连 ADB 后 `am start -n <pkg>/com.u8.sdk.U8UnityContext` | PC：`PcClientAddCommand`、`PcClientWaitSeconds`(60)；模拟器：`EmulatorAddCommand`、`EmulatorWaitSeconds`(60)；PC 输入建议管理员 | PC：视用户配置（通常直启客户端；绕过启动器）；模拟器：先起模拟器，游戏由 ADB 拉起 | 启动后 `Thread.Sleep(WaitSeconds)` 再 connect；PC 按窗口标题 `明日方舟` attach；模拟器 ADB `am start` | `StartSettingsUserControlModel.cs:304-494`；`StartUpSettings.cs`；`MaaCore.dll` `start_game is not supported on Win32Controller`；`resource/config.json:46-53,77-78` | ★★★（源码）+ ★★（Core 字符串） |

---

## 2. 逐款详解

### 2.1 ok-ww（鸣潮）：直启游戏根 exe，绕过 launcher

**（1）启动哪只 exe**：`Wuthering Waves.exe`（游戏根），不是 `launcher.exe`、也不是 `Client-Win64-Shipping.exe`。

- `config.py:114-118`：
  ```python
  def calculate_pc_exe_path(running_path):
      if running_path is None:
          return _find_most_recently_run_pc_exe() or _find_pc_exe_from_registry()
      game_exe_folder = Path(running_path).parents[3]
      return str(game_exe_folder / "Wuthering Waves.exe")
  ```
  当前 `configs/devices.json` 的 `pc_full_path = E:\Wuthering Waves\Wuthering Waves Game\Client\Binaries\Win64\Client-Win64-Shipping.exe`，`parents[3]` = `…\Wuthering Waves Game` → 得到 `E:\Wuthering Waves\Wuthering Waves Game\Wuthering Waves.exe`（本机存在，484KB bootstrap）。
- 解析链（`ok/device/DeviceManager.py:799-831` `get_exe_path`）：
  1. `device.full_path`（= `devices.json.pc_full_path`）非空 → `calculate_pc_exe_path(full_path)`；
  2. 为空 → `_find_most_recently_run_pc_exe()`（`config.py:13-43`，`HKCU\…\Explorer\UserAssist\*\Count` rot-13 解码，筛 `\wuthering waves.exe`，按最后运行时间取最新）；
  3. 再退 `_find_pc_exe_from_registry()`（`config.py:46-111`，卸载表 DisplayName 含 wuthering waves/鸣潮/鳴潮，值 `InstallPath/InstallLocation/LauncherPath/DisplayIcon/UninstallString`，在其目录找 `Wuthering Waves.exe`、`Wuthering Waves Game\Wuthering Waves.exe`、父目录 `Wuthering Waves Game\Wuthering Waves.exe`）；
  4. 最后 `if path and os.path.exists(path): return path; return None` —— 不存在则「启动游戏」失败，提示「Start game failed, please start game first」。

**（2）怎么启动**（`ok/util/process.py:359-415`）：拼 `start "" /b "<exe>" <args>`，`subprocess.Popen(cmd, cwd=os.path.dirname(exe), shell=True, creationflags=CREATE_NEW_PROCESS_GROUP)`。即：
- cwd = **exe 所在目录**（`…\Wuthering Waves Game`）；
- 通过 `cmd /c start /b` 异步拉起，父进程不等待；
- 权限：ok-ww 自身以管理员运行（PyAppify profile `admin: true`；启动游戏前 `start_controller.py:183-188` 会检查 `is_admin()`，非管理员直接弹窗要求重启），游戏**继承管理员**。

**（3）参数**：`src/game_launcher.py:4-7` 每次启动读 `Basic Options → Game Package`，返回 `-krqlv=hd`（sd/hd/uhd）；`start_controller.py:193-201` 若勾选 `Launch with DX11` 追加 `-dx11 -d3d11 -force-d3d11`。

**（4）等待/检测**（`ok/core/start_controller.py`）：
- `start_device()`（178-207）：`get_exe_path → execute(path,args) → _wait_until_started_window_stable() → _wait_until_device_ready()`；
- `_wait_until_started_window_stable()`（147-176）：`hwnd_window.do_update_window_size()` 后要求 `hwnd>0 && 宽高≥100×100`，尺寸稳定 `STARTED_WINDOW_STABLE_SECONDS=2` 秒（轮询 0.2s）；
- `_wait_until_device_ready()`（128-145）：循环 `device_manager.do_refresh(True)` + `check_device_error()`（截图能拿到帧、分辨率/比例校验、分辨率过小会提示），超时 `start_timeout=120`（`config.py:180`）。
- 注意：**窗口进程不是刚启动的 exe**——`Wuthering Waves.exe` 是 bootstrap，真正窗口属于 `Client-Win64-Shipping.exe`（`windows.exe` 配置，`config.py:204`）。所以 Hub 等待目标必须是 `Client-Win64-Shipping.exe` 窗口/进程。

**（5）本机日志证据**：`working/logs/ok-script.log` 2026-10-04 00:26:53~56 记录 `hwnd changed ... E:\Wuthering Waves\…\Client-Win64-Shipping.exe UnrealWindow real:0,0,1920,1080`、`started window size stable for 2s`。

**（6）Hub 可复用策略**：
- 候选 1：`devices.json → pc_full_path` 的 `parents[3]\Wuthering Waves.exe`（无需用户重选，首选）；
- 候选 2：`game_exe` 目录（`…\Wuthering Waves Game`）直接找 `Wuthering Waves.exe`；
- 候选 3：注册表/UserAssist（Hub 已有 `find_game_candidates` 的注册表扫描）；
- 候选 4：`find_game_candidates` 用户选择；
- 启动：`Popen([exe], cwd=dirname(exe))`（Hub 不需要 `-krqlv`/DX11，保持默认即可；如要模仿可加 `-krqlv=hd`）；
- 等待：轮询 `detector` 的 `UnrealWindow + ^\s*鸣潮\s*$` 或进程 `Client-Win64-Shipping.exe`，60–120s；
- 失败：若 120s 未出现，提示 / 降级启动 `E:\Wuthering Waves\launcher.exe`（此时只能等用户在启动器点开始）。

### 2.2 MaaNTE（异环）：MXU preAction 直启 HTGame.exe

**（1）启动哪只 exe**：`HTGame.exe`（游戏本体），不是 `NTELauncher.exe`（启动器）。

本机 `config/mxu-MaaNTE.json:141-152` 的 preActions：

```json
{
  "id": "r7q827z",
  "customName": "▶️ 启动 HTGame.exe",
  "enabled": false,
  "program": "D:\\Neverness To Everness\\Client\\WindowsNoEditor\\HT\\Binaries\\Win64\\HTGame.exe",
  "args": "",
  "waitForExit": false,
  "skipIfRunning": true,
  "useCmd": false
}
```

注意：MXU **没有** MaaNTE 的 pretask 支持（`MaaNTE.exe` 中 `pretask/run_pretask` 出现 0 次，而 MaaEnd.exe 有），所以 MaaNTE 只有「preAction 启动外部程序」这一条自动启动路径。

**（2）MXU 如何执行 preAction**（MistEO/MXU 源码 `src-tauri/src/commands/system.rs:531-634` `run_action`，★★★）：

- `args` 用 `shell_words::split` 解析（保留引号）；
- `build_launch_command`（`commands/utils.rs`）：`std::process::Command::new(program)` 直接 CreateProcess，**不经过 shell / 不经过启动器**；`use_cmd=true` 时改用 `cmd.exe /c`；Windows 下 `cmd /c` 加 `CREATE_NO_WINDOW`；stdout/stderr 置空；
- cwd：有 `cwd` 用 `cwd`，否则**默认 = program 所在目录**；
- `wait_for_exit=false` → `spawn()` 后立即返回（ok，游戏自己起）；
- 前端（MaaNTE.exe 内嵌 JS）：遍历 `instance.preActions`，`enabled && program`；若 `skipIfRunning && isProcessRunning(program)` → 跳过（日志「已在运行，跳过」）；否则 `runAction(...)`，退出码非 0 只警告不中断；preAction 之后才连接 controller。

**（3）等待/检测**：MXU 不检测 preAction 结果，直接进入 controller 连接流程：按 `interface.json` 的 Win32 controller 等 `UnrealWindow` + `^\s*(异环|NTE)\s*$` 窗口（等待超时由 MXU `windowWaitTimeout` 控制，数值未定位，★）。MaaNTE 的 Python agent 自己也用 `HTGame.exe` 找窗口做分辨率自检（`agent/utils/win32_process.py:67`、`agent/main.py:450-457`），但**不做启动**。

**（4）NTELauncher 与直启的取舍**：
- 脚本实现（preAction）支持直启 `HTGame.exe`，说明作者认为可行；但该 preAction 在本机配置中**默认关闭**，实际运行环境里游戏通常由玩家手动从 `NTELauncher.exe` 启动（登录/更新由启动器负责）。
- **Hub 建议**：默认走官方启动器 `NTELauncher.exe`（处理登录/更新/公告，最稳），等待 `HTGame.exe` 或 `UnrealWindow + 异环` 窗口；提供「快速启动（直启 HTGame.exe）」选项（与 MaaNTE preAction 同款，跳过登录检查，适合已登录/记住账号时）；两者都失败再让用户手选。

**（5）Hub 可复用策略**：
- exe 解析：`game_exe`（若已是 HTGame → 用）→ 从启动器目录拼已知相对路径 `Client\WindowsNoEditor\HT\Binaries\Win64\HTGame.exe`（Hub 已有 `NTE_GAME_RELATIVE`，`store.py:304-305`）→ 受限 glob（现有实现）→ 用户选择；
- 启动：`Popen([exe], cwd=dirname(exe))`，无参数；不等待（或等待 1-2s 确认未立刻崩溃）；
- 等待：`UnrealWindow + ^\s*(异环|NTE)\s*$` 或进程 `HTGame.exe`，120–180s（UE 游戏加载慢）；
- 降级：`NTELauncher.exe`（启动器），提示用户登录/点开始。

### 2.3 MaaEnd（终末地）：启动器 + 图像识别点击（不直启游戏）

**（1）流程总览**：
`instance.tasks` 中的 `__MXU_PRETASK__LaunchGamePC`（本机「全套日常」「快速日常」均启用）
→ MXU 调 `run_pretask(program="agent/go-service", args=["--pretask","LaunchGamePC", …], cwd=安装根)`
→ go-service 的 `pretask/launchgamepc` 包执行：
1. `parseOptions`（Region/Language/显示模式/分辨率/帧率/HDR/是否应用游戏设置）；
2. `isProcessRunning`（`Endfield.exe`）与 `findWindow(gameClassRegex, gameWindowRegex)`：游戏已在跑 → 直接返回；
3. 定位启动器：`FindLauncherInstallDir`（注册表卸载项 + 区域键）+ 选项 `LaunchGamePCLauncherPath/LauncherExe` 覆盖；默认 exe 名 `Launcher.exe`；
4. `startLauncher` 启动 `Launcher.exe`（cwd 安装根）；
5. `waitWindow(launcherClassRegex="^Qt\\d+QWindowIcon$")` 等启动器窗口（`waiting for launcher window`）；
6. `runLauncherPipeline` 跑 MaaFramework 流水线：
   - `GameLauncherMain → GameLauncherSelectEndfield`：模板匹配点击左侧「终末地」图标（`resource/image/GameLauncher/EndfieldIcon.png`）；
   - `GameLauncherClickStartGame`：同时满足「黄色底 ColorMatch」+「开始游戏/開始遊戲/(?i)\bPlay\b OCR」→ 点击右下角开始游戏；
   - `GameLauncherInGame`：OCR 期望「游戏中/遊戲中/(?i)\bRunning\b」，post_delay 3000ms；
7. `waitGame`：等 `UnityWndClass` + `Endfield` 游戏窗口；
8. 返回退出码 0 → MXU 继续连接 controller → 执行任务。

**（2）证据**：
- `tasks/pretasks/LaunchGamePC.json:2-18`（pretask 绑定 `Win32-Front`，`exec=agent/go-service`，`args=["--pretask","LaunchGamePC"]`）；
- `resource/pipeline/nodes.json:47015-47109`（上述节点与 ROI/模板/OCR 期望）；
- `nodes.json:124397-124425`：节点「画面不变且大面积为白色，通常是通过前置程序直接启动游戏导致」——**说明直启 `Endfield.exe` 是已知会出问题的路径**；
- go-service 符号：`launchgamepc.{Run,parseOptions,isProcessRunning,findWindow,startLauncher,waitWindow,runLauncherPipeline,waitGame,settingRegion,launcherClassRegex,gameWindowRegex,gameClassRegex,launchers}`；字符串：`failed to start launcher`、`waiting for launcher window`、`failed to connect launcher window`、`launcher pipeline succeeded`、`Launcher.exe`、`^Qt\d+QWindowIcon$`、`UnityWndClass`、`Endfield.exe`、`Software\Hypergryph\Endfield`、`Software\Gryphline\Endfield`、`SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall`、`InstallLocation`、`uninstall_key`、`launcher_path`、`game launched`；注册表区服键 `Software\<Hypergryph\|Gryphline>\Endfield`（本机**不存在**这些区服键，说明不是本机必需路径）。
- 本机选项值（`config/mxu-MaaEnd.json`）：「全套日常」`LaunchGamePCRegion=CN`、`LaunchGamePCLauncherPath=Auto`、`GameSetting=true`、`DisplayType=Window`、`Resolution=1280x720`。

**（3）本机注册表实测（★★★，Hub 可直接复用同样的发现逻辑）**：
```
HKLM\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\33a0a629…:
  DisplayName     = 鹰角启动器
  InstallLocation = E:\Hypergryph Launcher
  DisplayIcon     = E:\Hypergryph Launcher\Launcher.exe
  UninstallString = E:\Hypergryph Launcher\Uninstall.exe
HKLM\…\Uninstall\cd5f2928…:
  DisplayName = 鹰角启动器
  InstallLocation = E:\Arknights bilibili
  DisplayIcon     = E:\Arknights bilibili\Launcher.exe
```
→ **同一台机器有两个「鹰角启动器」**（终末地、明日方舟各一个），必须按 `InstallLocation\games\<X> Game\<X>.exe` 区分；这也解释了 go-service 里「多个 Endfield.exe 目录 / 找不到启动器 / 不一致」等错误字符串。

**（4）Hub 可复用策略（按推荐度排序）**：
- **A（推荐，贴近脚本意图）**：Hub 启动鹰角启动器 `Launcher.exe`（按游戏匹配正确的 InstallLocation：其 `games\Endfield Game\Endfield.exe` 存在且目录含 `Endfield_Data`），随后等待游戏窗口（`UnityWndClass + Endfield`）最多 180s；期间提示「请在鹰角启动器中点击『开始游戏』」。Hub 不做图像识别点击（复刻成本高、易受主题/分辨率影响）。
- **B（一键少一步，风险中）**：直接启动 `E:\Hypergryph Launcher\games\Endfield Game\Endfield.exe`；MaaEnd 自己写明「直启会导致画面白屏」的场景，需在 UI 标注「若白屏请改用启动器」；仅作为「快速启动」选项。
- **C（借用 MaaEnd 的启动能力）**：Hub 直接 spawn `MaaEnd-win-x86_64-v2.33.0\agent\go-service.exe --pretask LaunchGamePC <JSON>`（cwd=MaaEnd 根）复刻脚本的启动器+点击流程——**待验证**（go-service 依赖 `maafw/` 运行库与 MXU 传入的 JSON 参数格式；不建议作为默认实现）。
- 注意：MXU 本体 `MaaEnd.exe --autostart -i "<实例>"` 的一键日常已包含该 pretask；若 Hub 的「一键清日常」已能调起 MaaEnd，则「启动游戏」按钮只需覆盖「只想开游戏」的场景。

### 2.4 MAA（明日方舟）：PC 模式与模拟器模式

**（1）两种模式共用的启动实现**（`StartSettingsUserControlModel.cs:304-494`）：
- 启动目标由 `ConnectionTargetLaunchSettings(Path, AddCommand, WaitSeconds, OpenAfterMaaLaunch, …)` 描述；
- `ResolveShortcut(path, addCommand)`：若 `path` 是 `.lnk`，用 `IShellLink` 读取真实目标+参数（`GetPath/GetArguments`）；否则 `FileName=path, Arguments=addCommand`；
- `ProcessStartInfo(fileName, arguments){UseShellExecute=false}.Start()`；异常时降级 `Process.Start(path, addCommand){UseShellExecute=true}`（兼容需要 shell 的快捷方式）；若 Win32 错误 740（需要提权）→ 日志警告「Insufficient permissions」；
- 启动后 `WaitForConnectionTargetStart(WaitSeconds)`：每秒等待并写日志（`WaitForEmulator: Ns`），到时间再 connect；
- 触发条件：`OpenAfterMaaLaunch`（= `StartEmulator`/`StartPcClient` 开关）或手动点「启动模拟器/PC 客户端」测试按钮。

**（2）PC 客户端模式**（`ConnectConfig = PC`）：
- 配置键：`Gui.StartUpSettings.PcClientPath`、`PcClientAddCommand`、`PcClientWaitSeconds`、`StartPcClient`（= UI 的「启动后打开 PC 客户端」`OpenPcClientAfterLaunch`，属性别名见 `StartSettingsUserControlModel.cs:138-154`）；
- MAA **不自己发现游戏路径**：`PcClientPath` 为空时直接不启动（UI 报「客户端路径为空」）；路径可填 exe 或 `.lnk`；
- **MaaCore 明确不支持 Win32 启动游戏**：`MaaCore.dll` 字符串 `start_game is not supported on Win32Controller`（`asst::Win32Controller::start_game` 位置；★★）→ PC 模式必须外部先把客户端拉起来，MAA 只负责 `AttachWindow`（按窗口标题 `明日方舟`）和 StartUp 任务（登录/进入游戏）。
- 本机 `gui.new.json`：`PcClientPath=""`、`StartPcClient=false` → MAA 当前不会自动启动 PC 客户端；Hub 需要自己解析/让用户选择。

**（3）模拟器模式**（`ConnectConfig = MuMuEmulator12` 等）：
- 配置键：`Gui.StartUpSettings.EmulatorPath`、`EmulatorAddCommand`、`EmulatorWaitSeconds`、`StartEmulator`（= `OpenEmulatorAfterLaunch`）；
- `EmulatorPath` 可以是模拟器 exe，也可以是**快捷方式**（官方文档 `docs/zh-cn/manual/connection.md`「自动启动多开模拟器」：模拟器路径可直接选“多开N-明日方舟.lnk”，此时启动器会直接打开游戏）；
- `EmulatorAddCommand` 用于多开/直接开游戏，官方示例：
  `--instance Nougat32 --cmd launchApp --package "com.hypergryph.arknights"`（蓝叠）；
- 启动模拟器并等待 `EmulatorWaitSeconds` 后 connect ADB；随后「开始唤醒」任务在 `start_game_enabled=true` 时执行（`resource/config.json:46-53,77-78`）：
  ```
  start: [Adb] -s [AdbSerial] shell am start -n [PackageName]/com.u8.sdk.U8UnityContext
  stop:  [Adb] -s [AdbSerial] shell am force-stop [PackageName]
  ```
  `PackageName` 按区服：`com.hypergryph.arknights` / `.bilibili` / `com.YoStarEN/JP/KR.Arknights` / `tw.txwy.and.arknights`。
- 本机 MAA 配置：`ConnectConfig=MuMuEmulator12`、`AdbPath=E:\MuMuPlayer-12.0\nx_device\12.0\shell\.\adb.exe`、`Address=127.0.0.1:16384`、`StartEmulator=false`、`EmulatorPath=C:\Users\he146\Desktop\明日方舟.lnk`——**但本机该 .lnk 与 MuMu 目录均已不存在**（实测），属陈旧配置，Hub 必须校验存在性。

**（4）Hub 可复用策略**：
- 先读 MAA 的 `gui.new.json`（新格式；回退 `gui.json` 旧格式）判断当前模式：
  - `Configurations.<当前配置>.Gui.ConnectSettings.Config`（`PC` 或其他）与 `Gui.ConnectSettings.IsPCConnectConfig` 等价判断；
  - PC 模式：`StartUpSettings.PcClientPath` 非空且存在 → Hub 直接 `Popen/ShellExecute` 它（支持 `.lnk`）；否则用候选解析（HG 启动器 InstallLocation 下 `games\Arknights Game\Arknights.exe`）或让用户选；等待窗口 `明日方舟`（类 `UnityWndClass`）60–120s。
  - 模拟器模式：若 ADB 可用且设备已连接 → Hub 直接 `adb -s <serial> shell am start -n <pkg>/<activity>`（包名从 MAA 配置 `RuntimeSettings.ClientType` 映射，或复用 Hub detect 规则的 `adb_pkg`）；否则启动 `EmulatorPath`（含 `.lnk`）→ 等 `EmulatorWaitSeconds` → 再尝试 am start；失败则提示用 MAA/MuMu 手动启动。
- Hub 已有 ADB 基础能力（`detector._find_adb/_run_adb/adb_snapshot`，`detector.py:449-495`），新增一个 `am start` 封装即可。
- MAA `game_exe` 为空是合理的：应由模式决定启动目标，而不是单一 exe。

---

## 3. 本机实测路径与注册表（Hub 可直接作为默认候选）

### 3.1 游戏/启动器 exe（均存在）

| 文件 | 大小 | 说明 |
| --- | --- | --- |
| `E:\Wuthering Waves\Wuthering Waves Game\Wuthering Waves.exe` | 484,040 | 鸣潮游戏根 bootstrap（ok-ww 直启目标） |
| `E:\Wuthering Waves\Wuthering Waves Game\Client\Binaries\Win64\Client-Win64-Shipping.exe` | 169,825,048 | 鸣潮真实客户端（窗口进程） |
| `E:\Wuthering Waves\launcher.exe` | 569,544 | 鸣潮启动器（仅兜底） |
| `D:\Neverness To Everness\Client\WindowsNoEditor\HT\Binaries\Win64\HTGame.exe` | 273,224,288 | 异环游戏本体（MaaNTE preAction 目标） |
| `D:\Neverness To Everness\NTELauncher.exe` | 548,448 | 异环启动器（登录/更新，兜底） |
| `E:\Hypergryph Launcher\Launcher.exe` | 4,464,616 | 鹰角启动器（终末地） |
| `E:\Hypergryph Launcher\games\Endfield Game\Endfield.exe` | 827,960 | 终末地游戏本体 |
| `E:\Arknights bilibili\Launcher.exe` | 4,539,368 | 鹰角启动器（明日方舟 B 服） |
| `E:\Arknights bilibili\games\Arknights Game\Arknights.exe` | 823,864 | 明日方舟 PC 客户端 |

### 3.2 关键判断

- 鸣潮：**根 exe 与窗口进程不同**（bootstrap → Shipping）；等待必须用 `Client-Win64-Shipping.exe` / UnrealWindow 窗口，否则会「启动了但判定未运行」。
- 异环：`HTGame.exe` 本身就是渲染进程（273MB），窗口进程 = `HTGame.exe`（与 MaaNTE 检测一致）。
- 终末地/明日方舟：Unity 小 exe + `*_Data`，进程名 = exe 名；终末地直启有白屏风险（§2.3）。
- 两个「鹰角启动器」：必须按 `InstallLocation\games\` 下的游戏目录区分。

### 3.3 目录/注册表发现（Hub 可复用）

| 目标 | 发现方式 | 证据 |
| --- | --- | --- |
| 鸣潮游戏根 | `ok-ww devices.json → pc_full_path` 的 `parents[3]`；或 `game_exe` 目录直接找；或 UserAssist/卸载表 | `ok-ww config.py:13-118`；本机 `devices.json` |
| 异环游戏 | 启动器目录 + `Client\WindowsNoEditor\HT\Binaries\Win64\HTGame.exe` | Hub `store.py:304-305`；MaaNTE config preAction path |
| 终末地/明日方舟游戏 | 鹰角启动器 InstallLocation + `games\<X> Game\<X>.exe` | 本机注册表实测（两个卸载项）；MaaEnd go-service 同思路 |
| 鹰角启动器 | 卸载表 `DisplayName=鹰角启动器` → `InstallLocation` / `DisplayIcon` | 本机注册表实测（★★★） |
| 模拟器（MAA） | `gui.new.json → StartUpSettings.EmulatorPath`（可为 .lnk）；ADB 地址在 `Gui.ConnectSettings.Address` | 本机 MAA 配置 |
| 游戏包名（MAA 模拟器） | `RuntimeSettings.ClientType` → 包名表；Hub detect 规则 `adb_pkg` | `MAA resource/config.json:46-53`；Hub `detector.py` |

---

## 4. 统一建议 schema：`game_launch`

目标：把「启动哪只 exe、怎么起、等什么、失败怎么办」全部数据化，Hub 用同一执行器跑四款游戏。

```json
"game_launch": {
  "strategy": "exe",                  // exe | launcher | mxu_preaction | maa_pc | maa_adb
  "exe": "E:\\Wuthering Waves\\Wuthering Waves Game\\Wuthering Waves.exe",
  "args": [],                          // 可选；ok-ww 可填 ["-krqlv=hd"]
  "cwd": "",                           // 空 = exe 所在目录（与脚本一致）
  "elevated": false,                   // 游戏本体默认不要求管理员
  "elevate_on_error_740": true,        // 需要时自动 runas 重试
  "wait": {
    "timeout_s": 120,
    "poll_ms": 500,
    "any_of": [
      {"type": "win", "class_re": "^UnrealWindow$", "title_re": "^\\s*鸣潮\\s*$"},
      {"type": "proc", "names": ["Client-Win64-Shipping.exe"]}
    ],
    "fail_if": [
      {"type": "proc_exit", "within_s": 30}   // 启动后 30s 内进程退出 => 失败
    ]
  },
  "fallback": [
    {"type": "exe", "exe": "E:\\Wuthering Waves\\launcher.exe",
     "hint": "已打开游戏启动器，请在启动器中点击开始游戏"},
    {"type": "user_pick", "reason": "未找到可用启动程序或启动超时"}
  ],
  "discover": {                        // 供自动解析（Hub 已有部分实现）
    "stage1": "devices.json:pc_full_path parents[3]",
    "stage2": "exe_dir/Wuthering Waves.exe",
    "stage3": "registry/UserAssist",
    "stage4": "candidate_dialog"
  }
}
```

### 4.1 四款游戏的推荐规格（可直接实现）

| 游戏 | strategy | exe（默认解析） | args | cwd | elevated | wait（超时） | fallback |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 鸣潮 | `exe` | `…\Wuthering Waves Game\Wuthering Waves.exe` | `[]`（可选 `-krqlv=hd`） | exe 目录 | false | `UnrealWindow + ^\s*鸣潮\s*$` 或 `Client-Win64-Shipping.exe`（120s） | `launcher.exe` → 提示点开始 |
| 异环 | `exe` | `…\HT\Binaries\Win64\HTGame.exe` | `[]` | exe 目录 | false | `UnrealWindow + ^\s*(异环\|NTE)\s*$` 或 `HTGame.exe`（180s） | `NTELauncher.exe` → 提示登录/点开始 |
| 终末地 | `launcher` | `E:\Hypergryph Launcher\Launcher.exe` | `[]` | InstallLocation | false | `UnityWndClass + Endfield`（180s，期间提示点「开始游戏」） | 直启 `Endfield.exe`（标注白屏风险）→ user_pick |
| 明日方舟（PC） | `maa_pc` | MAA `PcClientPath`；空则 HG 启动器下 `games\Arknights Game\Arknights.exe` | `[]` | exe 目录 | false | `UnityWndClass + ^\s*明日方舟` 或 `Arknights.exe`（120s） | `E:\Arknights bilibili\Launcher.exe` → 提示点开始 |
| 明日方舟（模拟器） | `maa_adb` | `adb` + serial | `shell am start -n <pkg>/com.u8.sdk.U8UnityContext` | — | false | ADB `mCurrentFocus` 包名命中（pkg 来自配置，60s） | 启动 `EmulatorPath`（可 `.lnk`）→ 提示手动开游戏 |

### 4.2 Hub 实现建议（与现有代码衔接）

1. **新增 `store.build_game_launch(app)`**（仿 `build_okww_launch`）：
   - 输入 app + 本地已知配置（ok-ww `devices.json`、MAA `gui.new.json`、注册表卸载项）；
   - 输出上面的 `game_launch` 规格（含候选链与 fallback）；结果可持久化到 `app["game_launch"]`，路径变化时重建。
2. **新增 `store.launch_game(app)`**：
   - 按 strategy 执行：`exe/launcher` 用 `Popen([exe,*args], cwd=...)`；`.lnk` 用 `os.startfile/ShellExecute`；`maa_adb` 调 `detector` 的 adb 封装；
   - 返回 `(ok, error, spec)`；
   - 记录启动时间/PID（用于 `fail_if proc_exit`）。
3. **新增等待器 `store.wait_game_launched(app, spec)`**：
   - 复用 `detector.snapshot_windows()/snapshot_processes()/detect_game_state()`；每 `poll_ms` 轮询；
   - 命中 → 返回 True；超时/进程提前退出 → False + 原因；
   - 超时后可自动执行 `fallback[0]`（启动器），并 toast 提示用户手动点「开始游戏」。
4. **UI（`ui.launch_game`，当前 `ui.py:2531-2596`）**：
   - 已运行 → 聚焦（现有逻辑保留）；
   - 未运行 → 取规格 → 启动 → toast「正在启动…」→ 后台等待，成功 toast「已启动」，失败按 fallback/候选对话框；
   - 「自动检测」按钮（编辑卡片里的 `_auto_detect_game`）可以改为调用 `build_game_launch` 的 discover 链，优先给出游戏本体而不是启动器（当前 `GAME_EXE_HINTS` 里 wuwa 第二项是 `launcher.exe`，需要调整权重）。
5. **不要做的事情**：
   - 不要为了「像脚本」而给游戏加 `start "" /b`（Hub 用 `Popen` 即可，避免 cmd 转义问题）；
   - 不要默认提权启动游戏（脚本提权是为了脚本自身输入/截图；游戏本体非必要，且会触发 UAC 每次弹窗）；
   - 不要在 MaaEnd 路径下未经确认直启 `Endfield.exe`（白屏风险）；
   - 不要在 MAA 模拟器模式硬编码 `am start` 而不检查 adb/serial/包名（不同区服包名不同）。

---

## 5. 边界与风险

| 场景 | 说明 | Hub 处理 |
| --- | --- | --- |
| **模拟器内游戏**（MAA 模拟器 / MaaEnd ADB/CloudADB） | Windows 侧没有游戏窗口/进程；只能 ADB 或模拟器窗口 | MAA：`am start` + ADB 焦点检测；MaaEnd：交给 MaaEnd pretask/ADB controller；Hub 只负责启动模拟器/提示 |
| **云游戏**（MaaNTE CloudGame、MaaEnd CloudADB） | 本地无游戏 exe，只有云客户端窗口 | 不提供「启动游戏」直启；提示使用对应脚本/云客户端 |
| **需要启动器登录/更新** | 异环/终末地/明日方舟的启动器负责登录、更新、防沉迷/公告；直启游戏可能跳过登录或白屏 | 默认「启动器优先」：异环 `NTELauncher`、终末地 `Launcher.exe`、明日方舟 HG 启动器；把直启作为「快速启动」选项并标注风险 |
| **同一机器多个启动器** | 本机 2 个「鹰角启动器」（终末地/明日方舟）；名字完全相同 | 按 `InstallLocation\games\<X> Game\<X>.exe` 匹配游戏；找不到就候选对话框 |
| **陈旧配置** | MAA `EmulatorPath` 指向已删除的 `明日方舟.lnk`，MuMu 路径不存在 | 启动前 `os.path.isfile` 校验；失败回退候选/提示重新配置 |
| **权限/反作弊** | 鸣潮/异环/终末地/明日方舟均有反作弊；脚本自身需管理员（尤其 ok-ww/MXU Win32 controller）；游戏本体一般不需要管理员 | 游戏不提权；若 exe 报 740 再 runas；脚本保持原有提权逻辑（v0.7 报告） |
| **进程名 ≠ 启动 exe** | 鸣潮 bootstrap `Wuthering Waves.exe` → 窗口进程 `Client-Win64-Shipping.exe` | wait 规则同时支持「启动 exe 进程」与「窗口进程/窗口」，不能只等启动进程 |
| **启动但未到可交互界面** | 游戏窗口出现 ≠ 登录完成/进入大厅；脚本自己的连接/任务会继续等 | Hub 的「已启动」以窗口出现为准；是否可操作交给脚本判断 |
| **单实例/多开** | 鸣潮/异环/终末地一般单实例；MAA 模拟器可多开 | 启动前查正在运行状态（v0.6 detector）；多开场景不再自动启动 |
| **Steam/Epic/其它渠道** | 本机无此类安装；脚本也不支持 | 候选对话框 + 用户自选，不硬编码 |

---

## 6. 证据索引

### ok-ww（`D:\All MAA\WuwaMAA\ok-ww\data\apps\ok-ww\working\`）

| 证据 | 内容 |
| --- | --- |
| `config.py:114-118` | `calculate_pc_exe_path`：`parents[3]/Wuthering Waves.exe` |
| `config.py:13-43` | `_find_most_recently_run_pc_exe`（UserAssist rot-13） |
| `config.py:46-111` | `_find_pc_exe_from_registry`（卸载表 + 候选路径） |
| `config.py:197-212` | `windows` 配置：`exe=Client-Win64-Shipping.exe`、`hwnd_class=UnrealWindow` |
| `ok/util/process.py:359-415` | `_build_windows_start_command`（`start "" /b`）、`execute`（cwd=exe 目录、shell=True、CREATE_NEW_PROCESS_GROUP） |
| `ok/core/start_controller.py:14-25` | `STARTED_WINDOW_MIN_SIZE=(100,100)`、`STABLE_SECONDS=2`、`start_timeout`、`start_exe/start_method` |
| `ok/core/start_controller.py:128-207` | `_wait_until_device_ready` / `_wait_until_started_window_stable` / `start_device`（admin 检查、execute、等待） |
| `ok/device/DeviceManager.py:799-831` | `get_exe_path`（calculate → existence 校验） |
| `ok/device/DeviceManager.py:126-130` | `stop_hwnd`（kill 游戏 exe） |
| `src/game_launcher.py:4-7` | `-krqlv=<Game Package>` |
| `configs/devices.json:1-8` | `pc_full_path` 实测值、`selected_hwnd`、`interaction` |
| `working/logs/ok-script.log` | 2026-10-04 00:26:53~56 窗口/尺寸稳定日志 |

### MaaNTE / MXU

| 证据 | 内容 |
| --- | --- |
| `MaaNTE/config/mxu-MaaNTE.json:141-152` | preAction：`program=...\HTGame.exe`、`args=""`、`waitForExit=false`、`skipIfRunning=true`、`enabled=false` |
| `MaaNTE/agent/utils/win32_process.py:67` | `DEFAULT_GAME_PROCESS_NAME = "HTGame.exe"` |
| `MaaNTE/agent/main.py:450-457` | 用 `HTGame.exe` 找窗口做分辨率自检（不启动） |
| `MaaNTE/interface.json:20-71` | Win32 controller 规则（`UnrealWindow` + `异环/NTE`） |
| MXU `src-tauri/src/commands/system.rs:531-634` | `run_action`：CreateProcess、args shell_words、cwd 默认程序目录、wait_for_exit |
| MXU `src-tauri/src/commands/utils.rs` | `build_launch_command`（可选 `cmd /c`、CREATE_NO_WINDOW、stdio null） |
| MaaNTE/MaaEnd.exe 内嵌 JS | 前端 preAction：`enabled && program` → `skipIfRunning && is_process_running` → `runAction`；MaaEnd 额外支持 `run_pretask`（MaaNTE 无） |

### MaaEnd（`D:\All MAA\MaaEnd-win-x86_64-v2.33.0\`）

| 证据 | 内容 |
| --- | --- |
| `tasks/pretasks/LaunchGamePC.json:2-18` | pretask `exec=agent/go-service`、`args=["--pretask","LaunchGamePC"]`、绑定 `Win32-Front`；option 列表（Region/LauncherPath/LauncherExe/GameSetting…） |
| `tasks/preset/DailyFull.json:115`、`QuickDaily.json:76` | 预设含 `LaunchGamePC` |
| `resource/pipeline/nodes.json:47015-47109` | `GameLauncher*` 流水线节点（模板点终末地图标、ColorMatch+OCR 点开始游戏、OCR 等「游戏中」） |
| `resource/pipeline/nodes.json:124397-124425` | 「直启导致白屏」诊断节点 |
| `agent/go-service.exe` 符号/字符串 | `launchgamepc.{Run,parseOptions,isProcessRunning,findWindow,startLauncher,waitWindow,runLauncherPipeline,waitGame,launcherClassRegex,gameWindowRegex,gameClassRegex}`；`failed to start launcher`、`waiting for launcher window`、`failed to connect launcher window`、`launcher pipeline succeeded`、`Launcher.exe`、`^Qt\d+QWindowIcon$`、`UnityWndClass`、`Endfield.exe`、`SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall`、`InstallLocation`、`uninstall_key`、`launcher_path`、`game launched`、`Software\Hypergryph\Endfield`、`Software\Gryphline\Endfield` |
| `config/mxu-MaaEnd.json` | 实例「全套日常」`__MXU_PRETASK__LaunchGamePC` 启用，`Region=CN`、`LauncherPath=Auto`、`Resolution=1280x720` 等 |
| 本机注册表 | 2 个「鹰角启动器」卸载项及 InstallLocation/DisplayIcon（见 §2.3(3)） |

### MAA（`D:\All MAA\MAA-v5.1.0-win-x64\`）

| 证据 | 内容 |
| --- | --- |
| `config/gui.new.json` | `Gui.StartUpSettings.{PcClientPath="",PcClientAddCommand="",PcClientWaitSeconds=60,StartPcClient=false,EmulatorPath="C:\Users\he146\Desktop\明日方舟.lnk",EmulatorAddCommand="",EmulatorWaitSeconds=60,StartEmulator=false}`；`Gui.ConnectSettings.{Config=MuMuEmulator12,AdbPath,Address}`；`Gui.RuntimeSettings.{ClientType=Bilibili,StartGame=true}` |
| `config/gui.json.old` | 旧格式 `Start.*` / `Connect.*`（`127.0.0.1:16384`、`AddressHistory`） |
| `resource/config.json:46-53` | 六区服包名表 |
| `resource/config.json:77-78` | `am start -n [PackageName]/com.u8.sdk.U8UnityContext`、`am force-stop [PackageName]` |
| `MaaCore.dll` 字符串 | `asst::Win32Controller::start_game` 不支持：`start_game is not supported on Win32Controller`；`asst::MaaFwAdbController::start_game`（`Invalid client_type`）；`asst::Controller::start_game/stop_game` |
| `MAA.dll` 字符串 | `PcClientPath`、`PcClientAddCommand`、`PcClientWaitSeconds`、`StartPcClient`、`EmulatorPath`、`EmulatorAddCommand`、`EmulatorWaitSeconds`、`StartEmulator`、`OpenPcClientAfterLaunch`、`OpenEmulatorAfterLaunch`、`WaitForPcClient`、`WaitForEmulator`、`SelectPcClientTip`、`客户端路径`、`附加命令用于指定模拟器启动参数`、`模拟器路径` |
| GitHub `dev-v2` `src/MaaWpfGui/ViewModels/UserControl/Settings/StartSettingsUserControlModel.cs:304-494` | `.lnk` 解析（IShellLink）、`Process.Start(UseShellExecute=false)`、shell 回退、740 权限、`WaitForConnectionTargetStart` |
| GitHub `dev-v2` `src/MaaWpfGui/Configuration/Single/Settings/StartUpSettings.cs` | 配置字段定义 |
| 官方文档 `docs/zh-cn/manual/connection.md` | 「通过附加命令启动」「通过模拟器的快捷方式启动」（`--cmd launchApp --package …`、多开 .lnk） |

### Hub 现状（只读）

| 证据 | 内容 |
| --- | --- |
| `gamehub/store.py:274-277` | `proc_names_for_exe`（取 basename 大写） |
| `gamehub/store.py:282-331` | `GAME_KEYWORDS`/`GAME_EXE_HINTS`/`GAME_VENDOR_HINTS`/噪声词 |
| `gamehub/store.py:632-745` | `find_game_candidates`（注册表 + 常见目录，1.8s 预算） |
| `gamehub/store.py:747-819` | `resolve_game_exe`：**仅异环**做 HTGame 纠正，其它游戏原样返回 |
| `gamehub/store.py:1583-1616` | `shell_launch`/`launch_exe`（无 args/cwd/wait） |
| `gamehub/ui.py:2531-2596` | `launch_game`：检测→解析→候选对话框→`launch_exe`（无等待/超时/降级） |
| `gamehub/detector.py:440-514` | ADB 基础能力（`set_adb_enabled/_find_adb/_run_adb/adb_snapshot`） |

---

## 7. 复现/核对命令（只读）

```powershell
# ok-ww 启动链
Select-String -Path 'D:\All MAA\WuwaMAA\ok-ww\data\apps\ok-ww\working\config.py' -Pattern 'calculate_pc_exe_path','_find_pc_exe_from_registry'
Select-String -Path 'D:\All MAA\WuwaMAA\ok-ww\data\apps\ok-ww\working\ok\util\process.py' -Pattern 'start "" /b','def execute'
Select-String -Path 'D:\All MAA\WuwaMAA\ok-ww\data\apps\ok-ww\working\ok\core\start_controller.py' -Pattern 'STARTED_WINDOW_MIN_SIZE','_wait_until_started_window_stable','requires admin'
Get-Content 'D:\All MAA\WuwaMAA\ok-ww\data\apps\ok-ww\working\configs\devices.json'

# 异环 preAction
python -c "import json;d=json.load(open(r'D:\All MAA\MaaNTE\config\mxu-MaaNTE.json',encoding='utf-8'));print(json.dumps(d['instances'][0].get('preActions'),ensure_ascii=False,indent=1))"

# 终末地 pretask + 启动器流水线
python -c "import json;d=json.load(open(r'D:\All MAA\MaaEnd-win-x86_64-v2.33.0\tasks\pretasks\LaunchGamePC.json',encoding='utf-8'));print(json.dumps(d['pretask'],ensure_ascii=False,indent=1))"
Select-String -Path 'D:\All MAA\MaaEnd-win-x86_64-v2.33.0\resource\pipeline\nodes.json' -Pattern 'GameLauncherMain','GameLauncherClickStartGame'

# MAA PC/模拟器启动配置
python -c "import json;d=json.load(open(r'D:\All MAA\MAA-v5.1.0-win-x64\config\gui.new.json',encoding='utf-8'));c=d['Configurations'][d['Current']]['Gui'];print(json.dumps(c['StartUpSettings'],ensure_ascii=False,indent=1));print(json.dumps(c['ConnectSettings'],ensure_ascii=False)[:600])"

# 本机鹰角启动器（注册表）
Get-ChildItem 'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall' |
  ForEach-Object { Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue } |
  Where-Object { $_.DisplayName -match '鹰角|Hypergryph|Endfield' } |
  Select-Object DisplayName,InstallLocation,DisplayIcon,UninstallString | Format-List

# 四款游戏/启动器 exe 是否存在
'Wuthering Waves.exe / HTGame.exe / Endfield.exe / Arknights.exe' | ForEach-Object { ... }  # 见 §3.1 清单
```

---

## 8. 待验证项

1. `Wuthering Waves.exe` 直启是否总能成功（不依赖 `launcher.exe` 的登录态）：ok-ww 源码如此实现，但本报告未实跑；若失败，Hub fallback 到 `launcher.exe` 并提示。
2. `HTGame.exe` 直启是否需要先登录（`NTELauncher.exe`）：MaaNTE preAction 支持直启但本机配置未启用；Hub 建议默认启动器优先。
3. MaaEnd 启动器流水线中「开始游戏」按钮的 OCR 语言覆盖（简中/繁中/EN），Hub 不复制该逻辑，仅等待窗口。
4. Hub 通过 go-service 直接跑 `--pretask LaunchGamePC` 的可行性（依赖 `maafw` 与 JSON 参数格式）。
5. MAA PC 模式 `PcClientPath` 用户实际填的是 `Arknights.exe` 还是启动器快捷方式（本机为空，无法确认）。
6. 四款游戏在「已登录/已更新」状态下直启与经启动器启动的稳定性差异，建议 Hub 上线前各实测一次。

---

*报告完。结论均可用 §6 证据索引与 §7 命令复核；标注 ★ 的为推断，需一次真实启动验证。*
