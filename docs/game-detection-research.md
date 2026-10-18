# 游戏运行检测机制调研报告（四脚本逆向 / 静态分析）

- 任务：shared task `task-8` —— 研究 MaaNTE、MaaEnd、ok-ww、MAA 四款脚本软件各自如何判断「游戏是否正在运行」，为 GameHub v0.5.0 从「仅进程名」升级为「窗口类 + 标题 + 进程 + ADB」多源检测提供依据。
- 仓库：`D:\All MAA\GameHub`（GitHub: https://github.com/Diaohesi/ALL-MY-MAA ），当前版本 v0.5.0。
- 方法：纯静态分析 —— 读配置文件 / Python 源码 / 运行时日志 / 二进制字符串（ASCII + UTF-16LE），并对本机已安装的游戏目录做只读核对。**未启动任何 GUI、未启动游戏、未重启 Hub、未联网、未 commit。**
- 输出范围：仅本文件 `docs/game-detection-research.md`；其它文件只读。

### 证据强度标注约定

| 标记 | 含义 | 说明 |
| --- | --- | --- |
| ★★★ | 强 | 产品自带配置文件 / 可读源码 / 该产品自己的运行时日志，可直接引用行号或时间戳 |
| ★★ | 中 | 二进制字符串、函数符号、注册表项、文件名推断；可信但缺上下文 |
| ★ | 弱 | 基于上面证据的合理推断，需实测确认 |

---

## 0. 结论速览（TL;DR）

1. **四款脚本中三款（MaaNTE、MaaEnd、MAA）判断「游戏在运行」的第一依据都是 Win32 顶层窗口的 `类名(class_name)` + `标题(window_name)`，而不是进程名。** 进程名只作辅助/启动器已开/跳过 pre-action 用。
2. **MaaNTE 与 MaaEnd 的 GUI 都是同一套 MXU（MaaFramework 生态的通用 GUI：Tauri + React + Rust）**，检测链路完全一致：
   `interface.json` 里的 `controller[].win32.class_regex / window_regex` → MXU 调 `MaaToolkitDesktopWindowFindAll(classRegex, windowRegex)` 枚举桌面窗口 → 命中后保存 `savedDevice = { windowName, connectedProgramPath }` → 下次连自动等待同名窗口出现（`waitingForWindowNamed` / `waitingForAnyWindow`，带超时）。
3. **MAA 的 PC 客户端模式 = 按窗口标题找窗口**（运行时日志实锤：`AttachWindow: Found window "明日方舟" with HWND: "921028"`），模拟器模式 = ADB（序列号 + 包名 + `am start/force-stop`）。
4. **ok-ww 是四者中检测最严格的**：`EnumWindows` 找 `class == "UnrealWindow"` 的窗口 → 用窗口 PID 反查进程名必须是 `Client-Win64-Shipping.exe` → 再过滤可见/启用/尺寸>10px → 取面积最大者；「是否运行」= `hwnd > 0 && IsWindow(hwnd)`，**不要求标题**。
5. **Hub 当前用错了两处**（见 §1）：鸣潮、终末地都填了 `LAUNCHER.EXE`，两者规则完全相同且指向启动器而非游戏本体；异环填了 `NTELAUNCHER.EXE`（启动器）。这解释了「进程名判断不准确」。
6. 本机已静态验证：四个游戏窗口类字符串确实位于各自二进制中（`HTGame.exe`/`Client-Win64-Shipping.exe` → UTF-16 `UnrealWindow`；`Arknights`/`Endfield` 的 `UnityPlayer.dll` → UTF-16 `UnityWndClass`），与脚本配置完全吻合（§11）。

---

## 1. 基线：Hub v0.5.0 现有检测方式与问题

Hub 现在的实现（只读引用，未改动）：

| 位置 | 行为 |
| --- | --- |
| `gamehub/store.py:925-942` `snapshot_processes()` | `CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS)` 取全部进程名，`szExeFile.upper()` 存成集合 |
| `gamehub/ui.py:605-614` `_refresh()` | `names & set(app["game_procs"])` 非空 ⇒ 游戏「运行中」；每张卡片只显示 on/off |
| `gamehub/ui.py:591-594` `_game_state()` | 既无 `game_exe` 又无 `game_procs` 时显示 `unset` |
| `config.json:5-65` | 四张卡片的 `game_procs`：maa=空、nte=`NTELAUNCHER.EXE`、wuwa=`LAUNCHER.EXE`、maaend=`LAUNCHER.EXE` |

由此产生的实际缺陷：

1. **指向启动器而非游戏本体**：`NTELAUNCHER.EXE` 在游戏启动后通常不退出（或先于游戏运行），「启动器在跑」≠「游戏在跑」。
2. **`LAUNCHER.EXE` 规则撞车**：鸣潮与终末地两张卡片使用同一个进程名，任意一个启动器在跑就会让两张卡同时亮起，且任何其它软件的 `launcher.exe` 也会误报。
3. **无法识别模拟器内游戏**：MAA 走 MuMu 时，游戏是 Android 进程，Windows 侧只能看到 `MuMuPlayer.exe`；MAA 卡片又恰好是空 `game_procs`，永远 `unset`。
4. **无法识别云游戏**：MaaNTE 有云控制器、MaaEnd 有 CloudADB，云端没有本地游戏 exe。
5. **无窗口级证据**：进程名可伪造/同名，且游戏「有进程但窗口未起」「窗口在但进程被杀」等状态无法区分。

> 结论：升级方向正确 —— 学四个脚本，用「窗口类 + 标题」为主、进程名为辅、ADB 为模拟器/云补充。

---

## 2. 总表

| 脚本（游戏） | 检测方式（从上到下为优先级） | 关键特征（class / title / 进程 / 包名） | 证据 | 强度 | 可靠性 / 边界 |
| --- | --- | --- | --- | --- | --- |
| **MaaNTE**（异环 / NTE） | ① Win32 窗口（class_regex + window_regex，MXU 用 MaaToolkit 枚举桌面窗口）② 进程名 `HTGame.exe`（agent 自用）③ 云游戏窗口（独立 controller） | class `^UnrealWindow$`；title `^\s*(异环\|NTE)\s*$`（实际值 `异环  `，含 2 个尾随空格）；进程 `HTGame.exe`；云：class `Qt.*` + title `^\s*(云.*?异环)\s*$` | `MaaNTE/interface.json:20-71`；`MaaNTE/config/mxu-MaaNTE.json:9-12`；`MaaNTE/debug/2026-10-18-4.log:95-96`；`MaaNTE/agent/utils/win32_process.py:67,175-218`；`MaaNTE/MaaNTE.exe` 二进制符号 | ★★★ | 窗口未起就找不到（日志实锤「找到 Win32 窗口: 0 个」）；标题有尾随空格，必须用正则/trim；云窗口若用本地规则**不会**误判 |
| **MaaEnd**（明日方舟：终末地） | ① Win32 窗口（class UnityWndClass + title Endfield）② ADB（安卓端/云终末地）③ 进程 `Endfield.exe`（go-service 关游戏/判断）④ 启动器窗口（Qt + 鹰角启动器） | class `UnityWndClass`；title `Endfield`（CN 可能含 `终末地`）；进程 `Endfield.exe`；ADB 包名 5 个（见 §4）；启动器 class `^Qt\d+QWindowIcon$`、title `鹰角启动器` | `MaaEnd-win-x86_64-v2.33.0/interface.json:26-38,40-58`；`tasks/AndroidOpenGame.json:34-153`；`agent/go-service.exe` 符号 `launchgamepc.*`/`closegame.isEndfieldRunning` | ★★★（配置）+ ★★（二进制） | PC 端检测极稳；UnityWndClass 属通用类名，必须靠 title 收窄；安卓端无 Win32 特征，只能 ADB |
| **ok-ww**（鸣潮） | ① Win32 窗口 + PID→进程名双重校验（EnumWindows）② 进程名（`Client-Win64-Shipping.exe`）③ ADB（模拟器/手机，可选）④ 注册表/UserAssist 推断游戏 exe 路径 | class `UnrealWindow`；进程 `Client-Win64-Shipping.exe`；**不要求标题**；实测标题 `鸣潮  `；启动器 `E:\Wuthering Waves\launcher.exe`；游戏根 exe `Wuthering Waves.exe` | `ok-ww/data/apps/ok-ww/repo/config.py:197-212`；`ok/util/window.py:286-297,329-440`；`ok/device/DeviceManager.py:235-287,799-831`；`working/logs/ok-script.log`（2026-10-04 00:26:54/56）；`working/configs/devices.json` | ★★★（源码+运行日志） | 最严格；但 `Client-Win64-Shipping.exe` 是虚幻通用名，多款 UE 游戏同名，Hub 单独用会误判，需配 class 校验或路径校验 |
| **MAA**（明日方舟） | ① PC 客户端：按窗口**标题**找窗口（`AttachWindow`，UI 层 EnumWindows）② 模拟器：ADB（adb path + serial + 包名 + `am start`/`am force-stop`）③ MuMu 专用扩展（MuMuPlayerExtras + 包名取 display id） | PC：title `明日方舟`（CN，实测）；类名未用（Unity 客户端实际为 `UnityWndClass`）；进程 `Arknights.exe`。模拟器：包名 `com.hypergryph.arknights(.bilibili)` / `com.YoStarEN/JP/KR.Arknights` / `tw.txwy.and.arknights`；serial 形如 `127.0.0.1:16384`、`emulator-5554` | `MAA-v5.1.0-win-x64/resource/config.json:46-53,54-171`；`config/gui.json.old:11-32`；`debug/gui.log`（2026-02-15 03:00:37，2026-05-13 10:06:14）；`MAA.dll` / `MaaCore.dll` / `MaaToolkit.dll` 字符串 | ★★★（配置+运行日志） | PC 端不依赖类名，标题同名窗口可能有 2 个（日志实锤 `count: 2`），不能要求唯一；模拟器端必须 ADB，Win32 侧只能看模拟器进程 |

