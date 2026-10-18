# CHANGELOG

> 最新版本在最上方。

## v0.10.1 (2026-10-18)

- **异环「启动游戏」修复**：改回启动 `NTELauncher.exe`（登录后点「开始游戏」），不再直启
  `HTGame.exe`——直启会触发 UE map 错误、游戏起不来；旧配置里的启动器路径会被自动发现 / 记忆。
  等待逻辑仍监听「异环 / NTE」窗口与 `HTGame.exe`，找不到启动器时提示手动选择
- **异环「清日常」改为热键模式**：打开 MaaNTE 正常界面（不再带 `--autostart`），等主窗口就绪 /
  置前后发送 MaaNTE 设置里的「开始任务」全局热键（默认 `Ctrl+F10`），等价手动点「开始任务」；
  完成判定改为 `debug` 最新日志增量出现「停止任务 / tasks-completed / 已停止」
- **热键缺失 / 发送失败保护**：读不到热键或 `globalEnabled=false` 时保留 MaaNTE 窗口并提示
  手动点击开始任务，该项记为失败（不会静默成功）；MaaNTE 已在运行时只发送热键，不结束用户
  自己打开的实例；实例名 / 任务字段不再是必需
- 测试 / 回归更新：`tools/test_daily.py` 补充异环热键计划、手动回退与日志完成判定；
  `tools/test_game_exe.py` / `tools/test_game_launch.py` 改为校验 `NTELauncher.exe` 启动规格
- 更新 README / 主页中异环启动与清日常说明

## v0.10.0 (2026-10-18)

- **圆润淡紫渐变 UI**：默认强调色改为淡紫 `#b98bff`，标题栏 / 侧栏 / 面板使用深色淡紫渐变；
  更圆润的设计令牌（面板圆角 16 / 按钮 13 / 输入框 10、间距 10–26），强调色预设更新为淡紫系
- **自定义标题栏**：隐藏原生标题栏并自绘渐变标题栏（品牌图标 + 标题 + 最小化 / 最大化 / 关闭），
  支持拖动移动、双击最大化、8 向边缘 / 角落缩放；恢复任务栏 / Alt+Tab 行为并启用 Windows 圆角，
  关闭按钮遵循「关闭窗口行为」设置
- **字体大小**：设置 → 外观新增 小 / 标准 / 大 / 特大（0.9 / 1.0 / 1.12 / 1.25），
  保存后立即生效，标题栏 / 按钮 / 页面标题 / 行高与后续对话框同步缩放（侧栏按钮限幅防溢出）
- **自动更新**：启动时自动检查脚本与 Hub 版本（900ms / 1800ms），设置可开启「自动下载更新」
  （安装前仍确认）；打包版更新器等旧进程退出 → 备份 → 替换 exe → 重启，源码模式执行
  `git pull --ff-only`；网络失败 / 不可写 / 非 git 场景降级为打开发布页
- **四游戏启动重构**：鸣潮直启 `Wuthering Waves.exe`（`-krqlv=hd`）；异环直启 `HTGame.exe`
  并自动纠正旧 `NTELauncher.exe` 配置；终末地走鹰角启动器并等待 `Endfield` 窗口（失败回退直启 /
  手动选择）；MAA 分 PC（`Arknights.exe`）与模拟器（ADB `am start`）分支；自定义游戏直启
  `game_exe`。启动后统一等待窗口 / 进程（120–180s、500ms 轮询），失败给出回退提示
- **Logo**：`assets/hub.png` / `hub.ico` 更新为 LinYuxia 风格应用图标；网页 Logo/favicon 已是
  LinYuxia（v0.9.1 后完成）
- 新增 `docs/game-launch-research.md`（四脚本「启动游戏」方式调研）、
  `tools/test_game_exe.py`、`tools/test_game_launch.py`
- 测试：回归 / UI 状态 / 游戏启动策略等自测更新（数量与结论见 `docs/qa-report.md`）
- 更新 README / 主页（圆润淡紫 UI、标题栏、字体大小、自动更新、游戏启动重构、Logo）

