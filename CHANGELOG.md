# CHANGELOG

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
- 新增 GitHub Pages 项目主页：<https://diaohesi.github.io/ALL-MY-MAA/>
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