---

## 3. MaaNTE（异环 / NTE）

### 3.1 它怎么判断「游戏在运行」

MaaNTE 有**两层**检测，互相独立：

**（A）MXU 前端（MaaNTE.exe）—— 决定「连接哪个窗口」**

`interface.json` 声明了 4 个 controller（`interface.json:20-71`）：

| controller | class_regex | window_regex | 说明 |
| --- | --- | --- | --- |
| `Win32`（默认） | `UnrealWindow` | `^\s*(异环\|NTE)\s*$` | 后台截图 SendMessageWithCursorPos |
| `Win32-Front` | `UnrealWindow` | 同上 | 前台 PrintWindow + Seize |
| `Win32-Background` | `UnrealWindow` | 同上 | PrintWindow + SendMessageWithWindowPos |
| `CloudGame-Front` | `Qt.*` | `^\s*(云.*?异环)\s*$` | 云游戏窗口，FramePool |

MXU 的运行时日志（`debug/2026-10-18-4.log:95-96`）直接打印了检测过程与结果：

```
[MAA] 搜索 Win32 窗口, classRegex: UnrealWindow , windowRegex: ^\s*(异环|NTE)\s*$
[MAA] 找到 Win32 窗口: 0 个
```

底层调用是 MaaToolkit 的桌面窗口枚举（`debug/maafw.log:43`）：

```
[DBG][...][DesktopWindowWin32Finder.cpp][L13][MaaNS::ToolkitNS::DesktopWindowWin32Finder::find_all] | enter
```

在 `MaaNTE.exe` 二进制里可读到 MXU 侧实现（★）：
- 调用点：`maa_find_win32_windows`，参数 `{classRegex, windowRegex}`；失败时走 HTTP `/maa/windows?class_regex=&window_regex=`；
- 使用 `MaaToolkitDesktopWindowFindAll / GetHandle / GetClassName / GetWindowName`；
- 连接成功保存 `savedDevice.windowName`；并用 Rust 命令 `get_process_path_from_hwnd`（内部 `OpenProcess` + `QueryFullProcessImageNameW`）取窗口所属 exe，保存为 `savedDevice.connectedProgramPath`；
- 连接时若已有 `windowName` 则进入 `waitingForWindowNamed`（等待同名窗口出现），否则 `waitingForAnyWindow`（等待任意匹配 controller 的窗口），超时报 `windowWaitTimeout`；
- 选中窗口后自动附加一条 pre-action：`{program: connectedProgramPath, skipIfRunning: true}`，`skipIfRunning` 由 Rust 命令 `check_process_running`（`CreateToolhelp32Snapshot`）实现。

本机配置（`config/mxu-MaaNTE.json:9-12`）保存的正是这套结果：

```json
"savedDevice": {
  "windowName": "异环  ",
  "connectedProgramPath": "D:\\Neverness To Everness\\Client\\WindowsNoEditor\\HT\\Binaries\\Win64\\HTGame.exe"
}
```

> 注意：`windowName` 是 `"异环  "`（**两个尾随空格**），所以正则必须允许空白，或用 trim 后比较。

**（B）MaaNTE 的 Python agent —— 自己再按进程名找一次游戏窗口**

`agent/utils/win32_process.py`：

- `DEFAULT_GAME_PROCESS_NAME = "HTGame.exe"`（第 67 行）
- `get_pids_by_name()`（126-143）：Toolhelp32 快照枚举 **PID**（不是只比名字）
- `find_windows_by_process()`（175-218）：`EnumWindows` + `IsWindow/IsWindowEnabled/IsWindowVisible` + `GetWindowThreadProcessId` ∈ 上面 PID 集合 + `GetClassNameW` 匹配（`_match_class_name`，161-172，支持字符串相等或正则）+ 可选 `require_title` + client 区域 >10×10 + 记录标题/类名/尺寸
- `find_window_by_process()`（221-250）：优先 `selected_hwnd`，其次 `last_hwnd`（面积不缩小超过 10%），否则取 client 面积最大者

调用点 `agent/main.py:450-457`（连接控制器后自检分辨率）：

```python
from utils.win32_process import find_window_by_process, get_client_size
hwnd = find_window_by_process("HTGame.exe")
if hwnd is None:
    logger.warning("分辨率检测: 未找到游戏窗口 (HTGame.exe)")
```

另有硬编码标题列表（`agent/custom/action/auto_piano/maa_keyboard.py:45-48`）：

```python
WINDOW_TITLES = ["NTE  ", "异环  "]   # 之后 user32.FindWindowW(None, title)
```

### 3.2 可直接落地的规则建议（Hub）

```json
{
  "win_class": "^UnrealWindow$",
  "win_title": "^\\s*(异环|NTE)\\s*$",
  "procs": ["HTGame.exe"],
  "procs_path_re": "\\\\Client\\\\WindowsNoEditor\\\\HT\\\\Binaries\\\\Win64\\\\HTGame\\.exe$",
  "launcher_procs": ["NTELauncher.exe"],
  "cloud": { "win_class": "^Qt.*$", "win_title": "^\\s*云.*?异环\\s*$" }
}
```

- **主判定用窗口**（class+title），命中即「游戏运行中」；`HTGame.exe` 作为进程兜底（窗口枚举被权限挡住时）。
- class 用 `^UnrealWindow$` 精确匹配（本机 `HTGame.exe` 内含 UTF-16 `UnrealWindow`，§11）。
- title 必须用正则搜索并容忍尾部空格（`^\s*(异环|NTE)\s*$`）。
- **启动器 `NTELauncher.exe` 只做「启动器已打开」提示**，不要计入「游戏运行」。
- **云游戏不要混进本地规则**：`Qt.*` + `云.*异环` 是另一套窗口，Hub 若要支持，请单列为 `state = "cloud"`，不要与本地判定共用 `any_of`，否则会把云客户端算成本地游戏。

### 3.3 可靠性与边界

- 窗口枚举基于 MaaToolkit `DesktopWindowWin32Finder`（推断：`EnumWindows` + `IsWindowVisible`，仅顶层可见窗口；`MaaToolkit.dll` 中可见 `IsWindowVisible` 符号）；游戏最小化时窗口仍存在（`IsWindow`），但不可见 ⇒ 若 Hub 要求 `require_visible` 会产生「最小化就 off」的抖动。**建议：允许最小化，不要求 visible。**
- 云窗口 class `Qt.*` 非常宽泛（很多 Qt 程序都叫 `Qt5158QWindowIcon` 之类），但 title 正则足够窄，误判概率低；反过来也意味着 **Hub 不能只用 class 判断云游戏**。
- 「窗口存在」只代表客户端已启动（可能还停在登录/更新界面），不代表已进对局 —— 这正是 Hub 需要的「游戏已启动」语义，报告不再扩展。

---

## 4. MaaEnd（明日方舟：终末地）

### 4.1 它怎么判断「游戏在运行」

MaaEnd 有 9 个 controller（`interface.json:25-142`），Windows 相关的是：

