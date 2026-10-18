# v0.7.0 调研：ok-ww 启动链与四游戏「一键清日常」方案

- 任务：shared task `task-15` —— 研究「鸣潮只打开启动器」的根因与四款脚本（MaaNTE / MaaEnd / ok-ww / MAA）的一键清日常调用方案，供 GameHub v0.7.0 实现。
- 仓库：`D:\All MAA\GameHub`（GitHub: https://github.com/Diaohesi/All-My-Maa ），基线版本 v0.6.0。
- 方法：本地源码/配置/运行时日志/二进制字符串静态分析 + GitHub 官方文档与源码核对（走 `curl -x http://127.0.0.1:7897`）。**未启动游戏、未执行清日常、未重启用户 Hub、未修改除本文件外的任何文件、未 commit。**
- 证据强度：★★★ 配置文件 / 可读源码 / 官方文档 / 运行时日志；★★ 二进制字符串 / 符号；★ 推断（需实测）。

---

## 0. 结论速览

1. **「鸣潮只打开启动器」有两个独立原因，都要修**：
   - **A. 脚本启动器**：Hub 的 `script_exe = WuwaMAA/ok-ww/ok-ww.exe` 是 PyAppify **启动器/更新器**，不是脚本本体；脚本本体是 `data\apps\ok-ww\working\main.py`，由 `data\apps\ok-ww\python\pythonw.exe` 运行。Hub 的 `script_procs=["OK-WW.EXE"]` 也把启动器当成了脚本（启动器在脚本启动后会被自己杀掉，见 §2.3）。
   - **B. 游戏启动器**：Hub 的 `game_exe = E:\Wuthering Waves\launcher.exe` 是**游戏启动器**，点「启动游戏」自然只打开启动器。游戏本体是 `E:\Wuthering Waves\Wuthering Waves Game\Wuthering Waves.exe`（ok-ww 自己也是这么算的，`config.py:114-118`）。
2. **ok-ww 支持完全无人值守的 CLI 自动执行（官方文档 + 源码双证据）**：`pythonw.exe main.py -t <任务> -e`；`-t` 支持数字序号 / 任务名 / 类名，`-e` 表示任务成功后退出程序并关闭游戏。ok-ww **自己的 Windows 计划任务**就是用它（`ok/util/windows_schedule.py:1175-1271`）。
3. **`ok-ww.exe -t DailyTask -e` 也能透传参数**（PyAppify `execute_python.rs:24` 把启动器 argv 追加到 Python 命令行），但启动器是否拉起脚本还受 `app.json` 的 `auto_start`/10 秒倒计时影响；**一键清日常建议直接启动 `pythonw.exe`**，保留 `ok-ww.exe` 仅用于「更新/打开启动器」。
4. **MAA（GUI）没有「跑完就退出」的官方 CLI，但有两条可靠路径**：① 全局热键 `LinkStart`（本机配置 = `Ctrl + Shift + Alt + L`，`gui.new.json → Gui.HotKeys`）触发任务队列；② 开启设置「启动后直接运行」（`Gui.StartUpSettings.RunDirectly`），MAA 启动后 10 秒倒计时自动 `LinkStart`（源码 `AsstProxy.cs:756-814`）。完成信号：`<MAA>\debug\gui.log` 追加 `任务已全部完成！`。
5. **MXU（MaaNTE / MaaEnd）有官方自启动 CLI**：`MaaNTE.exe/MaaEnd.exe --autostart --instance "<实例名>" --quit-after-run`；`-q` 会在本次触发自动执行且实例任务结束后退出（官方 README + 二进制帮助文本 + 前端逻辑三方一致）。**MaaEnd 本机已有可直接用的实例「全套日常」「快速日常」（含 LaunchGamePC 前置任务）**；MaaNTE 的实例「挂机任务」目前只启用了 1 个任务，需玩家先配置。
6. 四款脚本的前置条件、调用序列、完成判定、超时与降级见 §7 总表与 §8 逐游戏方案。

---

## 1. 基线：v0.6 现状与本机真实状态

### 1.1 Hub v0.6 配置（`GameHub/config.json`，version 4）

| 卡片 | `script_exe` | `script_procs` | `game_exe` | `game_procs` |
| --- | --- | --- | --- | --- |
| maa | `MAA-v5.1.0-win-x64/MAA.exe` | `MAA.EXE` | （空） | `ARKNIGHTS.EXE` |
| nte | `MaaNTE/MaaNTE.exe` | `MAANTE.EXE` | `D:\Neverness To Everness\NTELauncher.exe` | `HTGAME.EXE` |
| wuwa | `WuwaMAA/ok-ww/ok-ww.exe` | `OK-WW.EXE` | `E:\Wuthering Waves\launcher.exe` | `CLIENT-WIN64-SHIPPING.EXE` |
| maaend | `MaaEnd-win-x86_64-v2.33.0/MaaEnd.exe` | `MAAEND.EXE` | `E:\Hypergryph Launcher\Launcher.exe` | `ENDFIELD.EXE` |

- 游戏检测（v0.6 新增的 `gamehub/detector.py`）已经正确，问题集中在**「启动脚本」「启动游戏」两个按钮的语义**与**脚本进程识别**。
- `game_exe` 三项都指向**启动器**：鸣潮 `launcher.exe`、异环 `NTELauncher.exe`、终末地 `E:\Hypergryph Launcher\Launcher.exe`。这就是「只打开启动器」的直接原因（不只鸣潮）。
- `script_procs` 对 ok-ww 而言指向 **PyAppify 启动器** `OK-WW.EXE`，而脚本本体是 `pythonw.exe`（见 §2.3）。

### 1.2 本机实际安装/运行状态（只读核对）

| 项目 | 实际值 |
| --- | --- |
| ok-ww 启动器 | `D:\All MAA\WuwaMAA\ok-ww\ok-ww.exe`（PyAppify/Tauri） |
| ok-ww 正式脚本 | `...\ok-ww\data\apps\ok-ww\working\main.py`（`main.py` 仅 7 行：`OK(config).start()`） |
| ok-ww Python | `...\data\apps\ok-ww\python\pythonw.exe`，**Python 3.12.10**，内嵌 site-packages（PySide6 6.11.1 / psutil / pywin32 / onnxocr / opencv） |
| ok-ww 实例 | 本机**当前正在运行**：`pythonw.exe`(PID 42024) 命令行 = `"...\python\pythonw.exe" "...\working\main.py"`（无参数，由启动器拉起） |
| ok-ww 配置 | `working\configs\`（DailyTask.json / Basic Options.json / devices.json …），`devices.json` 保存 `pc_full_path = E:\Wuthering Waves\...\Client-Win64-Shipping.exe` |
| MAA | `D:\All MAA\MAA-v5.1.0-win-x64\MAA.exe`；WPF GUI + MaaCore；`config\gui.json`（旧格式）+ `config\gui.new.json`（新格式，v6.19.0）双写 |
| MAA 任务队列 | `gui.new.json → Configurations.Default.TaskQueue[]`：**仅 `自动肉鸽` 的 `IsEnable=true`**，日常任务全部未勾选（玩家需先配置） |
| MAA 热键 | `Gui.HotKeys = {"ShowGui":{"Key":"M","Modifiers":"Alt, Control, Shift"}, "LinkStart":{"Key":"L","Modifiers":"Alt, Control, Shift"}}` |
| MaaNTE | `D:\All MAA\MaaNTE`；MXU 前端；`config\mxu-MaaNTE.json` 实例：`挂机任务`（Win32-Background，**仅 FishNew 启用**），`autoRunOnLaunch=false`，`autoStartInstanceId` 未设置 |
| MaaEnd | `D:\All MAA\MaaEnd-win-x86_64-v2.33.0`；MXU 前端；`config\mxu-MaaEnd.json` 实例：`全套日常`（14 任务启用，含 `__MXU_PRETASK__LaunchGamePC`）、`快速日常`（6 任务）、`实时辅助`（1 任务） |
| MAA PC 客户端 | `E:\Arknights bilibili\games\Arknights Game\Arknights.exe`（Unity） |
| 终末地 PC 客户端 | `E:\Hypergryph Launcher\games\Endfield Game\Endfield.exe`（Unity） |

---

## 2. A. ok-ww：启动链、CLI 自动执行、配置与完成信号

### 2.1 启动链全貌（PyAppify 启动器 → 正式脚本）

```
ok-ww.exe (PyAppify/Tauri: 启动器+更新器)
  └─ 读取 pyappify.yml / data/apps/ok-ww/app.json（profiles.China: admin=true, use_pythonw=true）
  └─ execute_python::run_python_script(...)
       exe   = data/apps/ok-ww/python/pythonw.exe
       args  = [working\main.py] + 启动器自身命令行参数（execute_python.rs:24 `args.extend(std::env::args().skip(1))`）
       cwd   = data/apps/ok-ww/working
       env   = 清理 PYTHON*（utils/process.rs clear_python_envs）+ 注入 PYAPPIFY_*
  └─ main.py → from config import config; OK(config).start()