## v0.9.1 (2026-10-18)

- **品牌图标**：应用图标改为 `assets/LinYuxia.png`，用于主窗口 / 任务栏（64 / 32px）与
  侧边栏品牌（46px）
- **四个子页面图标**：主页（手柄 `page_home.png`）、清日常（剑 `page_daily.png`）、
  设置（雪花 `page_settings.png`）接入侧边栏导航与页面标题；关于（角色头像 `page_about.png`）
  用于「关于软件」按钮与关于对话框
- **图标回退**：品牌图标缺失时回退旧 `hub.png`；关于图标缺失时回退 `LinYuxia.png` / `hub.png`；
  其它图标缺失时正常显示文字，不报错
- **资源加载**：图标统一从 `store.ASSETS` 读取（源码运行 `assets/`，PyInstaller 打包版
  `_MEIPASS/assets`），打包脚本的 `--add-data "assets;assets"` 会一并带上
- 图标常量集中在 `gamehub/ui.py`（`BRAND_ICON_FILE` / `PAGE_ICON_FILES` / `ICON_SIZES` /
  `ICON_FALLBACKS`）；新增 `assets/page_home.png`、`page_daily.png`、`page_settings.png`、
  `page_about.png`、`LinYuxia.png`
- 自测：`tools/test_ui_state.py` 增加图标映射 / 尺寸档 / 缺失回退断言（全绿）
- 更新 README / 主页图标说明

## v0.9.0 (2026-10-18)

- **界面美化与统一设计**：新增设计令牌（`gamehub/theme.py`）——统一 Microsoft YaHei UI 字体与
  字号（21 / 16 / 13 / 11 / 10，最小 10）、圆角 12 / 8、间距 8 / 12 / 16 / 20 / 24、
  深色 surface 分层色板与柔和描边；自绘 `RoundButton` / `RoundPanel` / `RoundEntry`，
  按钮具备默认 / 悬停 / 按下 / 禁用 / 主按钮 5 态，统一焦点描边
- **自由缩放与响应式**：窗口默认 1180×760、最小 1000×640，可自由缩放；侧边栏固定 232px、
  内容区自适应；主页 / 清日常 / 设置页支持滚动与换行，窗口变窄不横向溢出；
  对话框自动居中并限制在主窗口范围内
- **侧边栏功能分区**：新增「小工具」（打开 Clash Verge / 脚本目录 / 日志目录 / 检查脚本更新）
  与「关于与更新」（关于软件 / 检查软件更新）；主页改为更大更美的游戏行与 5 态按钮，
  清日常页 / 设置页视觉统一
- **关于软件**：显示版本、License、GitHub / 项目主页 / License / 更新日志入口，
  并预览 CHANGELOG 的「最近更新」（最新版本在最上面）
- **软件更新**：读取 GitHub latest release（`api.github.com/repos/Diaohesi/All-My-Maa/releases/latest`），
  与本地版本比较，显示新版本号与更新说明，可「打开发布页」；**不自动下载 / 安装**；
  网络失败给出明确提示
- **品牌**：项目名统一为 **All-My-Maa**（GitHub 仓库、Pages、文档、应用内标题与关于页）
- **测试**：扩展 `tools/test_ui_state.py`（更新解析 / 版本比较 / 设置与状态纯逻辑）；
  回归测试数量与结论见 `docs/qa-report.md`
- 更新 README / 主页（界面与体验、小工具 / 关于 / 软件更新、FAQ）

## v0.8.0 (2026-10-18)

- **界面重构**：主窗口改为左侧固定导航 +「主页 / 清日常 / 设置」三页（1200×720，可调整、
  最小 1000×620），由 Pillow 单画布改为真实 Tk 控件，按钮状态 / 悬停 / 禁用更清晰；
  保留深色标题栏、单实例、Pillow 图标