| controller | 类型 | 特征 | 证据 |
| --- | --- | --- | --- |
| `Win32-Front` | Win32 | `class_regex: "UnityWndClass"`，`window_regex: "Endfield"` | `interface.json:26-38` |
| `ADB` | Adb | 安卓模拟器/真机，附加 `./resource_adb` | `interface.json:40-48` |
| `CloudADB` | Adb | 云终末地（安卓 ADB），附加 `./resource_cloud_adb` | `interface.json:49-58` |
| `PlayCover` | PlayCover | macOS 侧载 | `interface.json:60-69` |
| `Linux-*` / `MacOS-*` | Linux/MacOS | 与 Hub 无关 | `interface.json:70-141` |

**ADB 端「游戏在运行」的判定 = 包名 + Activity**（`tasks/AndroidOpenGame.json`）：

| 区服 | StartApp 包名 / Activity | StopApp 包名 | 行号 |
| --- | --- | --- | --- |
| CN | `com.hypergryph.endfield/com.u8.sdk.U8UnityContext` | `com.hypergryph.endfield` | `:38` / `:46` |
| Bilibili | `com.hypergryph.endfield.bilibili/com.u8.sdk.U8UnityContext` | `com.hypergryph.endfield.bilibili` | `:60` / `:68` |
| Global | `com.gryphline.endfield.gp/com.u8.sdk.U8UnityContext` | `com.gryphline.endfield.gp` | `:82` / `:90` |
| VN | `com.hypergryph.endfield.vn/com.u8.sdk.U8UnityContext` | `com.hypergryph.endfield.vn` | `:104` / `:112` |
| 云 | `com.hypergryph.cloud.endfield/com.hypergryph.cloud.endfield.splash.SplashActivity` | `com.hypergryph.cloud.endfield` | `:137` / `:145` |

**PC 端 go-service（`agent/go-service.exe`）里的运行判定**（二进制符号 + 字符串，★★）：

| 符号 / 字符串 | 含义 |
| --- | --- |
| `.../pretask/launchgamepc.isProcessRunning` | 进程是否在跑（用于判断是否还要拉起启动器） |
| `.../pretask/launchgamepc.gameClassRegex` / `gameWindowRegex` / `launcherClassRegex` / `launchers` / `findWindow` / `waitWindow` / `runLauncherPipeline` / `startLauncher` | 找游戏窗口 / 找启动器窗口 / 等窗口出现 |
| `.../common/closegame.isEndfieldRunning` / `waitEndfieldExit` | 关游戏时判断 `Endfield.exe` 是否在跑 / 等它退出 |
| `CloseGameAction: Endfield.exe not running` / `killed` / `exited` / `timed out waiting for Endfield.exe exit` | 明文日志字符串，进程名 `Endfield.exe` |
| `github.com/shirou/gopsutil/v4/process` | 用 gopsutil 做进程枚举（不是 Toolhelp） |
| `^Qt\d+QWindowIcon$` | **启动器窗口类正则**（Qt 窗口类，如 `Qt5158QWindowIcon`） |
| `鹰角启动器` / `launcher_path` / `InstallLocation` / `uninstall_key` | 启动器标题 / 启动器安装路径发现 |
| `Software\\Hypergryph\\Endfield`、`Software\\Gryphline\\Endfield` | 按区服从注册表读安装信息 |
| `Skip Auto HDR: no Endfield.exe value under UserGpuPreferences` | 说明还会读 `HKCU` 下以 `Endfield.exe` 为键的值 |

> 结论：MaaEnd 的 PC 判定 = **`UnityWndClass` + 标题含 `Endfield`**；启动器判定 = **Qt 窗口类 + `鹰角启动器` 标题 + `Launcher.exe`**；关游戏/预动作判定 = **`Endfield.exe` 进程**。

### 4.2 可直接落地的规则建议（Hub）

```json
{
  "win_class": "^UnityWndClass$",
  "win_title": "Endfield|终末地",
  "procs": ["Endfield.exe"],
  "launcher": {
    "procs": ["Launcher.exe"],
    "procs_path_re": "(Hypergryph Launcher|Arknights bilibili)\\\\Launcher\\.exe$",
    "win_class": "^Qt\\d+QWindowIcon$",
    "win_title": "鹰角启动器"
  },
  "adb_pkg": [
    "com.hypergryph.endfield",
    "com.hypergryph.endfield.bilibili",
    "com.gryphline.endfield.gp",
    "com.hypergryph.endfield.vn",
    "com.hypergryph.cloud.endfield"
  ],
  "adb_activity": "com.u8.sdk.U8UnityContext"
}
```

- `UnityWndClass` 是**大量 Unity 游戏共用的通用类名**，绝不能单独作为判定条件；必须叠加标题正则。
- 标题用搜索而非全匹配（官方 EN 客户端标题可能类似 `Endfield`，CN 可能是 `明日方舟：终末地`；MaaEnd 二进制里同时出现 `明日方舟`、`终末地` 两个中文字面量，★★）。
- `Endfield.exe` 进程建议同时校验路径（`...\games\Endfield Game\Endfield.exe`），避免同名误判。
- 启动器规则同样适用于 MAA 的 PC 客户端启动器（两者都是鹰角启动器架构），可提取为共享规则。

### 4.3 可靠性与边界

- `interface.json` 只声明了类名+标题，**没有要求窗口唯一、没有要求前台**；MaaEnd 的 Win32-Front 明确「需要游戏窗口保持在最前且不被遮挡，会完全抢占鼠标」⇒ Hub 侧判定不需要前台。
- 安卓端（ADB/CloudADB）在 Windows 侧没有游戏窗口；MaaEnd 用包名 + `StartApp/StopApp`。Hub 若要支持「模拟器内终末地」，必须走 ADB 或「模拟器进程 + 模拟器窗口」，见 §9。
- 云终末地（`com.hypergryph.cloud.endfield`）本地无游戏 exe，只有云客户端窗口/流；**Hub 无法用本地 Win32 规则判断**。

---

## 5. ok-ww（鸣潮）

### 5.1 它怎么判断「游戏在运行」—— 源码逐层拆解

ok-ww 是四者中检测条件最完整的（Python 源码，★★★）。

**（1）声明检测参数** —— `config.py:197-212`

```python
'windows': {                       # required when supporting windows game
    'top_hwnd_class': [re.compile('CAgreementDlg'), re.compile('CLoginDlg_P_'),
                       'CefBrowserWindow', 'Chrome_RenderWidgetHostHWND', '#32770',
                       re.compile('CNativeLoginDlg'), 'Static', 'ComboBox', 'ComboLBox', 'Button'],
    'calculate_pc_exe_path': calculate_pc_exe_path,
    'launch_arguments': get_game_launch_arguments,
    'exe': 'Client-Win64-Shipping.exe',
    'hwnd_class': 'UnrealWindow',
    'interaction': 'PostMessage',
    'capture_method': ['WGC', 'BitBlt_RenderFull'],
    ...
}
```

- `hwnd_class: 'UnrealWindow'` —— 主窗口类名（字符串相等或正则匹配，见 `window.py:286-297`）
- `exe: 'Client-Win64-Shipping.exe'` —— **窗口所属进程名必须匹配**
- `top_hwnd_class` —— 游戏内登录/协议/加载等附属窗口的类名（用于把它们一起纳入截图范围/点击目标），不是游戏运行判定条件

**（2）枚举窗口并做多重校验** —— `ok/util/window.py:329-440` 的 `find_hwnd()`

判定顺序（`is_match()` 闭包，339-384 行）：

1. `IsWindow(hwnd) && IsWindowEnabled(hwnd)` 才继续（340）
2. 取 `GetClassNameW`；若 `class_name` 参数给出，必须匹配；**若 `class_name is None` 且窗口不可见则直接排除**（343-346）
3. 标题：若传 `title`，**字符串相等**或**正则搜索**（362-367）；ok-ww 的 config 未配 `title` ⇒ **不校验标题**
4. `get_exe_by_hwnd(hwnd)`（`window.py:52-86`）：`GetWindowThreadProcessId` → `psutil.Process(pid).name() / .exe() / .cmdline()`，然后 `compare_path_safe(name, exe_name)`（大小写/斜杠归一化，见 265-270）—— **进程名校验**
5. 可选 `player_id` 从 cmdline 提取（273-283），用于多开区分
6. `get_window_bounds()` 后 `width<=10 || height<=10` 直接排除（379-381）
7. 全部通过才放进 `results`

之后（386-440）：