```

同时 PyAppify 会生成一个 `.pyappify-shortcut.py`（**仅用于桌面/开始菜单快捷方式**，不是运行时链路），其内容（`.pyappify-shortcut.py:1-62`）给出了「干净环境」的完整定义：

- 清除 `PYTHONHOME/PYTHONSTARTUP/VIRTUAL_ENV/PYTHONPATH/PYTHONUSERBASE/PYTHONCASEOK/PYTHONHASHSEED/PYTHONOPTIMIZE/PYTHONVERBOSE/PYTHONDEBUG/PYTHONWARNINGS/PYTHONIOENCODING/PYTHONINSPECT`（第 5-6 行）
- `PATH` 仅保留系统目录（第 8-15 行）；`PYTHONNOUSERSITE=1`、`PYTHONIOENCODING=utf-8`、`PYTHONUNBUFFERED=1`（16-18 行）
- 主脚本绝对路径 + `subprocess.run([sys.executable, _main_script])`（24、55 行）

**证据强度**：★★★（本地源码 + PyAppify 官方源码 `src-tauri/src/execute_python.rs:12-49`、`app_service.rs:1509-1614`）。

### 2.2 绕过启动器直接启动正式脚本（推荐用于一键清日常）

**正确命令（已由 ok-ww 自己使用，强证据）**：`ok/util/windows_schedule.py:1175-1271` 生成 Windows 计划任务 XML：

```xml
<Exec>
  <Command>{python_exe}</Command>            <!-- sys.executable = ...\python\pythonw.exe -->
  <Arguments>main.py -t {task} -e</Arguments><!-- task_identifier 或数字序号；auto_exit 默认 true -->
  <WorkingDirectory>{working_directory}</WorkingDirectory>
</Exec>
<RunLevel>HighestAvailable</RunLevel>
<MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
```

即 Hub 直接调用：

```bat
rem 工作目录 = ...\data\apps\ok-ww\working，管理员权限
"...\data\apps\ok-ww\python\pythonw.exe" "...\data\apps\ok-ww\working\main.py" -t DailyTask -e
```

ShellExecute 版本（提权，Hub 实现用）：

```python
ctypes.windll.shell32.ShellExecuteW(
    None, "runas",
    r"D:\All MAA\WuwaMAA\ok-ww\data\apps\ok-ww\python\pythonw.exe",
    r'"D:\All MAA\WuwaMAA\ok-ww\data\apps\ok-ww\working\main.py" -t DailyTask -e',
    r"D:\All MAA\WuwaMAA\ok-ww\data\apps\ok-ww\working",
    1)
```

**环境变量**：
- 必须保证 cwd = `working`（`config.py` 中 `assets/…`、`configs`、`logs/…`、`data` 均为相对路径；`_ok.json` 也在 configs）。
- 建议清理 `PYTHONHOME/PYTHONPATH` 等（同 §2.1），设置 `PYTHONNOUSERSITE=1`、`PYTHONIOENCODING=utf-8`、`PYTHONUNBUFFERED=1`。
- `PYAPPIFY_*` 系列**可选**：缺失时 `pyappify.app_version=None`、launcher 选项隐藏（`GlobalConfig.create_app_launcher_options` 会优雅返回 None，d:\...\working\ok\util\GlobalConfig.py:348-369），不影响任务执行；ok-ww 自己的计划任务也不设置这些变量（★★★）。
- 想保留启动器元数据（版本显示、`open launcher` 按钮）可注入：`PYAPPIFY_APP_JSON_PATH=<app>\data\apps\ok-ww\app.json`、`PYAPPIFY_APP_VERSION=app.json.current_version`、`PYAPPIFY_APP_PROFILE=China`、`PYAPPIFY_EXECUTABLE=<app>\ok-ww.exe`。
- **管理员权限是硬需求**：`ok/device/DeviceManager.py` → `ok/core/start_controller.py:183-188` 在需要启动游戏且非管理员时弹窗要求重启（★★★）。Hub 提权启动可避免人工点「Yes」。

**代价/风险**（相对走启动器）：
1. 不触发 PyAppify 的更新检查与更新；Hub 应另设「更新」按钮走 `ok-ww.exe`（`store.launch_updater` 已按此设计）。
2. 不更新 `app.json` 的 `running`/`last_start`；启动器 UI 显示可能滞后（无功能影响）。
3. 丢失 PyAppify 的崩溃对话框抑制；ok-ww 自身日志仍在 `working\logs\ok-script.log`。
4. Defender 白名单提示不出现（安装时已处理则无影响）。
5. **单实例互斥**：`ok/util/process.py:235-300` 以 **cwd 的 md5** 命名 mutex，若已有同 cwd 实例会等待 5s 后强杀旧实例（★★★）。Hub 启动前必须先判 `launch_spec_running`，避免杀掉正在跑的任务。

### 2.3 为什么脚本进程不是 `OK-WW.EXE`

- 启动器在脚本窗口显示后会被 ok-ww 主动关闭：`Basic Options.json → "Kill Launcher After Start": true`，对应 `MainWindow.showEvent` 中 `request_pyappify_shutdown()`（`ok/ui/qt/MainWindow.py:577-579`，该配置项常量见 `ok/util/GlobalConfig.py:16`）。
- 因此 Hub 用 `OK-WW.EXE` 判断「脚本运行中」会在几秒后变假；**正确做法是按 exe 完整路径判定** `...\data\apps\ok-ww\python\pythonw.exe`（Hub v0.7 工作区已在做的 `launch_running_pids` 正是这个思路，`gamehub/store.py:1573-1602`）。
- 检测不到路径时应判定「未知」而非「未运行」，否则用户其它 `pythonw.exe` 会造成误判（工作区测试用例已覆盖，`tools/test_launch_spec.py:200-230`）。

### 2.4 CLI 参数（官方文档 + 源码）

`working/README.md`「命令行参数」原文（★★★，对应 GitHub `ok-oldking/ok-wuthering-waves` README）：

```bash
# 示例：启动后自动执行第一个任务（一条龙），并在任务完成后退出程序
ok-ww.exe -t 1 -e
```

`ok/util/process.py:571-609` 定义：

| 参数 | 含义 | 解析 |
| --- | --- | --- |
| `-t, --task` | 要执行的任务：1-based 序号 / 任务名 / 类名（也支持 `模块.类名`） | `parse_arguments_to_map` 数字转 int，其余保持字符串 |
| `-e, --exit` | 任务成功后退出程序（并关闭游戏） | `exit_after=True` |
| `-h, --headless` | 无 UI 启动 | `use_gui=False` |

任务解析（`ok/__init__.py:963-1008` `get_onetime_task` / `find_task_by_name`）：
数字 → `onetime_tasks[n-1]`；字符串 → 先按 `模块.类名` 精确匹配，再按「任务名或类名」精确/包含匹配（`📅 Daily Task` 的类名是 `DailyTask`，`-t DailyTask` 可用）。

**one-time 任务列表与顺序**（`working/config.py:262-274`，数字序号即此顺序）：

| # | 类名 | 说明 |
| --- | --- | --- |
| 1 | `DailyTask` | 每日任务（登录、月卡、刷本、领奖），**一键清日常用这个** |
| 2 | `FarmEchoTask` | 刷声骸 |
| 3 | `NightmareNestTask` | 无妄者巢穴 |
| 4 | `TacetTask` | 无音区 |
| 5 | `ForgeryTask` | 锻造 |
| 6 | `SimulationTask` | 模拟领域 |
| 7 | `MultiAccountDailyTask` | 多账号日常 |
| 8 | `MergeEchoTask` / 9 `EnhanceEchoTask` / 10 `ChangeEchoTask` / 11 `GardenTask` | 声骸合成/强化/转换、庭院 |

> 建议 Hub 用 `-t DailyTask`（类名稳定，不随顺序变化），不要用 `-t 1`。

### 2.5 启动后如何开始每日任务（内部链路）

1. `main.py` → `OK(config)`（`ok/__init__.py:662-744`）→ `ok.start()`（`ok/__init__.py:764-806`）。
2. Qt 模式下 `MainWindow.showEvent` → `og.ok.start_runtime()`（`ok/ui/qt/MainWindow.py:576`）。
3. `start_runtime()`（`ok/__init__.py:808-842`）：
   - 有 `-t` 参数 → `app.start_controller.start(task, exit_after=args.exit)`；
   - 否则若 `Basic Options → "Auto Start Game When App Starts"` → `start_controller.start()`；
   - 否则只刷新设备。
4. `start_controller.do_start`（`ok/core/start_controller.py:49-126`）：刷新设备 → `start_device()`（必要时启动游戏）→ `_mark_task_enabled(task)` → `og.executor.start()`。
5. `TaskExecutor.execute()`（`ok/task/TaskExecutor.py:547-615`）：只执行 `onetime_task.enabled` 的任务；任务结束后 `task.disable()` → `communicate.task_done`；若 `task.exit_after_task`（`-e` 或配置 `Exit After Task`）→ 日志 `Successfully Executed Task, Exiting Game and App!` → `device_manager.stop_hwnd()`（**kill 游戏 exe**，`ok/device/DeviceManager.py:126-130`）→ `communicate.quit` → 程序退出。
6. 「每日任务-开始」按钮的 GUI 链路（仅作兜底参考）：`TaskCard.start_clicked` → `og.app.start_controller.start(self.task)`（`ok/ui/qt/tasks/TaskCard.py:118-138`）。

### 2.6 配置文件结构（`working/configs/`）

| 文件 | 作用 | 例子 |
| --- | --- | --- |
| `Basic Options.json` | 全局开关：`Auto Start Game When App Starts`、`Kill Launcher After Start`、`Exit App when Game Exits`、`Start/Stop`（热键，默认 F9）、`Game Package` 等 | 本机 `Auto Start Game When App Starts=false` |
| `DailyTask.json` | 每日任务参数：`Which to Farm` / `Which Tacet Suppression to Farm` / `Farm Nightmare Nest for Daily Echo` / `Additional Tasks to Run After Daily Task` / `Exit After Task` | 本机 `Exit After Task=false`（命令行 `-e` 可覆盖） |
| `devices.json` | 上次设备：`pc_full_path`、`selected_hwnd`、`selected_exe`、`interaction` | 本机已保存 `Client-Win64-Shipping.exe` |
| `schedule_tasks_cache.json` | ok-ww「定时任务」缓存（Windows 计划任务） | 本机 `{}` |
| `_ok.json` | 窗口位置/尺寸等 UI 状态 | — |
| 其余 `*.json` | 各 one-time / trigger 任务参数 | `AutoCombatTask.json` 等 |

### 2.7 定时任务（可作为「每天自动清」的备选，不是 Hub 主路径）

`ok/util/windows_schedule.py`（57KB）用 **Windows Task Scheduler COM API** 注册计划任务：
- 任务 XML 见 §2.2；`<Arguments>main.py -t <identifier> -e</Arguments>`、`<WorkingDirectory>working</WorkingDirectory>`、`RunLevel=HighestAvailable`、`MultipleInstancesPolicy=IgnoreNew`（1233-1270 行）。
- 触发器支持 Daily/Weekly/Monthly/Once/自定义间隔（TriggerType，40-46 行）。
- 结论：**ok-ww 官方认可的「无人值守」方式就是「pythonw + main.py -t … -e」**；Hub 的调用与之完全同构，风险最低。

### 2.8 若只能 GUI 自动化（降级方案）

- 窗口：ok-ww 主窗口标题 = `OK-WW`（`config.py:255 gui_title`），类名由 Qt 决定（通常 `Qt5158QWindowIcon` 之类；**不保证稳定**，★★）。
- **控件不可通过 Win32 `EnumChildWindows`/`SendMessage` 操作**：PySide6/Qt 自绘控件没有独立 HWND（★★，Qt 通用行为）。可用的替代：
  1. **全局热键**：`Start/Stop`（默认 `F9`）由 `RegisterHotKey(None, 999, 0, VK)` 注册（`ok/ui/qt/start/StartCard.py:132-140`），`SendInput` 发 F9 即可暂停/开始（**但它等价于点顶部 Start，不会指定 DailyTask**，`og.app.start_controller.start()` 无 task 参数，`StartCard.clicked` 65-70 行）。
  2. UI Automation（Qt 的 Windows UIA 桥）或坐标点击：需先 `SetProcessDPIAware`、`GetClientRect` 计算 DPI 缩放，窗口位置来自 `configs/_ok.json`（`window_x/y/width/height`）；风险高（语言/主题/分辨率变化即失效）。
- 结论：**不要用 GUI 自动化做「一键清日常」**，仅在 CLI 全失败时给用户「打开脚本界面」按钮。

---

## 3. B. MAA（明日方舟 GUI）：启动自动运行与调用方案

### 3.1 配置键与存储位置（本机 v6.19.0 实测）

MAA 同时维护两份配置（同级 mtime，双写）：

| 文件 | 格式 | 关键路径 |
| --- | --- | --- |
| `MAA\config\gui.new.json` | 新格式（当前生效） | `Configurations.<配置名>.TaskQueue[]`（含 `IsEnable`）、`Configurations.<配置名>.Gui.StartUpSettings`、`Configurations.<配置名>.Gui.RuntimeSettings`、`Gui.HotKeys`、`Gui.MinimizeOnStartup`、`Timers` |
| `MAA\config\gui.json` | 旧格式（兼容/迁移） | `Start.RunDirectly`、`Start.StartEmulator`、`Start.EmulatorPath`、`Start.OpenEmulatorAfterLaunch`、`Connect.*`、`TaskQueue.Order.*`、`TaskQueue.*.IsChecked`、`Global.HotKeys`（JSON 字符串） |

`StartUpSettings`（`gui.new.json`，本机值，★★★）：

```json
{
  "RunDirectly": false,                       // 启动后直接运行任务（核心开关）
  "SkipStartupAutoRunAfterUpdate": true,      // 更新后立即重启时不自动运行
  "StartEmulator": false,                     // 启动时拉起模拟器
  "RestartEmulatorWhenAdbFailed": false,
  "EmulatorPath": "C:\\Users\\he146\\Desktop\\明日方舟.lnk",
  "EmulatorAddCommand": "",
  "EmulatorWaitSeconds": 60,
  "StartPcClient": false,                     // 启动时拉起 PC 客户端
  "RestartPcClientWhenConnectFailed": false,
  "PcClientPath": "",
  "PcClientAddCommand": "",
  "PcClientWaitSeconds": 60
}
```

`RuntimeSettings`：`ClientType: "Bilibili"`、`StartGame: true`（开始唤醒时启动游戏）、`PreRunScript/PostRunScript` 等。
`TaskQueue`（本机）：9 项任务，**仅 `自动肉鸽` IsEnable=true**；日常类任务（开始唤醒/自动公招/基建换班/信用收支/理智作战/剩余理智/领取奖励）均未勾选。

### 3.2 「启动后直接运行」的真实逻辑（源码实锤）

`MaaAssistantArknights/src/MaaWpfGui/Main/AsstProxy.cs:756-814`（GitHub `dev-v2` 分支，★★★）：

```csharp
bool runDirectly = SettingsViewModel.StartSettings.RunDirectly;
bool isPcConnection = SettingsViewModel.ConnectSettings.IsPCConnectConfig;
bool openConnectionTarget = isPcConnection
    ? SettingsViewModel.StartSettings.OpenPcClientAfterLaunch
    : SettingsViewModel.StartSettings.OpenEmulatorAfterLaunch;