- **主页按钮式启动器**：每个游戏一行（图标 / 名称 / 版本 / 脚本状态 / 游戏状态），主按钮
  「打开脚本」（未运行则启动，运行中显示「唤到前台」并聚焦窗口），另有「启动游戏」「清日常」
  「更多 ▾」（编辑卡片 / 检查更新 / 脚本官网 / GitHub / 游戏下载页 / 打开脚本文件夹 /
  更新启动器 / 删除自定义卡片）；点行图标或名称等同「打开脚本」
- **清日常页**：勾选框决定是否加入队列（`daily.enabled`）、↑↓ 排序（`daily_order`）、
  开始选中项 / 停止 / dry-run 预览；每行独立「开始清日常 / 停止」与独立状态
  （空闲 / 启动中 / 运行中 / 已完成 / 失败 / 超时 / 已停止）；同一时刻只运行一项，
  其它行保持自身状态；运行日志与免责提示
- **设置页**：强调色、启动时检查更新、状态刷新间隔（1.0 / 1.5 / 2.0 秒）、关闭窗口行为
  （退出 / 最小化）、脚本根目录与重新识别、Clash Verge 路径（浏览 / 自动查找）、
  清日常默认超时、执行前显示命令预览、启用 ADB 检测、完成后结束脚本默认值；
  关于页提供项目主页 / GitHub / Release / 更新日志 / QA 报告 / 调研报告 / 检查更新入口
- **配置扩展（仍为 v4）**：顶层新增 `settings`（强调色 / 启动检查更新 / 刷新间隔 / 关闭行为 /
  Clash 路径 / 清日常默认值），缺省补默认、非法值清洗；保存失败会提示
- **All-My-Maa 品牌**：项目更名为 All-My-Maa（GitHub 仓库、Pages、文档、应用内标题与关于页同步）
- **清日常独立状态**：新增 `daily.DailyManager`，按 app 维护状态，支持单项开始 / 停止与队列，
  非当前项不再显示「清日常中」
- 新增 `tools/test_ui_state.py`（per-app 状态隔离 / 勾选过滤 / settings 清洗与往返）；
  回归测试扩充（数量与结论见 `docs/qa-report.md`）
- 更新 README / 主页（新版界面、设置、勾选清日常、按钮式启动）

## v0.7.0 (2026-10-18)

- **鸣潮启动修复**：`ok-ww.exe` 只是 PyAppify 启动器 / 更新器，不是脚本本体。新增启动规格
  （`launch`，type=python）：「启动脚本」直接运行
  `data\apps\ok-ww\python\pythonw.exe` + `working\main.py`（cwd=working、清理 `PYTHON*` 环境、
  注入 `PYAPPIFY_*`），目录不完整时回退启动器；「更新」仍走 `ok-ww.exe`；脚本运行状态改为按
  `pythonw.exe` 完整路径判定，不再把启动器当脚本
- **一键清日常**：卡片底部「清日常」单游戏执行，工具栏「一键清日常」按顺序串行执行多款游戏；
  使用各脚本自身已配置的任务——ok-ww `-t DailyTask -e`、MAA `--skip-startup-auto-run` + LinkStart 热键、
  MaaNTE / MaaEnd `--autostart --instance "<实例名>" --quit-after-run`
- **清日常顺序队列**：启用 / 停用、↑↓ 排序并保存 `daily_order`、单项超时（1–600 分钟）、额外参数、
  完成后结束脚本、实时进度与结果汇总、随时停止、开始前 dry-run 命令预览
- 完成判定与异常处理：ok-ww 日志成功标记、MAA `gui.log` 完成 / 失败 / 停止关键字、MXU 进程退出；
  超时结束本次启动的进程并继续下一项；UAC 逐项确认；失败原因写入进度面板
- 配置扩展（仍为 v4）：新增 `daily`（清日常设置）、`daily_order`（队列顺序）、`launch`（启动规格）；
  旧配置自动补默认值，鸣潮启动规格自动生成