- 无人命中 ⇒ 返回 `None`
- 命中多个 ⇒ 取 **client 面积最大**者（392），但优先用户 `selected_hwnd`，其次 `last_hwnd`（若面积不缩小超过 10%，399-401）
- 若给了 `top_hwnd_class`：把同 exe/同目录的附属窗口按 z-order 合并（405-427），并展开可点击子窗口
- 若没给 `class_name`：用 `EnumChildWindows` 找与目标宽高比一致的子窗口作为真实画面区域（300-326, 429-436）

**（3）「是否运行」的最终判定** —— `ok/device/DeviceManager.py` + `capture_methods/hwnd_window.py`

- `DeviceManager.update_pc_device()`（235-287）：调 `find_hwnd(...)`，`connected = hwnd > 0`（274）
- `HwndWindow.do_update_window_size()`（`hwnd_window.py:235-282`）：先 `find_hwnd` 刷新 hwnd；随后 `exists = hwnd > 0 and win32gui.IsWindow(hwnd)`（279-282）
- 启动流程 `ok/core/start_controller.py`：`_wait_until_device_ready()`（128-145）轮询 `do_refresh` + `check_device_error`，直到 hwnd 出现；`_wait_until_started_window_stable()`（147-176）还要求窗口尺寸 ≥ 最小值并稳定 2 秒（`STARTED_WINDOW_MIN_SIZE`），超时 `start_timeout`（config `start_timeout: 120`）

**（4）启动游戏时的 exe 路径推断** —— `config.py:13-118`

- `_find_most_recently_run_pc_exe()`：读 `HKCU\...\Explorer\UserAssist\*\Count` 里 rot-13 编码的路径，筛 `\wuthering waves.exe`，按 `struct.unpack_from("<Q", data, 60)` 的最近运行时间取最大（13-43）
- `_find_pc_exe_from_registry()`：读卸载表 `InstallPath/InstallLocation/LauncherPath/DisplayIcon/UninstallString`，在附近找 `Wuthering Waves.exe`（46-111）
- `calculate_pc_exe_path(running_path)`：`Path(running_path).parents[3] / "Wuthering Waves.exe"`（114-118）—— 从「正在运行的 exe」反推游戏根 exe（注意 **launcher 和游戏本体**都在用）
- `DeviceManager.get_exe_path()`（799-831）：`windows` 设备走 `calculate_pc_exe_path(full_path)`，返回前 `os.path.exists` 校验

**（5）运行日志实锤**（`working/logs/ok-script.log`，★★★）

```
2026-10-04 00:25:28,343 INFO ... HwndWindow init title:None player_id:-1
    exe_name:['Client-Win64-Shipping.exe'] hwnd_class:UnrealWindow
    top_hwnd_class:[re.compile('CAgreementDlg'), ...]
2026-10-04 00:26:54,183 INFO ... hwnd changed from 0 to 5050142 top 5050142
    E:\Wuthering Waves\Wuthering Waves Game\Client\Binaries\Win64\Client-Win64-Shipping.exe UnrealWindow real:0,0,1920,1080
2026-10-04 00:26:56,272 INFO ... pc_device: {'imei': 'pc_5050142', 'nick': '鸣潮  ', 'width': 1920,
    'height': 1080, 'connected': True,
    'full_path': 'E:\\Wuthering Waves\\Wuthering Waves Game\\Client\\Binaries\\Win64\\Client-Win64-Shipping.exe',
    'real_hwnd': 5050142, 'exe': ['Client-Win64-Shipping.exe']}
```

以及 `working/configs/devices.json`（保存的最终设备）：

```json
{
  "preferred": "pc_5050142",
  "pc_full_path": "E:\\Wuthering Waves\\Wuthering Waves Game\\Client\\Binaries\\Win64\\Client-Win64-Shipping.exe",
  "capture": "WGC",
  "selected_exe": ["Client-Win64-Shipping.exe"],
  "selected_hwnd": 5050142,
  "interaction": "PostMessage"
}
```

⇒ 实测窗口标题 `鸣潮  `（两个尾随空格）、类 `UnrealWindow`、进程 `Client-Win64-Shipping.exe`、1920×1080。

### 5.2 可直接落地的规则建议（Hub）

```json
{
  "win_class": "^UnrealWindow$",
  "win_title": "^\\s*鸣潮\\s*$",
  "title_optional": true,
  "procs": ["Client-Win64-Shipping.exe"],
  "procs_path_re": "Wuthering Waves\\\\Wuthering Waves Game\\\\Client\\\\Binaries\\\\Win64\\\\Client-Win64-Shipping\\.exe$",
  "also_procs": ["Wuthering Waves.exe"],
  "launcher_procs": ["launcher.exe"],
  "launcher_path_re": "Wuthering Waves\\\\launcher\\.exe$"
}
```

- **必须同时要求 class + 进程名**（照抄 ok-ww）：`UnrealWindow` 是虚幻引擎通用窗口类，很多 UE 游戏都用；`Client-Win64-Shipping.exe` 也是通用名（项目名不同才会变，本游戏就是 `Client`）。两者组合后误判率极低。
- 标题建议做成 `title_optional`（ok-ww 本身不校验标题），若要求标题请用 `^\s*鸣潮\s*$` 并容忍尾随空格。
- **不要只填 `LAUNCHER.EXE`**（Hub 现状）：这是启动器，且名字太通用；启动器请单独用 `launcher_path_re` 限定路径。
- 进程路径校验：若 Hub 无法读取 exe 全路径（权限），退化为 class+进程名组合即可，仍比现状可靠得多。

### 5.3 可靠性与边界

- ok-ww 需要管理员权限（`start_controller.py:183-188`：`PC version requires admin privileges`）才能对游戏进程截图/发消息；**Hub 只做检测不需要管理员**，但读 `process.exe()` 路径在游戏以更高权限运行时可能 `AccessDenied`（`window.py:71-75` 已处理为空串）⇒ Hub 应实现「路径读取失败则只用进程名」降级。
- 多开：ok-ww 用 `player_id`（cmdline 里的数字/`index=`）区分多个客户端；Hub 若只做 on/off 可忽略，但规则里保留 `selected_hwnd` 概念便于后续「聚焦窗口」。
- 窗口最小化/移出屏幕：ok-ww 会暂停（`hwnd_window.py:292-299`），但 `exists` 仍为 True ⇒ Hub 检测不应把最小化判为关闭。

---

## 6. MAA（明日方舟）

MAA 有两种完全不同的连接方式，对应两套「游戏运行」判定。

### 6.1 PC 客户端模式：按窗口标题找窗口（Win32 AttachWindow）

**配置键**（`MAA.dll` 字符串，★★）：
`Connect.UseAttachWindow`、`Connect.AttachWindow.ScreencapMethod`、`Connect.AttachWindow.MouseMethod`、`Connect.AttachWindow.KeyboardMethod`；
PC 客户端启动相关：`StartPcClient`、`PcClientPath`、`PcClientWaitSeconds`、`OpenPcClientAfterLaunch`、`RestartPcClientWhenConnectFailed`、`RetryPcClientOnDisconnected`、`PcClientAddCommand`。

**实现**（`MAA.dll` 字符串 + 运行时日志，★★★）：

- 方法/日志符号：`FindWindowsByName`、`TryFindWindow`、`EnumWindows`；日志模板
  - `AttachWindow: Found window "{WindowName}" with HWND: {Hwnd}`
  - `AttachWindow: No window found with name {WindowName}`
  - `AttachWindow: Multiple windows found with name {WindowName}, count: {Count}, using first one: {Hwnd}`
- 运行时日志（`debug/gui.log`）：
  ```
  2026-02-15 03:00:37.746 [WRN][AsstProxy] AttachWindow: Multiple windows found with name 明日方舟, count: 2, using first one: "529344"
  2026-02-15 03:00:37.940 [ERR][TaskQueueViewModel] AttachWindow 绑定窗口失败，请检查截图/输入方式配置
  2026-05-13 10:06:14.674 [INF][AsstProxy] AttachWindow: Found window "明日方舟" with HWND: "921028"
  ```
  ⇒ **MAA 的 PC 端判定 = 桌面存在标题为 `明日方舟` 的顶层窗口**；不校验类名，不要求唯一（找到 2 个也照用第一个）。
- `MAA.dll` 里另有两个中文 UTF-16 字面量 `明日方舟`、`明日方舟 - MuMu模拟器`，与 `BlueStacks App Player`、`Google Play Games on PC Emulator` 出现在同一字符串池（★★）⇒ 这是**模拟器窗口标题列表**（MAA 按标题找/关模拟器窗口时用），不是 PC 客户端类名。
- PC 客户端 exe 由用户选择（`PcClientPath`），MAA **不按进程名判断 PC 客户端是否运行**（推断 ★，依据：二进制中无 `Arknights.exe` 字样，且日志只体现窗口绑定）。