if (Bootstrapper.ShouldSkipStartupAutoRun) { /* --skip-startup-auto-run */ return; }

// 会自动开任务或连接目标时，先给 10 秒反悔倒计时（不强制拉起主窗口）
if (runDirectly || openConnectionTarget) { await ConfirmStartupAutoRunAsync(..., seconds: 10); }

await Task.Run(() => SettingsViewModel.StartSettings.TryToStartConnectionTarget(true)); // 起模拟器/PC 客户端
if (runDirectly) { await Instances.TaskQueueViewModel.LinkStart(); }                    // 起任务队列
```

跳过条件（同文件 734-754）：资源损坏、需要重启、Demo 模式、`--skip-startup-auto-run`。
⇒ **MAA 启动后确实可以自动执行玩家预设的任务队列**，前提是 `RunDirectly=true` 且任务已勾选。

### 3.3 CLI 参数（`MAA.dll` 字符串 + `Bootstrapper.cs`）

| 参数 | 语义 | 证据 |
| --- | --- | --- |
| `--config <配置名>` | 启动时切换到指定配置；**Config 内部可能重启进程** | `Bootstrapper.cs:490-494`（★★★） |
| `--skip-startup-auto-run` | 跳过「启动后直接运行/启动模拟器/PC 客户端」 | `Bootstrapper.cs:498-509`、`MAA.dll` `--skip-startup-auto-run`（★★★） |
| `--keep-awake [分钟]` | 保持唤醒（定时唤醒链用） | `Bootstrapper.cs:511-520` |
| `--instance <n>` / `--mutex-name` / `--demo` / `--shots` / `--no-progress-ui` / `--show-console` / `--skip-core-init` | 多实例/调试/截图等 | `MAA.dll` 字符串（★★） |

**单实例行为**：`Bootstrapper.HandleMultipleInstances()`（854-970 行）检测到已有实例时**只发送激活信号**把窗口提前，不会转发「开始任务」；再次启动 `MAA.exe` 也无法触发任务（★★★）。

### 3.4 任务队列存储

- 新格式：`gui.new.json → Configurations.<当前配置>.TaskQueue[]`，每项形如
  `{"$type":"StartUpTask", "TaskType":"StartUp", "Name":"开始唤醒", "IsEnable": false, ...}`（含各任务参数，如 `FightTask.StagePlan`、`RecruitTask.MaxTimes`）。
- 旧格式：`gui.json → Configurations.<配置>.TaskQueue.Order.<TaskName>` + `TaskQueue.<TaskName>.IsChecked`（迁移兼容）。
- 配置切换：`--config <name>`；每个配置有独立任务队列。
- 另：`Timers.List[]` 存 8 个定时启动槽（`Hour/Minute/IsEnabled/Config`），`Timers.ForceScheduledStart/ScheduledWakeUp` 等。

### 3.5 三种「让 MAA 启动即执行日常」的方案

| 方案 | 做法 | 优点 | 缺点/风险 |
| --- | --- | --- | --- |
| **B1 热键触发（推荐）** | Hub 启动 `MAA.exe --skip-startup-auto-run`（避免不可控自动运行）→ 等 MAA 就绪 → `SendInput` 发送 `LinkStart` 热键 | 不改用户配置；MAA 已在运行也能用 | 依赖热键已启用/注册成功；键盘被其它程序占用时失败 |
| B2 启动后直接运行 | 用户（或 Hub 一次性）把 `StartUpSettings.RunDirectly=true`；Hub 直接启动 `MAA.exe` | 调用最简单；与 MAA 官方「开机自启」同源 | 10 秒倒计时用户可取消；会连带 `StartEmulator/StartPcClient`；改配置需备份 |
| B3 MAA 定时任务 | 用 MAA `Timers` 设定每天时间点 | 不依赖 Hub 常驻 | 与「Hub 一键」交互弱，用户时间固定 |

**热键细节（B1）**：
- 本机 `LinkStart = Alt + Ctrl + Shift + L`（`gui.new.json → Gui.HotKeys.LinkStart`）；旧格式见 `gui.json → Global.HotKeys`（JSON，含 Key/Modifiers 数字）。
- MAA 用 `GlobalHotKey.dll` 注册系统级热键（`MaaWpfGui` / `GlobalHotKey` 字符串，★★）；注册失败有 `HotKeyLinkStartRegistrationFailed` 日志/setting。**系统级热键无需 MAA 窗口前台**，Hub 用 `keybd_event/SendInput` 即可（★★，需实测一次）。
- Hub 读取配置建议：优先 `gui.new.json → Gui.HotKeys.LinkStart`（`Key` 单字符 + `Modifiers` 逗号串），回退旧 `gui.json → Global.HotKeys`；若热键缺失/为 `None` → 降级到 B2 或提示用户。

### 3.6 模拟器 vs PC 客户端差异

| 维度 | 模拟器（ADB） | PC 客户端（Win32 AttachWindow） |
| --- | --- | --- |
| 配置 | `Gui.ConnectSettings.Config = MuMuEmulator12`；`AdbPath`、`Address`（本机 `127.0.0.1:16384`）、`AddressHistory`（`gui.json.old:10-33`） | `ConnectConfig = PC`、`UseAttachWindow=true`；`StartUpSettings.PcClientPath` 指向 `Arknights.exe`/快捷方式 |
| 「启动游戏」 | `RuntimeSettings.StartGame=true` → MAA 用 `am start -n <pkg>/com.u8.sdk.U8UnityContext`（`resource/config.json:46-53,77-78`） | `StartUpSettings.StartPcClient=true` 时 MAA 自行启动 PC 客户端；否则需用户先开客户端，MAA 按窗口标题 `明日方舟` attach |
| 权限 | 普通权限即可（ADB） | 建议管理员（输入方式 `PostMsg`/`Seize`；MAA 文案推荐 `PostMsg-WindowPos`） |
| 前置 | 模拟器已开（本机 `StartEmulator=false`，需用户先开 MuMu），ADB 可连 | PC 客户端已开或 `StartPcClient=true`；窗口标题必须存在 |

---

## 4. C. MXU（MaaNTE / MaaEnd）：`--autostart` 语义与完成信号

### 4.1 官方 CLI（MXU README + 二进制帮助文本 + MaaNTE/MaaEnd 实测字符串，★★★）

`MistEO/MXU` README「命令行参数」与 `MaaNTE.exe` 内嵌中文帮助完全一致：

| 参数 | 功能 |
| --- | --- |
| `-h/--help` | 显示帮助并退出（不启动 GUI） |
| `--autostart` | 标记为「开机自启动」启动，进入自启动模式并触发自动执行逻辑 |
| `-i/--instance <实例名>` | 指定自动执行使用的实例（仅 `--autostart` 下生效；支持 `-i=<名>`、`--instance=<名>`） |
| `-q/--quit-after-run` | 当本次启动实际触发自动执行后，等待任务结束并自动退出 MXU |

示例：`mxu.exe --autostart -i "日常任务" --quit-after-run`。

### 4.2 实例名存储

`<安装目录>\config\mxu-<ProjectName>.json` → `instances[].name`：

| 项目 | 文件 | 实例 |
| --- | --- | --- |
| MaaNTE | `D:\All MAA\MaaNTE\config\mxu-MaaNTE.json` | `挂机任务`（controller `Win32-Background`，仅 `FishNew` enabled） |
| MaaEnd | `D:\All MAA\MaaEnd-win-x86_64-v2.33.0\config\mxu-MaaEnd.json` | `全套日常`（14 enabled，含 `__MXU_PRETASK__LaunchGamePC`）、`快速日常`（6）、`实时辅助`（1） |

同一文件还有：`settings.autoRunOnLaunch`（本机均 false）、`settings.autoStartInstanceId`（未设置）、`instances[].savedDevice`（存档窗口/进程路径）、`instances[].tasks[]`（`taskName` + `enabled` + `optionValues`）、`instances[].preActions[]`（可执行程序，MaaNTE 有一条被禁用的「启动 HTGame.exe」）。

### 4.3 `--autostart` 实际触发逻辑（前端 JS，★★★）

`MaaNTE.exe` / `MaaEnd.exe` 内嵌前端代码：

1. 启动时 Rust 命令 `is_autostart` 返回真 → `setIsAutoStartMode(true)`；
2. `get_start_instance` 返回 `--instance` 的名字 → 在 `instances[]` 中按**名字**查找（找不到只 warning，随后回退 `autoStartInstanceId`；两者都没有则**不会触发**，只是打开界面）；
3. 条件 `(isAutostart || autoRunOnLaunch) && 实例存在` → 设置 active instance；
4. 若 `has_quit_after_run_flag()`：订阅该实例 `isRunning`，**从 true 变 false 时执行 `exit(0)`**；
5. 500ms 后 `document.dispatchEvent(new CustomEvent("mxu-start-tasks", {source:"autostart"}))` → 复用界面「开始任务」同一逻辑（自动连接 → 加载资源 → 执行该实例已启用任务）。

⇒ 结论：
- `--autostart` **不依赖** `autoRunOnLaunch`；它等价于「点该实例的开始按钮 + 开机自启模式」。
- `-q` 的退出条件 = 「本次确实触发了自动执行」且「实例从运行变为停止」；成功/失败/手动停止都会退出，**退出码固定 0**（★★★）。
- 实例名必须精确匹配（含空格/中文）。

### 4.4 MaaEnd 是否支持

是：`MaaEnd.exe` 含同一套命令 `get_start_instance` / `is_autostart` / `has_quit_after_run_flag` / `mxu-start-tasks` / `autoStartInstanceId`（二进制字符串逐项核对，★★★；MaaEnd 也是 MXU 前端）。
MaaNTE 与 MaaEnd 的 CLI 帮助文本相同（二进制内嵌，★★★）。

### 4.5 如何知道任务完成

| 信号 | 可用性 | 说明 |
| --- | --- | --- |
| **进程退出（`-q`）** | ★★★ 主信号 | `has_quit_after_run_flag` → 实例 `isRunning` 落下 → `exit(0)` |
| 退出码 | ★★★ 但无区分 | 成功/失败均 0 |
| MXU 日志 | ★★ | `debug\mxu-tauri.log`（Rust 侧，含 `tasks-completed` 事件流字符串）、`debug\YYYY-MM-DD-N.log`（应用日志，`[Task]` 前缀）；本机今日日志无任务记录，未能实测完成关键字 |
| 实例任务状态（IPC/UI） | ★ | Tauri IPC 事件 `task-progress` / `tasks-completed`，外部无法直接订阅 |
| 游戏窗口/进程消失 | ★★ | 任务结束后 MXU 通常不主动关游戏，不可靠 |

**建议**：以「MXU 进程退出」为完成信号；成功与否用「日志中是否有失败/异常 + 用时是否异常短」启发式判断，UI 文案用「已完成（未校验）」；超时则提示用户。

### 4.6 前置条件

- **MaaNTE**：实例任务需玩家预先配置（本机仅 1 个任务）；游戏需先运行（实例无 LaunchGamePC 前置；可让 Hub 先启动 `HTGame.exe` 并等窗口，或用实例里那条被禁用的 preAction）。
- **MaaEnd**：实例「全套日常」已含 `__MXU_PRETASK__LaunchGamePC` → MXU 会自动拉起鹰角启动器/游戏；若启动器无法定位会报 `不一致无法找到启动器`（go-service 字符串），需在任务设置里手填启动器路径。
- **权限**：两个项目的 Win32 controller 均声明 `"permission_required": true`（`MaaNTE/interface.json:25`、`MaaEnd/interface.json:31`），**建议 Hub 以管理员启动 MXU**。

---

## 5. D. 四游戏「一键清日常」推荐方案

### 5.1 总表

| 游戏 | 推荐调用（管理员） | 完成判定 | 默认超时 | 失败/降级 |
| --- | --- | --- | --- | --- |
| **鸣潮 ok-ww** | `pythonw.exe "<working>\main.py" -t DailyTask -e`（cwd=working）；可选启动器：`ok-ww.exe -t DailyTask -e` | pythonw 进程退出 + 日志 `Successfully Executed Task, Exiting Game and App!`（`working\logs\ok-script.log`，`-e` 时约 10s 延迟后退出） | 90 min | 进程退出但无成功标记 → 读日志尾部报错并提示「打开脚本界面」；超时 → 先提示，用户确认后再结束进程（`-e` 失败不会退出，需停止） |
| **明日方舟 MAA** | `MAA.exe --skip-startup-auto-run`（可选 `--config "<配置名>"`）→ 等就绪 → 发 `LinkStart` 热键（本机 `Ctrl+Shift+Alt+L`） | `MAA\debug\gui.log` 追加 `任务已全部完成！`；失败 `任务出错: X`；停止 `已停止` | 120 min | 热键失败/未配置 → 引导开启「启动后直接运行」后重启 MAA，或提示手动点开始；MAA 已在运行时直接发热键 |
| **悠米 MaaNTE** | 先确保 `HTGame.exe` 在运行（Hub 启动并等窗口）→ `MaaNTE.exe --autostart --instance "挂机任务" --quit-after-run` | MaaNTE 进程退出（`-q`） | 120 min | 实例名不存在 → 打开 MXU 让用户选择/配置；退出即视为结束（不区分成败，日志启发式） |
| **终末地 MaaEnd** | `MaaEnd.exe --autostart --instance "全套日常" --quit-after-run`（pretask 自动拉起游戏） | MaaEnd 进程退出（`-q`） | 150 min | 实例名不存在/启动器路径不对 → 提示到 MaaEnd 任务设置；超时提示 |

### 5.2 队列与并发

- **串行**：四款脚本都会抢占鼠标/前台（MaaNTE/MaaEnd Win32-Front 会 Seize；ok-ww 亦需前台输入），且游戏对 GPU 独占。Hub 的「一键清日常」= 顺序队列，一次只跑一个。
- 启动前互斥检查：目标脚本是否已在跑（`launch_spec_running` / 进程名）；游戏是否已在跑（v0.6 detector 状态）。已在跑 → 询问「复用现有实例继续」还是「中止」。
- 结束/失败后：等待对应脚本进程真正退出（ok-ww 有 ~10s 收尾；MXU 退出后可能残留 agent 子进程，需再等 3-5s）再启动下一项。
- 每项记录：开始时间、PID、日志文件当前偏移、结束原因（success/failed/timeout/stopped）。
- 全局取消：用户点「停止」→ 各脚本都没有「优雅停止」CLI：ok-ww 无停止参数（只能结束进程，进程被杀后由游戏自行退出或用户手动关）；MAA 的 `LinkStart` 热键只负责**开始**，停止只能在 MAA 界面点「停止」或 `taskkill`；MXU 直接结束进程即可（`-q` 的 exit 订阅不会触发，但任务随进程终止）。默认策略：只在超时且用户确认后 `taskkill`。

### 5.3 逐游戏调用序列与前置条件

#### 1) 鸣潮 —— ok-ww（修复后）

```
前置：
  - ok-ww 正式脚本存在：<ok-ww>\data\apps\ok-ww\working\main.py、python\pythonw.exe
  - 玩家已在 ok-ww 里配置好 DailyTask（configs\DailyTask.json）并至少成功跑过一次
  - 管理员权限（启动游戏/输入需要）