- 新增 `gamehub/daily.py`（计划 / 执行 / 顺序队列）、`tools/test_daily.py`（mock 自测）、
  `tools/test_launch_spec.py`（启动规格自测，`--live` 只读核对本机 ok-ww）
- 新增调研报告 `docs/daily-automation-research.md`：四款脚本的启动链、CLI 参数、完成信号、
  前置条件与风险（688 行）
- UI：顶部新增「一键清日常」按钮、卡片底部「清日常」链接（运行中显示「清日常中」）、
  右键菜单「清日常（当前游戏）」、顺序队列对话框（排序 / 启用 / 设置 / 预览 / 停止）
- 自测：`tools/test_daily.py`、`tools/test_launch_spec.py` 全绿；回归测试 156 用例保持全绿
- 更新 README / 主页（一键清日常说明、鸣潮启动修复、四脚本原理、配置字段、常见问题）

## v0.6.0 (2026-10-18)

- **准确游戏运行检测**：游戏状态不再只看进程名，改为复用各脚本自身的判断方法——
  一次 `EnumWindows` 窗口快照 + 窗口类 / 标题正则 + 进程（路径收窄，取不到路径时降级）+
  可选 ADB（默认关闭）；区分「运行中（窗口）/ 运行中（进程）/ 运行中（ADB）」
  「启动器已开」「云游戏运行中」「未运行 / 未配置」；启动器 / 云游戏只显示文案，不再误报成运行
- 内置规则：MaaNTE / MaaEnd 自动读取各自 `interface.json` 的 `controller[].win32`；
  ok-ww 按其 `config.py` 采用 `UnrealWindow` + `Client-Win64-Shipping.exe` 双重校验；
  MAA PC 端 `UnityWndClass` + `^明日方舟|^Arknights`，模拟器为 ADB 包名规则（默认关闭）
- 编辑卡片新增「检测规则（可选）」四项：窗口类、窗口标题、进程名、ADB 包名，可自定义；
  「自动检测」选中启动程序后会把脚本自带规则建议填入空项
- 修复旧配置误配：内置卡片 `game_procs` 由启动器进程（`NTELauncher.exe` / `Launcher.exe`）
  迁移为游戏本体进程（`Arknights.exe` / `HTGame.exe` / `Client-Win64-Shipping.exe` / `Endfield.exe`），
  配置升级为 v4
- 新增 `gamehub/detector.py`（窗口 / 进程 / ADB 检测与规则解析）与
  `tools/test_detect_game.py`（不打开 GUI 的游戏状态检测自测）
- 新增调研报告 `docs/game-detection-research.md`：四款脚本的窗口类 / 标题 / 进程 / ADB 检测机制
  逆向与静态分析、无法可靠检测的场景与建议
- 回归测试更新：`tools/regression_test.py` 扩充到 **111 个用例**（含检测规则相关用例），
  全绿、退出码 0；`docs/qa-report.md` 更新为 v0.6.0 最终版（111 通过 / 0 失败 / 0 跳过）
- 本机验证：异环运行中被准确识别「运行中（窗口）」（`UnrealWindow` + 「异环」含尾随空格 +
  `HTGame.exe`），其余三款未运行且无启动器误报；`EnumWindows` 快照 8–14ms
- 更新 README / 主页（游戏运行检测说明、配置 v4、检测规则、目录结构、常见问题）

## v0.5.0 (2026-10-18)

- **游戏启动程序自动检测**：编辑卡片时「游戏启动程序」旁新增「自动检测」按钮，
  扫描注册表卸载项（HKLM / HKCU，含 WOW6432Node）与常见安装目录
  （Program Files、LOCALAPPDATA\Programs、各盘 Games / Game / 游戏 等），
  按匹配度排序列出候选（名称 + 路径 + 来源「注册表 / 常见目录」），双击或「确定」填入；
  检测总预算 1.8 秒，本机实测每款游戏约 0.2–0.4 秒