**本机对照**（§11）：Arknights PC 客户端实际位于 `E:\Arknights bilibili\games\Arknights Game\Arknights.exe`，其 `UnityPlayer.dll` 内含 UTF-16 `UnityWndClass`（★★）；窗口标题为 `明日方舟`（★★★，MAA 日志）。

### 6.2 模拟器模式：ADB + 包名

**包名映射**（`resource/config.json:46-53`，★★★）：

```json
"packageName": {
  "Official": "com.hypergryph.arknights",
  "Bilibili": "com.hypergryph.arknights.bilibili",
  "YoStarEN": "com.YoStarEN.Arknights",
  "YoStarJP": "com.YoStarJP.Arknights",
  "YoStarKR": "com.YoStarKR.Arknights",
  "txwy":     "tw.txwy.and.arknights"
}
```

**启动/停止命令**（`resource/config.json:77-78`，★★★）：

```
start: [Adb] -s [AdbSerial] shell am start -n [PackageName]/com.u8.sdk.U8UnityContext
stop:  [Adb] -s [AdbSerial] shell am force-stop [PackageName]
```

**连接配置种类**（`resource/config.json:54-171`，★★★）：
`General`、`CapWithShell`、`BlueStacks`、`MuMuEmulator12`、`MuMuArm`、`LDPlayer`、`Androws`、`Nox`、`XYAZ`、`WSA`、`Compatible`、`SecondResolution`、`CompatMac`、`CompatPOSIXShell`、`Waydroid`、`AVD`。
其中 `MuMuEmulator12` 只覆写了 orientation（96-99 行），`Waydroid` 用 `--windowingMode 4` 启动（162 行）。

**本机实际连接配置**（`config/gui.json.old:10-33`，★★★）：

```
Connect.AdbPath        = E:\MuMuPlayer-12.0\nx_device\12.0\shell\.\adb.exe
Connect.Address        = 127.0.0.1:16384
Connect.AddressHistory = ["127.0.0.1:16384","emulator-5554","127.0.0.1:16416","192.168.3.78:5555","192.168.0.102:5555"]
Connect.ConnectConfig  = MuMuEmulator12
Connect.MuMu12EmulatorPath = E:\MuMuPlayer-12.0
Connect.MuMu12Index    = 0
Connect.MuMuBridgeConnection = False
```

**MuMu 扩展**（`MaaCore.dll` / `MaaAdbControlUnit.dll` 字符串，★★）：
`MaaNS::CtrlUnitNs::MuMuPlayerExtras`、`extras.mumu.path` / `extras.mumu.lib`、`mumu_index_`、`package_name_`、
`Failed to get display id for package, try default`、`MaaAdbControlUnit` 的 `{ADB}` / `{ADB_SERIAL}` 占位符、`adb_path` / `adb_serial`。
MaaToolkit 侧还有 `AdbDeviceWin32Finder::find_mumu_devices`（★★）⇒ MAA 能自动从 MuMu 安装信息发现 ADB 地址。

**运行时日志**（`debug/gui.log`，★★★）：

```
2025-11-12 23:24:25.953 [INF][AsstProxy] name: MuMuEmulator12, extras: {"path":"E:\\MuMuPlayer-12.0"}
2025-11-12 23:24:28.964 [INF][AsstProxy] handle: ..., adbPath: E:\MuMuPlayer-12.0\nx_device\12.0\shell\.\adb.exe,
                                         address: emulator-5554, config: MuMuEmulator12
2025-11-12 23:24:35.079 [INF][AsstProxy] ... return: true
2025-11-12 23:24:35.082 [INF][TaskQueueViewModel] 最快截图耗时: 20ms (MumuExtras)
```

以及大量 `adb.exe -s 127.0.0.1:16384 shell "dumpsys SurfaceFlinger --latency | head -n 1"`（`debug/asst.log`）⇒ 连接状态 = `adb connect` 成功 + `devices` 列表里出现 + shell 命令返回 0。

**Win32 控制单元**（`MaaWin32ControlUnit.dll` / `MaaCore.dll`，★★）：
`MaaWin32ControlUnitCreate`、`MaaNS::CtrlUnitNs::Win32ControlUnitMgr::connect`、`asst::Win32Controller::attach` ⇒ Win32 模式是「外部拿 hwnd，交给控制单元 attach」，所以**窗口类/标题的匹配发生在 UI 层（MAA.dll）而不是 Core**。

### 6.3 可直接落地的规则建议（Hub）

```json
{
  "maa": {
    "pc": {
      "win_class": "^UnityWndClass$",
      "win_title": "^\\s*明日方舟|^\\s*Arknights",
      "title_required": true,
      "procs": ["Arknights.exe"],
      "procs_path_re": "Arknights Game\\\\Arknights\\.exe$",
      "launcher": { "procs": ["Launcher.exe"],
                    "procs_path_re": "Arknights bilibili\\\\Launcher\\.exe$",
                    "win_class": "^Qt\\d+QWindowIcon$", "win_title": "鹰角启动器" }
    },
    "emulator": {
      "adb_pkg": ["com.hypergryph.arknights", "com.hypergryph.arknights.bilibili",
                  "com.YoStarEN.Arknights", "com.YoStarJP.Arknights",
                  "com.YoStarKR.Arknights", "tw.txwy.and.arknights"],
      "adb_activity": "com.u8.sdk.U8UnityContext",
      "emu_procs": ["MuMuPlayer.exe", "MuMuNxMain.exe", "NemuPlayer.exe", "dnplayer.exe", "HD-Player.exe"]
    }
  }
}
```

- **PC 端**：以窗口标题为第一依据（这正是 MAA 自己的做法）；`Arknights.exe` 进程 + 路径作为兜底/辅助。
- 标题正则建议 `^\s*明日方舟`（CN）与 `^\s*Arknights`（EN）二选一或 `any_of`；**不要要求窗口唯一**（MAA 日志里同名窗口有 2 个）。
- **模拟器端**：Hub 无法从 Win32 侧看到安卓游戏进程，建议：
  - 首选 ADB：`adb -s <serial> shell dumpsys window | grep mCurrentFocus` 或 `pm list packages` 匹配包名；serial 可参考 MAA 的 `127.0.0.1:16384`（MuMu12 默认）与 `emulator-5554`。
  - 退路：`MuMuPlayer.exe` 等模拟器进程 + 模拟器窗口标题（`明日方舟 - MuMu模拟器`，★★）+ 用户手动指定「游戏已启动」。
  - 最省事方案：UI 上允许用户为 MAA 卡片选择「PC 客户端 / 模拟器」模式，两种模式用不同规则集（与 MAA 自己的 `ConnectConfig.PC` vs `MuMuEmulator12` 一一对应）。

### 6.4 可靠性与边界

- PC 端不校验类名 ⇒ 若系统里存在其它标题为 `明日方舟` 的窗口（如浏览器标签窗口、模拟器窗口标题恰好相同），会被 MAA 采信（日志中 `count: 2` 就是这种情况）。Hub 用 **标题 + 类名（UnityWndClass）** 双条件可以比 MAA 更严格。
- 模拟器端 ADB 判定依赖 `adb` 可执行文件与端口；MuMu 每次启动端口可能变（`16384 + 32*index`），建议 serial 从 `adb devices` 实时取，而不是写死。
- 端口历史里出现过 `192.168.x.x:5555`（无线 ADB），说明用户可能连真机/无线调试 ⇒ Hub 的 ADB 规则要允许任意 serial。

---

## 7. 横向对比：三种框架的通用模式（重要）

| 维度 | MXU（MaaNTE / MaaEnd） | MaaFramework Core | ok-script（ok-ww） | MAA（WPF） |
| --- | --- | --- | --- | --- |
| 枚举方式 | `MaaToolkitDesktopWindowFindAll(class_regex, window_regex)`（内部 EnumWindows + IsWindowVisible） | 不枚举，等待外部传入 hwnd | `win32gui.EnumWindows` | UI 层 `EnumWindows` + `FindWindowsByName` |
| 匹配条件 | 类名正则 + 标题正则（来自 `interface.json`） | 只认 hwnd | 类名（精确/正则）+ 进程名（psutil）+ 可见/尺寸 | 标题（精确/子串） |
| 是否用进程名 | 是（`check_process_running`，用于 pre-action `skipIfRunning`） | 否 | 是（强校验，窗口 PID→进程名） | 否（PC 端）；模拟器端用 ADB 包名 |
| 是否用窗口标题 | 是（主条件） | 否 | 否（可选） | 是（主条件） |
| 「运行中」定义 | 找到匹配窗口（或等待出现） | hwnd 有效 | `hwnd>0 && IsWindow(hwnd)` + 面积>10px | 找到标题匹配窗口 |
| 保存状态 | `savedDevice.windowName` + `connectedProgramPath` | hwnd | `devices.json`（pc_full_path / selected_hwnd / exe） | `PcClientPath` + 上次窗口名 |
| 失败兜底 | 等窗口超时 | — | 无 exe/class/title 时枚举所有可见窗口让用户选 | 提示绑定失败 |