调用：
  1. 若「脚本运行中」→ 打开其窗口或询问是否复跑
  2. 若无管理员：ShellExecuteW(runas) 启动 pythonw + main.py + -t DailyTask -e（cwd=working）
  3. 记录 logs\ok-script.log 当前大小
完成：
  - pythonw 进程消失（按 exe 路径判定）
  - 成功：日志尾部出现 "Successfully Executed Task, Exiting Game and App!"（约 10s 前）
  - 失败/超时：日志尾部 ERROR / 进程存活超过 90min
```

> 不推荐用 `ok-ww.exe` 作为一键入口：它是否立刻拉起脚本取决于 `app.json.auto_start` 与 10 秒倒计时（PyAppify 行为），Hub 无法保证；且启动器会在脚本起来后自己退出，造成「脚本状态」误判。

#### 2) 明日方舟 —— MAA

```
前置：
  - MAA 连接配置正确（本机 MuMu12 / 127.0.0.1:16384，或 PC 客户端 AttachWindow）
  - 任务队列已勾选日常任务（本机当前只有「自动肉鸽」，需玩家先配置；建议单独建「日常」配置）
  - 若用热键：Gui.HotKeys.LinkStart 已启用（本机 Ctrl+Shift+Alt+L）
调用（B1）：
  1. 若 MAA 未运行：ShellExecuteW(runas 可选) MAA.exe --skip-startup-auto-run [--config "<配置名>"]
  2. 等主窗口出现 / gui.log 出现 "MaaAssistantArknights GUI started"
  3. 记录 gui.log 大小 → SendInput 发送 LinkStart 热键（Alt+Ctrl+Shift+L）
  4. 轮询 gui.log 追加内容