- **启动游戏时自动检测**：未配置游戏启动程序时先自动检测，有候选弹出深色候选选择框
  （含「浏览…」手动选择），无候选回退文件选择框；选中的路径与进程名会写回配置
- 新增 `tools/test_detect.py`：游戏自动检测命令行自测，不打开 GUI
- 修复（来自回归测试，详见 `docs/qa-report.md`）：`save_state` 保存失败不再静默，
  界面会提示配置保存失败（QA-03）；异环 `app.json` 缺字段时回退版本（QA-01）；
  `interface.json` 版本值非字符串时回退（QA-02）；版本比较支持预发布号与短版本（QA-04）；
  进程名清洗忽略非字符串项（QA-05）；注册表 `DisplayIcon` 带图标索引时正确解析（QA-09）
- 新增回归测试 `tools/regression_test.py`（标准库 unittest，57 个用例）与 `docs/qa-report.md` 测试报告
- 新增 GitHub Pages 项目主页：<https://diaohesi.github.io/All-My-Maa/>
  （`docs/index.html` + `docs/site.css`，`.github/workflows/pages.yml` 自动部署）
- 新增 `tools/verify_exe.ps1` 本地打包验证脚本
- 更新 README（在线主页入口、自动检测说明、目录结构、常见问题）

## v0.4.0 (2026-10-18)

- 界面重构为运行时动态渲染（Pillow），卡片数量随数据变化，支持翻页
- **可视化添加游戏**：顶层「添加游戏」对话框，可填名称、脚本路径、游戏路径、
  进程名、官网/GitHub/更新地址、下载页、主题色、自定义图标
- **启动游戏**：每张卡片新增「启动游戏」按钮，首次点击选择游戏启动程序并记住；
  支持游戏运行状态检测，已在运行时点击可切回前台
- **下载游戏**：卡片底部新增「下载」链接，一键打开对应游戏官方下载页
- **编辑 / 删除**：右键卡片或「更多」菜单可编辑、删除（删除仅对自定义卡片）
- 工具栏：添加游戏 / 检查更新 / 重新识别路径 / 打开 Clash Verge
- 状态区改为「脚本状态 + 游戏状态」双状态显示
- 配置升级为 v3：支持自定义卡片、游戏路径/进程、图标、下载页；兼容旧配置
- 路径自动识别升级：内置脚本按 exe 名扫描、多版本择优；自定义脚本同样支持重扫
- 新增 `tools/make_assets.py`（生成图标）、`tools/grab_hub.py`（截图）等开发工具
- 新增 `requirements.txt`、更新 README / 截图

## v0.3.0 (2026-10-18)

- 新增「明日方舟终末地」脚本卡片（MaaEnd），界面改为四卡片布局
- 新增脚本路径自动识别：配置 → 自动扫描 → 预期位置；支持手动选择
- 路径以相对路径保存，整个文件夹换电脑 / 换盘符后仍可用
- 新增「重新识别路径」按钮，脚本升级换目录后一键重新识别
- Clash Verge 路径支持多位置探测与 `config.json` 配置
- 支持 `config.json` 的 `root` 选项，Hub 与脚本可分开存放
- 新增桌面快捷方式脚本与 PyInstaller 打包脚本（可选免 Python 运行）
- 整理为可直接上传 GitHub 的仓库结构（README / LICENSE / CHANGELOG / .gitignore / docs）

## v0.2.0 (2026-10-18)

- 新增后台版本检查，卡片显示 `本地 → 最新` 并高亮「更新」
- 新增每张卡片的「更新 / 官网 / GitHub / 文件夹」入口
- 新增右上角「打开 Clash Verge」按钮
- 版本号改为读取各脚本本地真实版本，脚本自更新后自动跟随

## v0.1.0 (2026-10-18)

- 首个精简版：三个脚本一键启动、运行状态检测、悬停反馈、路径缺失兜底、单实例