**共性结论（Hub 可直接照搬）**：

1. 先 `EnumWindows` 建一次快照（可见/非 toolwindow/有标题/客户区 >100×100），同一轮刷新里所有卡片复用。
2. 每个游戏用 **`(类名正则, 标题正则)` 二元组** 作为主键；进程名只作辅助与兜底。
3. 窗口 → `GetWindowThreadProcessId` → 进程名/exe 路径，这是 MXU（`get_process_path_from_hwnd`）和 ok-ww（`get_exe_by_hwnd`）共同做法，可用于「窗口属于游戏」的二次校验与「聚焦窗口」。
4. 允许「同名多窗口」「最小化」「标题带尾随空格」；不要要求唯一、前台、可见。

---

## 8. 统一规则 schema 建议（供 feature-dev 实现）

目标：一份规则同时支持「Win32 窗口 / 进程 / ADB」三类证据，`any_of` 任一命中即视为运行，并可标出「启动器已开 / 云游戏」等中间状态。

```json
{
  "schema_version": 1,
  "apps": {
    "nte": {
      "label": "异环",
      "detect": {
        "any_of": [
          {
            "type": "win",
            "class_re": "^UnrealWindow$",
            "title_re": "^\\s*(异环|NTE)\\s*$",
            "require_visible": false,
            "min_client_size": [200, 120],
            "require_foreground": false,
            "match": "all"
          },
          {
            "type": "proc",
            "names": ["HTGame.exe"],
            "path_re": "\\\\Client\\\\WindowsNoEditor\\\\HT\\\\Binaries\\\\Win64\\\\HTGame\\.exe$"
          }
        ],
        "state_labels": { "win": "running", "proc": "running" }
      },
      "launcher": {
        "any_of": [
          { "type": "proc", "names": ["NTELauncher.exe"] }
        ]
      },
      "cloud": {
        "any_of": [
          { "type": "win", "class_re": "^Qt.*$", "title_re": "^\\s*云.*?异环\\s*$" }
        ]
      }
    },

    "maaend": {
      "label": "明日方舟：终末地",
      "detect": {
        "any_of": [
          { "type": "win", "class_re": "^UnityWndClass$", "title_re": "Endfield|终末地",
            "min_client_size": [200, 120] },
          { "type": "proc", "names": ["Endfield.exe"],
            "path_re": "\\\\games\\\\Endfield Game\\\\Endfield\\.exe$" }
        ]
      },
      "launcher": {
        "any_of": [
          { "type": "win", "class_re": "^Qt\\d+QWindowIcon$", "title_re": "鹰角启动器" },
          { "type": "proc", "names": ["Launcher.exe"],
            "path_re": "Hypergryph Launcher\\\\Launcher\\.exe$" }
        ]
      },
      "adb": {
        "any_of": [
          { "type": "adb", "pkg": ["com.hypergryph.endfield", "com.hypergryph.endfield.bilibili",
                                   "com.gryphline.endfield.gp", "com.hypergryph.endfield.vn",
                                   "com.hypergryph.cloud.endfield"],
            "activity": "com.u8.sdk.U8UnityContext", "serial_re": ".*" }
        ]
      }
    },

    "wuwa": {
      "label": "鸣潮",
      "detect": {
        "any_of": [
          { "type": "win", "class_re": "^UnrealWindow$", "title_re": "^\\s*鸣潮\\s*$",
            "title_optional": true, "min_client_size": [200, 120] },
          { "type": "proc", "names": ["Client-Win64-Shipping.exe"],
            "path_re": "Wuthering Waves\\\\Wuthering Waves Game\\\\Client\\\\Binaries\\\\Win64\\\\Client-Win64-Shipping\\.exe$" }
        ],
        "proc_class_check": {
          "name": "Client-Win64-Shipping.exe",
          "win_class_re": "^UnrealWindow$"
        }
      },
      "launcher": {
        "any_of": [ { "type": "proc", "names": ["launcher.exe"],
                      "path_re": "Wuthering Waves\\\\launcher\\.exe$" } ]
      }
    },

    "maa": {
      "label": "明日方舟",
      "detect": {
        "any_of": [
          { "type": "win", "class_re": "^UnityWndClass$", "title_re": "^\\s*(明日方舟|Arknights)",
            "min_client_size": [200, 120] },
          { "type": "proc", "names": ["Arknights.exe"],
            "path_re": "Arknights Game\\\\Arknights\\.exe$" },
          { "type": "adb", "pkg": ["com.hypergryph.arknights", "com.hypergryph.arknights.bilibili",
                                   "com.YoStarEN.Arknights", "com.YoStarJP.Arknights",
                                   "com.YoStarKR.Arknights", "tw.txwy.and.arknights"],
            "activity": "com.u8.sdk.U8UnityContext", "serial_re": ".*" }
        ]
      },
      "launcher": {
        "any_of": [
          { "type": "win", "class_re": "^Qt\\d+QWindowIcon$", "title_re": "鹰角启动器" },
          { "type": "proc", "names": ["Launcher.exe"],
            "path_re": "Arknights bilibili\\\\Launcher\\.exe$" }
        ]
      }
    }
  },

  "globals": {
    "poll_interval_ms": 2000,
    "win_snapshot": {
      "skip_toolwindow": true,
      "skip_empty_title": true,
      "min_client_size": [100, 100],
      "allow_minimized": true
    },
    "proc_path_lookup": "best_effort",
    "adb": { "enabled": false, "adb_path": "", "probe_timeout_ms": 1500 }
  }
}
```

### 8.1 字段语义（实现约定）

| 字段 | 语义 |
| --- | --- |
| `type` | `win` / `proc` / `adb` |
| `class_re` | 对 `GetClassNameW` 结果做 `re.search`（ok-ww 的 `_match_class_name` 即是 search，MXU 的 `classRegex` 亦是 find 语义） |
| `title_re` | 对 `GetWindowTextW` 结果做 `re.search`；默认**不做 strip**，用 `\s*` 容忍尾随空格（异环/鸣潮实测都有） |
| `title_optional` | true 时标题不参与判定（用于 ok-ww 这类「不校验标题」的产品） |
| `match` | `all`（class 与 title 同时满足，默认）/ `any` |
| `min_client_size` | `GetClientRect` 宽高下限，过滤掉隐藏的 0×0 窗口 |
| `require_visible` | 默认 false；`IsWindowVisible` 为 false 仍算运行（最小化/被遮挡） |
| `names` / `path_re` | 进程名（大小写不敏感）与 `QueryFullProcessImageNameW` 全路径正则；`path_re` 仅用于**收窄同名风险**，取不到路径时降级为只比名字 |
| `pkg` / `activity` / `serial_re` | ADB：`pm list packages` / `dumpsys window` 前台包名 / `adb devices` 序列号 |
| `launcher` / `cloud` | 与 `detect` 同结构，只用于显示「启动器已开」「云游戏」中间状态，不计入 `running` |

### 8.2 检测算法建议（伪代码）

```python
def poll(apps):
    wins = snapshot_windows()          # 一次 EnumWindows：hwnd, class, title, client_size, pid, exe_path(可选)
    procs = snapshot_processes()       # 现有 Toolhelp32；另建 name->set(pid) 用于给 win 补 exe_path
    adb_cache = adb_devices() if enabled else {}

    for app in apps:
        state = "off"
        for rule in app.detect.any_of:
            if rule.type == "win" and any(win_match(w, rule) for w in wins):
                state = "running"; break
            if rule.type == "proc" and proc_match(procs, rule, wins):
                state = "running"; break
            if rule.type == "adb" and adb_match(adb_cache, rule):
                state = "running"; break
        # 只有 detect 未命中时才检查 launcher / cloud，用于 UI 文案
        app.state = state
        app.launcher_on = match_any(app.launcher, wins, procs)
        app.cloud_on = match_any(app.cloud, wins)
```

实现要点：