完成：
  - "任务已全部完成！" → success
  - "任务出错: " / "已停止" / "正在停止……" → failed/stopped
  - 超时 120min
降级：
  - 热键未注册（HotKeyLinkStartRegistrationFailed）→ 引导开启「启动后直接运行」并重启 MAA（B2），
    或 UI 提示「请手动点击开始」；不要在 MAA 运行时重复启动 exe（只会激活窗口）
```

#### 3) 异环 —— MaaNTE

```
前置：
  - 实例「挂机任务」的任务已配置为日常（本机仅 FishNew，需玩家补齐）
  - 游戏已运行（实例无 LaunchGamePC 前置）→ Hub 先启动 HTGame.exe（或 NTELauncher.exe）并等窗口
  - 管理员（Win32 controller permission_required）
调用：
  1. 若 HTGame.exe 未运行：启动 D:\Neverness To Everness\Client\WindowsNoEditor\HT\Binaries\Win64\HTGame.exe
     并等待「UnrealWindow + 异环」窗口就绪（复用 v0.6 detector）
  2. ShellExecuteW(runas) MaaNTE.exe --autostart --instance "挂机任务" --quit-after-run
完成：
  - MaaNTE 进程退出（-q）→ 视为结束；用日志启发式判断成败
超时：120min；超时提示用户，必要时结束 MaaNTE 进程
```

#### 4) 终末地 —— MaaEnd

```
前置：
  - 实例「全套日常」/「快速日常」已存在（本机已有）
  - 鹰角启动器可被 go-service 定位（registry Software\Hypergryph\Endfield 或任务设置手填路径）
  - 管理员
调用：
  1. （可选）确认 Endfield.exe / 鹰角启动器未在跑；已在跑则跳过启动
  2. ShellExecuteW(runas) MaaEnd.exe --autostart --instance "全套日常" --quit-after-run
     （实例内含 __MXU_PRETASK__LaunchGamePC，会自动拉起启动器/游戏）
完成：
  - MaaEnd 进程退出（-q）