1. **性能**：`EnumWindows` 在本机窗口数量级下 <1ms；`GetWindowThreadProcessId` + 进程名快照一次即可。现有 2 秒轮询（`ui.py` 的 `_refresh`）完全够用，不需要额外线程。
2. **进程 exe 路径**：尽量用 `QueryFullProcessImageNameW`（MXU 同款），失败时退回 `psutil`/空串；**路径仅用于收窄，不作为必要条件**，避免权限问题导致永远 off。
3. **窗口 → 进程名**：`win.class/title` 命中后可以不再校验进程名；`proc` 规则命中时若存在同名但不同路径的进程（如多个 `Launcher.exe`），用 `path_re` 过滤。
4. **兼容旧配置**：`game_procs` 保留为 `detect.any_of` 里的 `type=proc` 规则；迁移时按 §8 的 JSON 一次性升级 `config.json`（`version: 3 → 4`）。
5. **UI 状态**：建议三态 `off / launcher / running`（+ 可选 `cloud`）；当前 `_game_state()` 只有 on/off/unset，可在不改布局的前提下扩展文案。

---

## 9. 无法可靠检测的情况（必须写进文档/UI 提示）

| 场景 | 为什么难 | 建议 |
| --- | --- | --- |
| **模拟器内游戏**（MAA 走 MuMu、MaaEnd 走 ADB） | Windows 侧只有模拟器进程/窗口，没有游戏进程；游戏是 Android 进程 | ① 首选 ADB：`pm list packages` / `dumpsys window` 前台包名（MAA 配置里有完整包名表，见 §6.2）；② 退路：模拟器进程（`MuMuPlayer.exe` 等）+ 模拟器窗口标题（`明日方舟 - MuMu模拟器`，MAA.dll 字符串）；③ UI 允许用户手动声明「模拟器模式」 |
| **云游戏**（MaaNTE `CloudGame-Front`、MaaEnd `CloudADB`） | 本地无游戏 exe、无 UE/Unity 窗口；只有云客户端窗口（MaaNTE：`Qt.*` + `云.*异环`） | 单列 `cloud` 规则并显示「云游戏运行中」，不要与本地 `running` 混用；MaaEnd 云端甚至只有安卓 ADB 包名 |
| **启动器 ≠ 游戏**（异环 NTELauncher、鸣潮 launcher、鹰角启动器） | 启动器可能常驻、可能与游戏同时存在、进程名通用（`Launcher.exe`） | 启动器规则单独放 `launcher`，用**路径正则**收窄；`running` 只由游戏窗口/进程决定 |
| **窗口存在但停在登录/更新界面** | 窗口在 ≠ 已进入对局 | Hub 语义定义为「游戏已启动」即可；若要「已登录」，需截图/OCR，超出本次范围 |
| **同名多窗口**（MAA 日志 `count: 2`；异环 `异环  ` 有尾随空格） | 唯一性假设不成立 | 判定用「存在任一命中」，不用「唯一命中」；标题用正则容忍空白 |
| **游戏以管理员权限运行、Hub 普通权限** | `QueryFullProcessImageName`/`psutil.Process.exe()` 可能 `AccessDenied` | 路径校验失败即降级为「类名+标题」或「进程名」判定，并在日志里记 debug，不阻塞状态 |
| **全屏独占 / 最小化 / 窗口被遮挡** | `IsWindowVisible` 可能为 false，`GetClientRect` 正常 | 不要求 visible/前台；仅过滤 client 尺寸 ≤ 下限的隐藏窗口 |
| **游戏更新器阶段**（下载/校验，窗口类可能不同） | 早期启动阶段可能只有 updater 窗口 | 天然处于 `off`，属预期；可在 UI 提示「启动器已打开」帮助用户理解 |
| **同名进程误报**（`LAUNCHER.EXE`、`Client-Win64-Shipping.exe` 通用名） | 进程名不是唯一标识 | 进程规则必须配套 `path_re` 或窗口类校验（ok-ww 就是 class+进程名双条件） |

---

## 10. 证据索引（文件清单）

> 所有路径为绝对/相对本机安装目录；行号为静态阅读所得，二进制证据为字符串/符号。

### MaaNTE（`D:\All MAA\MaaNTE\`）

| 文件 | 内容 |
| --- | --- |
| `interface.json:20-71` | 4 个 controller 定义（Win32 / Win32-Front / Win32-Background / CloudGame-Front） |
| `interface.json:27-28,39-40,52-53,64-65` | `class_regex` / `window_regex` 具体值 |
| `config/mxu-MaaNTE.json:9-12` | `savedDevice.windowName = "异环  "`、`connectedProgramPath = ...\HTGame.exe` |
| `config/mxu-MaaNTE.json:141-152` | `preActions`（`skipIfRunning: true`） |
| `debug/2026-10-18-4.log:95-96` | MXU 实跑：「搜索 Win32 窗口, classRegex: UnrealWindow , windowRegex: ^\s*(异环\|NTE)\s*$」「找到 Win32 窗口: 0 个」 |
| `debug/maafw.log:43` | `DesktopWindowWin32Finder::find_all` |
| `agent/utils/win32_process.py:67,126-143,161-172,175-250,492-498` | 进程 PID 快照 + EnumWindows + 类名/标题/尺寸过滤 + 最大窗口选择；`DEFAULT_GAME_PROCESS_NAME = "HTGame.exe"` |
| `agent/main.py:450-457` | `find_window_by_process("HTGame.exe")` 自检窗口分辨率 |
| `agent/custom/action/auto_piano/maa_keyboard.py:45-48,68-82` | `WINDOW_TITLES = ["NTE  ", "异环  "]` + `FindWindowW` |
| `MaaNTE.exe`（二进制） | `maa_find_win32_windows`、`MaaToolkitDesktopWindowFindAll/GetClassName/GetWindowName`、`get_process_path_from_hwnd`、`check_process_running`、`is_process_running`、`is_path_from_hwnd`、`waitingForWindowNamed`、`windowWaitTimeout` |

### MaaEnd（`D:\All MAA\MaaEnd-win-x86_64-v2.33.0\`）

| 文件 | 内容 |
| --- | --- |
| `interface.json:26-38` | `Win32-Front`：`UnityWndClass` + `Endfield` |
| `interface.json:40-58` | ADB / CloudADB |
| `interface.json:60-141` | PlayCover / Linux / MacOS |
| `tasks/AndroidOpenGame.json:34-153` | 5 个包名 + `StartApp`/`StopApp` |
| `tasks/pretasks/LaunchGamePC.json:2-18` | 启动预任务绑定 `Win32-Front` |
| `tasks/CloseGamePC.json:2-20` | 关游戏绑定 `Win32-Front` |
| `agent/go-service.exe`（二进制符号/字符串） | `launchgamepc.isProcessRunning / gameClassRegex / gameWindowRegex / launcherClassRegex / launchers / findWindow / waitWindow / runLauncherPipeline / startLauncher`；`closegame.isEndfieldRunning / waitEndfieldExit`；`UnityWndClass`；`^Qt\d+QWindowIcon$`；`鹰角启动器`；`Endfield.exe`；`Software\Hypergryph\Endfield`、`Software\Gryphline\Endfield`、`InstallLocation`、`launcher_path`；`github.com/shirou/gopsutil/v4/process` |

### ok-ww（`D:\All MAA\WuwaMAA\ok-ww\`）

| 文件 | 内容 |
| --- | --- |
| `data/apps/ok-ww/repo/config.py:197-212` | `top_hwnd_class` / `exe: Client-Win64-Shipping.exe` / `hwnd_class: UnrealWindow` |
| `data/apps/ok-ww/repo/config.py:13-118` | UserAssist / 注册表 / `calculate_pc_exe_path`（`Wuthering Waves.exe`） |
| `data/apps/ok-ww/repo/ok/util/window.py:52-86` | `get_exe_by_hwnd`（psutil 进程名/exe/cmdline） |
| `.../ok/util/window.py:286-297` | `_match_class_name`（字符串相等或 `re.search`） |
| `.../ok/util/window.py:329-440` | `find_hwnd` 全流程（可见性/类/标题/进程/player_id/尺寸/最大面积/附属窗口） |
| `.../ok/util/window.py:442-475` | `find_all_visible_windows`（无 exe/class/title 时让用户选） |
| `.../ok/device/DeviceManager.py:235-287,799-831` | `update_pc_device`（`connected = hwnd > 0`）、`get_exe_path` |
| `.../ok/device/capture_methods/hwnd_window.py:235-282` | `find_hwnd` 刷新 + `exists = IsWindow(hwnd)` |
| `.../ok/core/start_controller.py:128-207` | 等待设备/窗口稳定、超时、启动游戏（需管理员） |
| `data/apps/ok-ww/working/logs/ok-script.log` | 2026-10-04 00:26:54 / 00:26:56：`hwnd changed ... Client-Win64-Shipping.exe UnrealWindow 1920x1080`、`nick: '鸣潮  '` |
| `data/apps/ok-ww/working/configs/devices.json:1-10` | `pc_5050142` / `pc_full_path` / `selected_exe` / `selected_hwnd` |

### MAA（`D:\All MAA\MAA-v5.1.0-win-x64\`）

| 文件 | 内容 |
| --- | --- |
| `resource/config.json:46-53` | `packageName` 六个区服包名 |
| `resource/config.json:54-171` | 16 种 connection 配置（含 `General.start/stop` 的 `am start` / `am force-stop`） |
| `config/gui.json.old:10-33` | `Connect.*`：`MuMuEmulator12`、`AdbPath`、`Address 127.0.0.1:16384`、`AddressHistory`、`MuMu12EmulatorPath` |
| `config/gui.json:6,22` | `Connect.MuMu12Display`、`Start.StartEmulator` |
| `debug/gui.log` | `AttachWindow: Found window "明日方舟" with HWND: "921028"`（2026-05-13 10:06:14）；`Multiple windows found with name 明日方舟, count: 2`（2026-02-15 03:00:37）；MuMu 连接日志（2025-11-12 23:24:25~35） |
| `debug/asst.log` | `adb.exe -s 127.0.0.1:16384 shell "dumpsys SurfaceFlinger --latency | head -n 1"` 等 ADB 调用 |
| `MAA.dll`（二进制） | `Connect.UseAttachWindow`、`Connect.AttachWindow.{Screencap,Mouse,Keyboard}Method`、`StartPcClient`、`PcClientPath`、`PcClientWaitSeconds`、`RestartPcClientWhenConnectFailed`、`RetryPcClientOnDisconnected`、`PcClientAddCommand`；`FindWindowsByName`、`TryFindWindow`、`EnumWindows`、`AttachWindow: ... {WindowName} ... {Hwnd}`；CJK：`明日方舟`、`明日方舟 - MuMu模拟器`、`BlueStacks App Player`、`Google Play Games on PC Emulator` |
| `MaaCore.dll`（二进制） | `com.hypergryph.arknights`、`package_name_`、`MaaNS::CtrlUnitNs::MuMuPlayerExtras`、`asst::Win32Controller::attach`、`MaaWin32ControlUnitCreate` |
| `MaaAdbControlUnit.dll`（二进制） | `adb_path`、`adb_serial`、`{ADB}`、`{ADB_SERIAL}`、`extras.mumu.path`、`MuMuPlayerExtras` |
| `MaaToolkit.dll`（二进制） | `DesktopWindowWin32Finder::find_all`、`MaaToolkitDesktopWindowGetClassName/GetWindowName/GetHandle`、`IsWindowVisible`、`AdbDeviceWin32Finder::find_mumu_devices` |

---

## 11. 本机静态验证记录（四游戏对照）

命令均为只读（Python 二进制查找 / PowerShell `Test-Path`）：

| 游戏 | 游戏本体 exe（本机实测存在） | 二进制中的窗口类字符串 | 与脚本配置对照 |
| --- | --- | --- | --- |
| 异环 | `D:\Neverness To Everness\Client\WindowsNoEditor\HT\Binaries\Win64\HTGame.exe`（273 MB，UE） | UTF-16 `UnrealWindow`（offset 189,546,024） | 与 MaaNTE `class_regex: UnrealWindow` 完全一致 |
| 鸣潮 | `E:\Wuthering Waves\Wuthering Waves Game\Client\Binaries\Win64\Client-Win64-Shipping.exe`（170 MB，UE） | UTF-16 `UnrealWindow`（offset 132,784,136） | 与 ok-ww `hwnd_class: UnrealWindow` 一致；运行日志亦实锤 |
| 终末地 | `E:\Hypergryph Launcher\games\Endfield Game\Endfield.exe`（Unity） | `UnityPlayer.dll` 内 UTF-16 `UnityWndClass` | 与 MaaEnd `class_regex: UnityWndClass` 一致 |
| 明日方舟 | `E:\Arknights bilibili\games\Arknights Game\Arknights.exe`（Unity） | `UnityPlayer.dll` 内 UTF-16 `UnityWndClass` | MAA 只用标题 `明日方舟`；类名来自 Unity 引擎标准，Hub 可用作二次校验 |

Unity 元数据（`*_Data/app.info`）：

```
E:\Arknights bilibili\games\Arknights Game\Arknights_Data\app.info  ->  HyperGryph / Arknights
E:\Hypergryph Launcher\games\Endfield Game\Endfield_Data\app.info   ->  HyperGryph / Endfield
```

启动器路径核对：`D:\Neverness To Everness\NTELauncher.exe`、`E:\Wuthering Waves\launcher.exe`、`E:\Hypergryph Launcher\Launcher.exe`、`E:\Arknights bilibili\Launcher.exe` 均存在；**这四者都不是游戏本体**，Hub 现状把其中三个当成了游戏（§1）。

---

## 12. 风险点与建议优先级

| 优先级 | 事项 |
| --- | --- |
| P0 | 移除 `game_procs` 里的 `LAUNCHER.EXE`（wuwa / maaend 撞车且是启动器）；改为 class+title 主判定 |
| P0 | 异环从 `NTELAUNCHER.EXE` 改成窗口规则（`UnrealWindow` + `异环/NTE` 标题）+ `HTGame.exe` 兜底 |
| P1 | MAA 卡片 `game_procs` 为空：PC 客户端用 `明日方舟` 标题 + `UnityWndClass`；模拟器模式走 ADB（可选，设置里开关） |
| P1 | 进程规则统一带 `path_re` 收窄（`launcher.exe`、`Client-Win64-Shipping.exe` 都是通用名） |
| P2 | 三态 UI（`off / launcher / running`，可选 `cloud`），避免用户把「启动器已开」误读为「游戏已开」 |
| P2 | ADB 探测作为可选模块（默认关），避免 Hub 启动时拉起 adb 进程 |
| P3 | 规则外置为 `config.json` 的 `detect` 字段（schema 见 §8），保留旧 `game_procs` 自动迁移 |

---

## 13. 附：复现命令（只读）

```powershell
# 1) 二进制窗口类字符串（UTF-16LE）
python -c "d=open(r'D:\Neverness To Everness\Client\WindowsNoEditor\HT\Binaries\Win64\HTGame.exe','rb').read(); print(d.find('UnrealWindow'.encode('utf-16-le')))"
python -c "d=open(r'E:\Wuthering Waves\Wuthering Waves Game\Client\Binaries\Win64\Client-Win64-Shipping.exe','rb').read(); print(d.find('UnrealWindow'.encode('utf-16-le')))"
python -c "d=open(r'E:\Arknights bilibili\games\Arknights Game\UnityPlayer.dll','rb').read(); print(d.find('UnityWndClass'.encode('utf-16-le')))"

# 2) 产品自带的窗口规则
Select-String -Path 'D:\All MAA\MaaNTE\interface.json' -Pattern 'class_regex|window_regex'
Select-String -Path 'D:\All MAA\MaaEnd-win-x86_64-v2.33.0\interface.json' -Pattern 'UnityWndClass|Endfield'
Select-String -Path 'D:\All MAA\WuwaMAA\ok-ww\data\apps\ok-ww\repo\config.py' -Pattern "hwnd_class|Client-Win64"

# 3) 运行时窗口检测证据
Select-String -Path 'D:\All MAA\MaaNTE\debug\2026-10-18-4.log' -Pattern '搜索 Win32 窗口|找到 Win32 窗口'
Select-String -Path 'D:\All MAA\MAA-v5.1.0-win-x64\debug\gui.log' -Pattern 'AttachWindow'
Select-String -Path 'D:\All MAA\WuwaMAA\ok-ww\data\apps\ok-ww\working\logs\ok-script.log' -Pattern 'hwnd changed|pc_device'

# 4) MAA 的包名/ADB 命令
Select-String -Path 'D:\All MAA\MAA-v5.1.0-win-x64\resource\config.json' -Pattern 'com.hypergryph|am start|am force-stop'
```

---

*报告完。所有结论均可由 §10 索引中的文件/行号或 §11 的本机二进制核对复现；标注 ★ 的条目为推断，落地前建议用一次真实启动实测确认。*