超时：150min；失败提示到 MaaEnd 的启动器路径设置
```

### 5.4 Hub 侧实现要点（与当前工作区衔接）

- 当前工作区 `gamehub/store.py` 已实现 `build_okww_launch/launch_app/launch_running_pids/launch_spec_running`（未提交）；`launch_app` 已支持 `spec["args"]`（`store.py:1537`），**每天任务只需把 `["-t","DailyTask","-e"]` 写进 args**。
- 缺口 1：**提权**。`launch_app` 目前用 `subprocess.Popen`（1542-1546），从非管理员 Hub 启动的 pythonw 不会触发 UAC，ok-ww 会弹「PC version requires admin privileges」模态框（`MainWindow.py:487-496`），破坏无人值守。建议给 spec 增加 `"elevate": true`，用 `ShellExecuteW(None,"runas", exe, 参数串, cwd, 1)`；代价是无法用 ShellExecute 注入 env，但 ok-ww 的官方计划任务同样不注入 env（§2.2），可接受。
- 缺口 2：**完成判定**。建议在 `store` 新增 `launch_log_path(app)` 与 `watch_log(text, offset, patterns)`；ok-ww 用 `working\logs\ok-script.log`、MAA 用 `debug\gui.log`、MXU 用进程退出。
- 缺口 3：**MAA 热键发送**。`SendInput` 发送 Alt+Ctrl+Shift+L（读 `gui.new.json`）；失败回退提示。
- 缺口 4：**MXU 启动**。给 MaaNTE/MaaEnd 卡片增加 `daily` 配置（实例名 + 可选管理员），复用 `launch_exe` 扩展为带参数与 runas。
- 缺口 5：**game_exe 修正**（与脚本入口分开）：
  - wuwa：`E:\Wuthering Waves\Wuthering Waves Game\Wuthering Waves.exe`
  - nte：`D:\Neverness To Everness\Client\WindowsNoEditor\HT\Binaries\Win64\HTGame.exe`
  - maaend：`E:\Hypergryph Launcher\games\Endfield Game\Endfield.exe`（或保留启动器但要说明会先开启动器）
  - maa：PC 客户端 `E:\Arknights bilibili\games\Arknights Game\Arknights.exe`（若走模拟器则留空，由 MAA 负责）
- UI 建议：卡片增加「▶ 一键清日常」（走 daily 队列）与「打开脚本」（现有 launch，保留人工操作）；「更新」保持走启动器 exe。

---

## 6. E. 原理总结（含引用）

### 6.1 MAA / MaaFramework

- **MAA GUI**（`MAA.exe`，WPF/.NET，本机 v6.19.0）：负责连接配置、任务队列、热键、定时、UI；通过 P/Invoke 调 `MaaCore.dll`。任务 = 「识别（OCR/模板匹配）→ 动作（点击/滑动）」的 pipeline 循环；连接层分 `MaaAdbControlUnit`（ADB，含 MuMu/LD/BlueStacks 扩展）与 `MaaWin32ControlUnit`（窗口 attach）。仓库：https://github.com/MaaAssistantArknights/MaaAssistantArknights （GUI 源码 `src/MaaWpfGui/...`，文档 `docs/zh-cn/manual/`）。
- **MaaFramework** 是 MAA 的底层自动化框架（PI V2 协议：`interface.json` 的 controller/task/resource/option）；MXU 与 MaaNTE/MaaEnd 都基于它：https://github.com/MaaXYZ/MaaFramework/blob/main/docs/zh_cn/3.3-ProjectInterfaceV2协议.md
- 本机证据：`MaaCore.dll`（`com.hypergryph.arknights`、`MaaWin32ControlUnitCreate`、`MuMuPlayerExtras`）、`MaaWin32ControlUnit.dll`、`resource/config.json`（ADB 命令模板）。

### 6.2 MXU（MaaNTE / MaaEnd）

- **MXU**：Tauri（Rust）+ React/TS 的通用 GUI，解析任意符合 PI V2 的 `interface.json`；内嵌 MaaFramework 运行库（`maafw/`）；实例（instances）保存 controller/任务/存档设备；支持 `--autostart/--instance/--quit-after-run` 供系统自启动使用。仓库：https://github.com/MistEO/MXU
- MaaNTE（`MaaNTE.exe` = MXU + `interface.json` + `resource/` + Python agent）与 MaaEnd 同构；二进制内帮助文本、Rust 命令（`is_autostart/get_start_instance/has_quit_after_run_flag`）与前端 `mxu-start-tasks` 事件构成自启动链路（§4.3）。

### 6.3 ok-script / ok-ww

- **ok-script**（https://github.com/ok-oldking/ok-script）：Python 自动化框架（任务类体系、PySide6/qfluentwidgets GUI、截图 WGC/BitBlt、PostMessage 输入、日志/定时/更新）。ok-ww 是其上的鸣潮项目（`src/task/*`）。
- GUI 与执行核心分离：`ok/app` 负责 UI，`TaskExecutor` 按 `enabled` 的任务轮询执行；one-time 任务可被 CLI `-t` 指定并在 `-e` 时退出（§2.4-2.5）。
- 定时：用 Windows Task Scheduler COM 注册 `pythonw main.py -t … -e`（§2.7）。

### 6.4 PyAppify

- **PyAppify**（https://github.com/ok-oldking/pyappify ）：Rust/Tauri 启动器 + 更新器；首次运行从 git 拉代码到 `data/apps/<app>/repo`、装 Python 到 `data/apps/<app>/python`、复制到 `working`、`pip install -r requirements.txt`；启动时以 `working` 为 cwd、清理 PYTHON* 环境、注入 `PYAPPIFY_*`，再 `python(w).exe main.py <argv...>`（`src-tauri/src/execute_python.rs:12-49`）。
- `app.json` 记录 `current_version/current_profile/auto_start/update_method/running` 等；`admin=true` 只体现在**生成的快捷方式**（Run as administrator）与运行时提示，**不会自动提权当前进程**（★★★，`app_service.rs:1509-1532`、`app.json:43-55`）。这解释了「从 Hub 非提权启动 ok-ww.exe → 子进程非管理员 → ok-ww 要求重启」的链路。

---

## 7. 证据索引（本地文件:行 / 二进制字符串）

### ok-ww

| 证据 | 内容 | 强度 |
| --- | --- | --- |
| `working\README.md`「命令行参数」 | `ok-ww.exe -t 1 -e` 官方示例；`-t`/`-e` 语义 | ★★★ |
| `working\ok\util\process.py:571-609` | `parse_arguments_to_map`：`-t/--task`、`-e/--exit`、`-h/--headless` | ★★★ |
| `working\ok\__init__.py:703,764-806` | `self.args`、`start()`：GUI/headless 分支 | ★★★ |
| `working\ok\__init__.py:808-842` | `start_runtime()`：`-t` → `start_controller.start(task, exit_after=exit)` | ★★★ |
| `working\ok\__init__.py:844-863` | `run_task/run_onetime_task`（无 UI 执行） | ★★★ |
| `working\ok\core\start_controller.py:41-126` | `do_start`：启动游戏、`_mark_task_enabled`、`executor.start()` | ★★★ |
| `working\ok\task\TaskExecutor.py:547-615` | 执行 onetime 任务；结束 `disable()`；`exit_after_task` → 关游戏、`quit` | ★★★ |
| `working\ok\util\windows_schedule.py:1175-1271` | 计划任务 XML：`pythonw + main.py -t … -e`、cwd=working、HighestAvailable | ★★★ |
| `working\config.py:262-283` | one-time / trigger 任务列表与顺序 | ★★★ |
| `working\configs\DailyTask.json` | 每日任务参数与 `Exit After Task` | ★★★ |
| `working\configs\Basic Options.json` | `Start/Stop`（F9）、`Kill Launcher After Start` 等 | ★★★ |
| `working\ok\ui\qt\start\StartCard.py:65-70,116-140` | 顶部 Start → `start_controller.start()`；全局热键 `RegisterHotKey` | ★★★ |
| `working\ok\ui\qt\tasks\TaskCard.py:118-138` | 任务卡「Start」→ `start_controller.start(task)` | ★★★ |
| `working\ok\ui\qt\MainWindow.py:566-579` | 隐藏/杀掉 PyAppify 启动器（`KILL_LAUNCHER_AFTER_START`） | ★★★ |
| `working\ok\util\process.py:235-300` | 单实例 mutex（cwd md5，超时强杀旧实例） | ★★★ |
| `.pyappify-shortcut.py:1-62` | 干净环境定义 + `subprocess.run([python, main.py])` | ★★★ |
| `data\apps\ok-ww\app.json:35-55` | `running/last_start/auto_start/update_method`、profile `admin/use_pythonw` | ★★★ |
| `data\apps\ok-ww\working\logs\ok-script.log` | 本机运行日志（`ok-script init v3.7.4`、`pc_device ... 鸣潮`） | ★★★ |
| 进程实测 | 当前运行的 `pythonw.exe`(PID 42024) 命令行 = `...\python\pythonw.exe ...\working\main.py` | ★★★ |

### MAA

| 证据 | 内容 | 强度 |
| --- | --- | --- |
| `config\gui.new.json` | `Gui.StartUpSettings.RunDirectly/SkipStartupAutoRunAfterUpdate/StartEmulator/StartPcClient/PcClientPath`；`Gui.RuntimeSettings.StartGame`；`Gui.HotKeys`；`TaskQueue[]`；`Timers` | ★★★ |
| `config\gui.json` / `gui.json.old` | 旧格式：`Start.RunDirectly`、`Connect.*`（MuMu12、`127.0.0.1:16384`） | ★★★ |
| `debug\gui.log` | `AttachWindow: Found window "明日方舟" ...`、`任务已全部完成！`、`任务出错: X`、`已停止`、`HotKeys has been set: {"ShowGui":..., "LinkStart":"Ctrl + Shift + Alt + L"}` | ★★★ |
| `resource\config.json:46-53,77-78` | 包名表 + `am start/am force-stop` 模板 | ★★★ |
| `MAA.dll` 字符串 | `--skip-startup-auto-run`、`SkipStartupAutoRunAfterUpdate`、`StartupAutoRunCountdown*`、`ConfirmStartupAutoRunAsync`、`RunDirectly`、`Connect.UseAttachWindow`、`PcClientPath`、`GlobalHotKey`、`HotKeyLinkStart`、`--config/--instance/--keep-awake/--demo` | ★★ |
| GitHub `dev-v2` `src/MaaWpfGui/Main/AsstProxy.cs:756-814` | StartupAutoRun：10 秒倒计时 → `TryToStartConnectionTarget` → `LinkStart` | ★★★ |
| GitHub `dev-v2` `src/MaaWpfGui/Main/Bootstrapper.cs:490-520,854-970` | `--config`（会重启进程）、`--skip-startup-auto-run`、单实例仅激活不转发任务 | ★★★ |
| GitHub `dev-v2` `.../Configuration/Single/Settings/StartUpSettings.cs` | `RunDirectly` 注释：启动后直接运行/启动模拟器，更新重启用 `--skip-startup-auto-run` 跳过 | ★★★ |
| 文档 | `docs/zh-cn/manual/connection.md`（模拟器路径/启动）https://github.com/MaaAssistantArknights/MaaAssistantArknights/blob/dev-v2/docs/zh-cn/manual/connection.md | ★★★ |

### MaaNTE / MaaEnd / MXU

| 证据 | 内容 | 强度 |
| --- | --- | --- |
| MXU README「命令行参数」 | `--autostart` / `-i, --instance` / `-q, --quit-after-run` 表格与示例（https://github.com/MistEO/MXU） | ★★★ |
| `MaaNTE.exe` 内嵌中文帮助 | 「MXU 命令行参数 … `--autostart 以开机自启动模式运行，并触发自动执行逻辑` … `-q … 在任务完成时自动退出`」 | ★★★ |
| `MaaNTE.exe`/`MaaEnd.exe` 前端 | `is_autostart` → `setIsAutoStartMode`；`get_start_instance` 按名字查实例；`has_quit_after_run_flag` 订阅 `isRunning` 落下 → `exit(0)`；`mxu-start-tasks` 事件 | ★★★ |
| `MaaNTE\config\mxu-MaaNTE.json` | 实例 `挂机任务`、`autoRunOnLaunch=false`、`autoStartInstanceId` 未设、`savedDevice` | ★★★ |
| `MaaEnd\config\mxu-MaaEnd.json` | 实例 `全套日常`/`快速日常`/`实时辅助`，enabled 任务清单（含 `__MXU_PRETASK__LaunchGamePC`） | ★★★ |
| `MaaNTE\interface.json:25`、`MaaEnd\interface.json:26-38` | controller 声明 `permission_required: true`；Win32-Front `UnityWndClass` + `Endfield` | ★★★ |
| `MaaEnd\debug\mxu-tauri.log` | Rust 侧日志（`mxu_lib::commands::*`、读取 `tasks\preset\DailyFull.json` 等） | ★★★ |
| `MaaEnd\agent\go-service.exe` 字符串 | `launchgamepc.*`、`不一致无法找到启动器`、`鹰角启动器`、`^Qt\d+QWindowIcon$` | ★★ |
| `MaaNTE\debug\custom\2026-09-27.log.zip` | agent 运行日志（PI 环境、controller 配置） | ★★★ |

### GameHub（只读参考）

| 证据 | 内容 |
| --- | --- |
| `gamehub/store.py:1424-1468` | `build_okww_launch`：pythonw/main.py/cwd/env/process_exe_dirs（工作区未提交） |
| `gamehub/store.py:1523-1560` | `launch_app`：`spec["args"]` 支持、失败回退启动器（未提交） |
| `gamehub/store.py:1573-1607` | `launch_running_pids`（按 exe 完整路径）/`launch_spec_running`（未提交） |
| `gamehub/detector.py:1-40` | v0.6 detect schema（win/proc/adb） |
| `tools/test_launch_spec.py` | feature-dev 的启动规格自测（离线 mock，未提交） |

---

## 8. 复现/核对命令（只读）

```powershell
# ok-ww CLI 说明（本地 README）
Select-String -Path 'D:\All MAA\WuwaMAA\ok-ww\data\apps\ok-ww\working\README.md' -Pattern '命令行参数','-t 1 -e'

# ok-ww 官方计划任务命令（pythonw + main.py -t … -e）
Select-String -Path 'D:\All MAA\WuwaMAA\ok-ww\data\apps\ok-ww\working\ok\util\windows_schedule.py' -Pattern 'cmd_args','python_exe','WorkingDirectory'

# ok-ww 当前进程形态（脚本=pythonw，不是 ok-ww.exe）
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" |
  Select-Object ProcessId,CommandLine

# MAA 任务队列 / 启动设置 / 热键
python -c "import json;d=json.load(open(r'D:\All MAA\MAA-v5.1.0-win-x64\config\gui.new.json',encoding='utf-8'));print(json.dumps(d['Configurations']['Default']['Gui']['StartUpSettings'],ensure_ascii=False,indent=1));print(json.dumps(d['Gui']['HotKeys'],ensure_ascii=False))"

# MAA 完成/失败关键字（历史）
Select-String -Path 'D:\All MAA\MAA-v5.1.0-win-x64\debug\gui.log' -Pattern '任务已全部完成','任务出错','已停止'

# MXU 实例名
python -c "import json;print([i['name'] for i in json.load(open(r'D:\All MAA\MaaNTE\config\mxu-MaaNTE.json',encoding='utf-8'))['instances']])"
python -c "import json;print([i['name'] for i in json.load(open(r'D:\All MAA\MaaEnd-win-x86_64-v2.33.0\config\mxu-MaaEnd.json',encoding='utf-8'))['instances']])"
```

---

## 9. 风险与待实测项

| 风险 | 说明 / 缓解 |
| --- | --- |
| **未实测真实清日常** | 受任务约束未启动游戏/脚本；`-t`/热键/`--autostart` 的端到端成功需 feature-dev 或用户实测一次（建议先用不消耗体力的任务或直接观察日志） |
| **管理员/提权** | ok-ww、MXU（Win32 controller）都需要管理员；Hub 需 `ShellExecuteW runas`，UAC 弹窗无法避免（用户点一次） |
| **ok-ww 单实例互斥** | 第二次启动会强杀同 cwd 旧实例（5s 等待）；Hub 必须先判运行状态 |
| **MAA 热键冲突** | 热键可能被其它软件占用（MAA 日志 `HotKeyLinkStartRegistrationFailed`）；Hub 应先读配置并做可用性校验，UI 提供「改为启动后直接运行」引导 |
| **MXU `-q` 不区分成败** | 只能以进程退出为完成；成功判断依赖日志启发式（未实测关键字），UI 文案避免绝对化 |
| **MaaNTE 实例未配置日常** | 本机仅 FishNew；直接一键只会跑钓鱼。Hub 应在调用前校验实例 enabled 任务数，并给「配置指南」入口 |
| **MAA 任务队列未勾选** | 本机只有自动肉鸽；若用户直接点一键，会跑错任务。Hub 应读取 `TaskQueue[].IsEnable` 校验并提示 |
| **MAA `--config` 会重启进程** | Hub 若使用 `--config` 需按「进程可能退出并新起」处理；建议让用户把目标配置设为 `Current` 后省略该参数 |
| **游戏启动器 vs 游戏本体** | Hub 的 `game_exe` 三项都指向启动器；一键清日常不应依赖 Hub 的 game_exe，而应由脚本自启游戏 |
| **ban 风险** | 脚本自动化违反游戏条款（ok-ww README 明示）；Hub 应保留免责声明与二次确认 |
| **日志编码/体积** | `gui.log`/`ok-script.log` 为 UTF-8 文本、持续追加（本机 gui.log 2.3MB）；按「记录 offset + 只读增量」实现，避免整文件读取 |

---

## 10. Lead 补充核实项（回填，实施前必读）

### 10.1 ok-ww：`-t` 名称解析规则、`-h` 取舍、推荐命令

- **`-t` 到底能写什么**（`ok/util/process.py:571-609` + `ok/__init__.py:879-1008`）：
  | 写法 | 是否可用 | 说明 |
  | --- | --- | --- |
  | `-t 1` | ✅ | 1-based 序号，当前顺序第 1 个 = `DailyTask`（`config.py:262-274`） |
  | `-t DailyTask` | ✅ **推荐** | 先按 `模块.类名`、再按「任务名 / 类名」精确匹配，最后包含匹配；大小写不敏感（`find_task_by_name` 全部 `.lower()`） |
  | `-t src.task.DailyTask` | ✅ | 模块路径 + 类名精确匹配；模块改名时有类名回退 |
  | `-t "Daily Task"` | ✅ | 任务 `name` 是 `"📅 Daily Task"`，包含匹配命中 |
  | `-t "每日任务"` / 中文译名 | ❌ | 任务 `name` 是英文硬编码（`DailyTask.py:29 self.name = "📅 Daily Task"`），GUI 中文只是显示翻译，CLI 不认 |
  | `-t MultiAccountDailyTask` | ⚠️ | 那是「多账号日常」，单账号清日常请用 `DailyTask`（`config.py:269` 与 `262` 两个不同任务） |
- **不要用 `-t 1` 长期写死**：任务顺序可能随版本调整；用类名 `DailyTask` 最稳。
- **`-h/--headless` 是否加？——不建议**：
  - `-h` 会走 `should_init_task_manager_headless()`（`ok/__init__.py:758-762`）→ 无主窗口、无 GUI 热键、出错只有日志；`run_task`→`run_onetime_task` 虽能跑（`ok/__init__.py:844-863`），但 `start_runtime` 的 GUI 分支（`ok/__init__.py:823-836`）不会执行。
  - 不加 `-h` 时，Qt 主窗口显示后 `MainWindow.showEvent → og.ok.start_runtime()` 检测到 `-t` 参数会**自动开始该任务**（`ok/__init__.py:827-836`），用户能看到进度、失败弹窗、截图区，符合「一键清日常」的可观测性；`-e` 同样生效（GUI 分支 `app.start_controller.start(start_task, exit_after=self.args.exit)`）。
  - 结论：**一键清日常用 `pythonw main.py -t DailyTask -e`（不加 -h）**；`-h` 仅留给未来的无头批处理模式。
- **前置**：`Basic Options.json → "Auto Start Game When App Starts"` 只在**没有** `-t` 时决定是否拉起游戏；带 `-t DailyTask` 时 `start_controller.do_start()` 内部仍会 `start_device()`（必要时启动游戏），所以**该开关对一键清日常不是必需**，但建议保持开启作为兜底（本机当前 `false`，可由用户开启）。
- **`-e` 的完整语义**：任务成功后打印 `Successfully Executed Task, Exiting Game and App!` → 等待 5s → `device_manager.stop_hwnd()`（kill 游戏 exe）→ 再等 5s → `communicate.quit` → App 退出（`ok/task/TaskExecutor.py:589-595`、`DeviceManager.py:126-130`）。**失败或任务未结束时不会退出**，Hub 需按超时兜底。

### 10.2 MAA：`Start.RunDirectly` 语义确认 + 安全读写/恢复方案

- **语义（已确认）**：`StartUpSettings.RunDirectly`（旧键 `Start.RunDirectly`）就是**「启动后直接运行」**：MAA 完成 Core 初始化后 → 10 秒倒计时弹窗 → `TryToStartConnectionTarget(true)`（必要时拉起模拟器/PC 客户端）→ `LinkStart()` 执行**任务队列中 `IsEnable=true` 的全部任务**（源码 `MaaWpfGui/Main/AsstProxy.cs:756-814`；`StartUpSettings.cs` 中 `RunDirectly` 与注释「启动后直接运行 / 启动模拟器」，更新重启链用 `--skip-startup-auto-run` 跳过）。
- **可安全读写的键**（MAA 同时双写两份配置，建议两份都读、两份都写，写完让 MAA 自己加载）：

  | 文件 | JSON 路径 | 旧值 | 目标值 |
  | --- | --- | --- | --- |
  | `MAA\config\gui.new.json` | `Configurations.<Current>.Gui.StartUpSettings.RunDirectly` | `false` | `true` |
  | `MAA\config\gui.json`（旧格式兼容） | `Configurations.<Current>.Start.RunDirectly` | `"False"` | `"True"` |

  其中 `<Current>` = 文件的 `"Current"` 字段（本机 `"Default"`）；旧格式值为字符串 `"True"/"False"`（大写首字母），新格式为布尔。
  - **待验证**：当前 MAA v6.x 以 `gui.new.json` 为准，`gui.json` 里的 `Start.*` 可能只是迁移兼容读取；实现时以写 `gui.new.json` 为主，`gui.json` 仅作兼容双写/回退，改完务必实测一次 `gui.log` 是否出现「即将自动运行任务」。
- **安全备份/恢复流程（Hub 实现建议）**：
  1. 先确认 MAA 已退出（进程 `MAA.exe` 不存在；否则热键/激活路径优先，不要改正在运行的配置）；
  2. `shutil.copy2(gui.json, gui.json.hub-bak)`、`shutil.copy2(gui.new.json, gui.new.json.hub-bak)`；
  3. 两个文件都置 `RunDirectly=true`（保留其他键原样，`json.dump(ensure_ascii=False, indent=2)` 可直接覆盖，MAA 能读）；
  4. 启动 `MAA.exe`（可不带 `--skip-startup-auto-run`；若带则该参数会**跳过**自动运行，正好用于「只打开 MAA」）；
  5. 等 `gui.log` 出现 `任务已全部完成！` / `任务出错:` / 超时；
  6. 等 MAA 退出或用户确认后，把两份 `.hub-bak` 还原回原文件（注意：MAA 运行期间会持续写配置，**必须等 MAA 进程结束后再恢复**，否则会被覆盖）。
  - 更轻量的替代：不改配置，用热键方案（本报告 §3.5 B1，推荐默认）；「写配置」仅作为热键不可用时的 B2 降级。
- **模拟器 / PC 两种模式差异（与 RunDirectly 的关系）**：
  - 模拟器：`Gui.ConnectSettings.Config = MuMuEmulator12`（或其它），`RunDirectly` 会先 `TryToStartConnectionTarget`：`StartEmulator=true` 才拉起模拟器（本机 false → 需用户先开），`RuntimeSettings.StartGame=true` 时由「开始唤醒」任务 `am start` 启动游戏；完成后任务队列继续。
  - PC 客户端：`ConnectConfig = PC`（`IsPCConnectConfig`）+ `StartUpSettings.PcClientPath`；`StartPcClient=true` 时 MAA 自己拉起客户端并 `AttachWindow`（按标题 `明日方舟`），否则需用户先开客户端。PC 模式建议管理员权限（输入方式 Seize/PostMsg）。
- **`Start.*` 其它相关键**（旧格式，供回退检查）：`Start.StartEmulator`、`Start.OpenEmulatorAfterLaunch`、`Start.MinimizingStartup`（新格式对应 `Gui.MinimizeOnStartup`）、`Start.EmulatorPath`、`Start.EmulatorWaitSeconds`。

### 10.3 MXU：MaaEnd 同构确认 + 实例名读取

| 项目 | 读取路径 | 键 |
| --- | --- | --- |
| MaaNTE | `D:\All MAA\MaaNTE\config\mxu-MaaNTE.json` | `instances[].name`（本机 `["挂机任务"]`）、`settings.autoRunOnLaunch`、`settings.autoStartInstanceId` |
| MaaEnd | `D:\All MAA\MaaEnd-win-x86_64-v2.33.0\config\mxu-MaaEnd.json` | `instances[].name`（本机 `["全套日常","快速日常","实时辅助"]`）、同上 |

- 两者配置结构、CLI、自启动逻辑完全同构（`MaaEnd.exe` 含 `is_autostart/get_start_instance/has_quit_after_run_flag/mxu-start-tasks` 同名命令，★★★）。
- `--instance` 只按 **`instances[].name` 精确匹配**（含空格/中文）；匹配不到会回退 `settings.autoStartInstanceId`，两者都不存在 → 仅打开界面、**不会触发任务、`-q` 也不会退出**（前端逻辑，★★★）。Hub 调用前应从上述 JSON 读实例名做校验。
- 实例里 `instances[].tasks[].enabled` 决定实际执行哪些任务；Hub 可据此提示「该实例未启用日常任务」（例如 MaaNTE 本机仅 `FishNew`）。

### 10.4 完成判定汇总（可直接实现）

| 脚本 | 主信号 | 成功判定 | 失败/停止判定 | 备注 |
| --- | --- | --- | --- | --- |
| ok-ww | **进程退出**（按 `...\ok-ww\python\pythonw.exe` 完整路径判定，不看 `OK-WW.EXE`） | 退出前日志追加 `Successfully Executed Task, Exiting Game and App!`（`working\logs\ok-script.log`） | 退出但无该行 → 失败；90min 仍存活 → 超时（需 kill） | `-e` 有 ~10s 收尾 + kill 游戏 |
| MXU（MaaNTE/MaaEnd） | **进程退出**（`-q` 触发，`exit(0)`） | 无区分（退出即结束）；日志无失败特征 + 用时合理 → 视为完成 | 退出码恒 0；仅日志启发式 | 退出后等 3-5s 让 agent 子进程退出 |
| MAA | **`MAA\debug\gui.log` 增量文本**（不落盘任务状态） | `任务已全部完成！`（实锤 16 次） | `任务出错: <任务名>` / `正在停止……` / `已停止` | `TaskQueue.TaskItemStatus.Completed`、`AllTasksCompleted` 只是 MAA.dll 内的 **UI 本地化资源键/字符串**，不是可读文件；MAA 完成后窗口保持（`PostActions=None`） |
| 游戏本身（兜底） | v0.6 detector 的窗口/进程状态 | 游戏窗口消失/进程退出 | — | 只在脚本退出后做一致性校验 |

**Hub 实现建议**：启动前记录日志文件 `os.path.getsize`，运行中每 1-2s 读增量（按字节 seek + UTF-8 errors="replace"），匹配上述固定文案；日志轮转/截断时重置 offset。ok-ww 日志路径：`<ok-ww>\data\apps\ok-ww\working\logs\ok-script.log`；MAA：`<MAA>\debug\gui.log`（本机 2.3MB 纯追加）。

---

*报告完。所有结论均可用 §7 证据索引与 §8 命令复核；标注 ★ 的为推断（如热键系统级发送、MXU 日志完成关键字），落地前建议实测一次。*
