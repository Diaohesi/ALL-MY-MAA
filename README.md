# 游戏脚本中心 · GameHub Lite v0.6.0

<p align="center">
  <a href="https://github.com/Diaohesi/ALL-MY-MAA/releases/latest"><img alt="release" src="https://img.shields.io/github/v/release/Diaohesi/ALL-MY-MAA?label=release&color=4fc3ff"></a>
  <a href="https://github.com/Diaohesi/ALL-MY-MAA/actions/workflows/build-exe.yml"><img alt="build" src="https://github.com/Diaohesi/ALL-MY-MAA/actions/workflows/build-exe.yml/badge.svg"></a>
  <a href="https://github.com/Diaohesi/ALL-MY-MAA/stargazers"><img alt="stars" src="https://img.shields.io/github/stars/Diaohesi/ALL-MY-MAA?color=b98bff"></a>
  <img alt="license" src="https://img.shields.io/badge/license-MIT-green">
  <img alt="platform" src="https://img.shields.io/badge/platform-Windows-0078D7">
  <img alt="python" src="https://img.shields.io/badge/python-3.10%2B-3776AB">
  <a href="https://diaohesi.github.io/ALL-MY-MAA/"><img alt="homepage" src="https://img.shields.io/badge/homepage-GitHub%20Pages-5ee7c7"></a>
</p>

一个 Windows 桌面启动器：把 **明日方舟（MAA）**、**异环（MaaNTE）**、
**鸣潮（ok-ww）**、**明日方舟终末地（MaaEnd）** 等游戏脚本收进同一个窗口，
并且可以**可视化添加任意新游戏**。

一键启动脚本、启动游戏、打开游戏下载页、实时运行状态、版本检查与更新入口、
官网 / GitHub 直达、Clash Verge 快捷打开，还能自动识别脚本路径，换电脑、换盘符都能用。
从 v0.5.0 起，游戏启动程序支持**自动检测**：扫一遍注册表和常见安装目录，直接挑候选；
从 v0.6.0 起，游戏运行状态改为**复用各脚本自己的判断方法**（窗口类 / 标题正则、进程、可选 ADB），
能区分「运行中（窗口 / 进程 / ADB）」「启动器已开」「云游戏运行中」，启动器不再被误报成游戏运行。

**在线主页（GitHub Pages）**：<https://diaohesi.github.io/ALL-MY-MAA/>
— 截图、功能一览和下载入口都在这一页。

![主界面](docs/screenshot.png)

<p align="center">
  <img src="docs/add-dialog.png" width="640" alt="添加游戏对话框">
</p>

## 下载

- 想先了解再下载？逛一下
  [在线主页（GitHub Pages）](https://diaohesi.github.io/ALL-MY-MAA/)，
  截图、功能和下载入口都在一页里。
- **推荐**：到 [Releases](https://github.com/Diaohesi/ALL-MY-MAA/releases) 下载
  打包好的 `GameHub.exe`，放到 `GameHub/` 文件夹里双击 `启动游戏中心.bat` 即可，
  **不需要安装 Python 和 Pillow**。
- 源码运行 / 自己打包：

  ```bat
  git clone https://github.com/Diaohesi/ALL-MY-MAA.git GameHub
  cd GameHub
  python -m pip install pillow
  ```

- 问题反馈：[Issues](https://github.com/Diaohesi/ALL-MY-MAA/issues)


## 功能

| 功能 | 说明 |
| --- | --- |
| 一键启动脚本 | 点卡片或「启动脚本」拉起脚本；已在运行则把它的窗口切到最前 |
| 启动游戏 | 每张卡片有「启动游戏」按钮；未配置启动程序时自动检测候选，之后记住路径与进程名 |
| 游戏启动程序自动检测 | 编辑卡片时点「自动检测」，扫描注册表卸载项与常见安装目录，按匹配度列出候选（名称 + 路径 + 来源） |
| 下载游戏 | 卡片底部「下载」直接打开对应游戏的官方下载页；可在编辑里改成任意链接 |
| 游戏运行检测 | 复用各脚本自身的判断方法：窗口类 / 标题正则 + 进程（路径收窄）+ 可选 ADB；区分「运行中（窗口 / 进程 / ADB）」「启动器已开」「云游戏运行中」「未运行 / 未配置」，每 1.5 秒刷新 |
| 自定义检测规则 | 编辑卡片可填窗口类正则、窗口标题正则、进程名、ADB 包名；留空则使用脚本自动规则 |
| 版本检查 | 后台检查最新版本，有新版本时显示 `MAA · v6.19.0 → v6.20.0` 并高亮「更新」 |
| 更新 | 点「更新」打开对应脚本，让它走自己的更新流程（脚本自更新最安全） |
| 可视化添加游戏 | 顶部「添加游戏」填写名称、脚本路径、游戏路径、官网/下载链接、主题色即可 |
| 编辑 / 删除 | 右键卡片或点「更多」→ 编辑 / 删除（内置卡片不可删除，可修改） |
| 官网 / GitHub | 每张卡片底部一键打开对应项目主页与仓库 |
| 翻页 | 超过 4 个游戏时自动分页，两侧箭头翻页 |
| 路径自动识别 | 配置优先 → 自动扫描脚本目录 → 预期位置；「重新识别路径」可一键重扫 |
| 可移植 | 路径保存为相对路径，整个文件夹换电脑 / 换盘符后仍可用 |
| Clash Verge | 右上角按钮一键打开 / 切到 Clash Verge，方便访问 GitHub |
| 深色界面 | Win11 深色标题栏，运行时用 Pillow 动态绘制，卡片数量随数据变化 |

## 快速开始

1. 安装 [Python 3.10+](https://www.python.org/downloads/windows/)（勾选
   **Add python.exe to PATH**）。
2. 安装依赖（只需一次）：

   ```bat
   python -m pip install pillow
   ```

3. 把本仓库解压到脚本软件所在目录旁边，例如：

```
D:\All MAA\
├─ GameHub\                     ← 本程序（仓库根目录）
├─ MAA-v6.19.0-win-x64\         ← 明日方舟 MAA
├─ MaaNTE\                      ← 异环 MaaNTE
├─ WuwaMAA\ok-ww\               ← 鸣潮 ok-ww
└─ MaaEnd-win-x86_64-v2.33.0\   ← 明日方舟终末地 MaaEnd
```

4. 双击 `启动游戏中心.bat`；想放到桌面就双击 `创建桌面快捷方式.bat`。

> 脚本目录名不需要固定：Hub 会在自己所在目录里按 exe 文件名自动查找
> `MAA.exe` / `MaaNTE.exe` / `ok-ww.exe` / `MaaEnd.exe`，版本号目录名变了也能找到。
> 脚本放别处的话，可以在 `config.json` 里设置 `"root": "D:/其他/脚本目录"`。

### 打包成免 Python 的单文件 exe（可选）

在装有 Python 的机器上双击 `tools\build_exe.bat`，会生成 `dist\GameHub.exe`。
把它复制到 `GameHub\` 文件夹里，之后双击 `启动游戏中心.bat` 会优先运行它，
**目标电脑不需要安装 Python 和 Pillow**。

## 使用说明

### 添加一个新游戏

1. 点顶部 **「添加游戏」**；
2. 填写：
   - **游戏名称** / **脚本名称**（显示在卡片上）
   - **脚本启动程序**（必填，.exe；卡片「启动脚本」用它）
   - **脚本进程名**（可留空，默认取 exe 文件名，用于识别运行状态）
   - **游戏启动程序**（可选；「启动游戏」按钮用，不填首次点击会让你选）
   - **游戏进程名**（可选，用于显示游戏运行状态）
   - **官网 / GitHub / 更新检查地址 / 下载页**（可选，卡片链接与更新检查用）
   - **主题色**（8 种预设）
   - **自定义图标**（可选，png/ico，会自动复制到 `user_icons/`）
3. 保存后会立刻生成卡片并写入 `config.json`。

内置的 4 个游戏也可以右键 →「编辑此卡片」修改名称、路径、下载页等。

### 游戏启动程序自动检测（v0.5.0）

「游戏启动程序」不用再手动翻文件夹：

1. 右键卡片 →「编辑此卡片」，在「游戏启动程序」旁点 **「自动检测」**；
2. Hub 会扫描 **注册表卸载项**（HKLM / HKCU，含 WOW6432Node）和常见安装目录
   （`Program Files`、`Program Files (x86)`、`LOCALAPPDATA\Programs`、
   各盘 `Games` / `Game` / `游戏` 等目录），按匹配度排序，列出带来源标注
   （`注册表` / `常见目录`）的候选；双击候选或选中后点「确定」即可填入；
3. 直接点卡片的「启动游戏」时，如果还没配置启动程序，Hub 也会先自动检测：
   有候选弹出同一个选择框（也可以点「浏览…」手动选），没有候选则打开文件选择框。

检测总预算 1.8 秒，本机实测每款游戏约 0.2–0.4 秒。内置四款游戏自带关键词；
自定义游戏会按你填写的游戏名作为关键词扫描。本机示例（仅供参考）：
明日方舟 → `MuMuNxMain.exe`，异环 → `NTELauncher.exe`，
鸣潮 → `Wuthering Waves.exe`，终末地 → `Endfield.exe`。

### 游戏运行检测（v0.6.0）

v0.5 及更早只按进程名判断游戏是否在运行，内置配置甚至把启动器进程（`NTELauncher.exe` /
`Launcher.exe`）当成了游戏进程，于是「启动器开着」也会显示「运行中」。v0.6.0 改为
**复用每个脚本自己的判断方法**：

- **一次窗口快照**：`EnumWindows` 枚举顶层窗口，记录窗口类、标题、客户区、PID（本机约 8–14ms）；
- **窗口规则**：窗口类正则 + 标题正则（可只填其一），默认过滤 100×100 以下的小窗；
  允许最小化、同名多窗口、标题带尾随空格；
- **进程规则**：进程名 + 路径正则收窄（避免 `Client-Win64-Shipping.exe` 这类通用名误报），
  读不到进程路径时自动降级为「窗口类 + 标题」或进程名判定；
- **可选 ADB**：模拟器 / 云端包名规则，默认关闭（避免每次轮询拉起 adb 进程），
  需要时可在代码里调用 `gamehub.detector.set_adb_enabled(True)` 开启；
- **只做文案、不算运行**：启动器（`launcher`）与云游戏（`cloud`）单独匹配，
  分别显示「启动器已开」「云游戏运行中」，不会让「游戏运行中」误亮。

各内置脚本的规则来源：

| 脚本 | 规则来源 |
| --- | --- |
| MaaNTE（异环） | 直接读 `MaaNTE/interface.json` 的 `controller[].win32`（class_regex / window_regex），脚本更新自动跟随；内置兜底 `UnrealWindow` + `^\s*(异环\|NTE)\s*$` |
| MaaEnd（终末地） | 同样读 `interface.json` 的 `controller[].win32`；兜底 `UnityWndClass` + `Endfield` |
| ok-ww（鸣潮） | 照其 `config.py` 的做法：`UnrealWindow` + `Client-Win64-Shipping.exe` 双重校验（不强制标题） |
| MAA（明日方舟） | PC 客户端 `UnityWndClass` + `^明日方舟\|^Arknights`；模拟器模式为 ADB 包名规则（默认关闭） |

状态文案共 7 种：**运行中（窗口）/ 运行中（进程）/ 运行中（ADB）/ 启动器已开 /
云游戏运行中 / 未运行 / 未配置**。想自己校准？右键卡片 →「编辑此卡片」，
「检测规则（可选）」里可以填**窗口类正则、窗口标题正则、进程名、ADB 包名**，
留空则继续使用脚本自动规则；「自动检测」选中游戏启动程序后也会带出脚本自带的规则建议。
检测实现与逆向依据见 [docs/game-detection-research.md](docs/game-detection-research.md)。

### 更新是怎么做的

Hub 只负责**检查和提醒**，真正的文件更新由脚本自己完成（MAA 启动时检查更新、
ok-ww 启动即自动更新、MaaNTE / MaaEnd 启动后自检更新）。点「更新」时，如果检测到
新版本会打开脚本让它更新；已是最新会直接提示，不会白启动。

### 路径与配置

`config.json`（已 gitignore）示例：

```json
{
  "version": 4,
  "apps": {
    "maa": {
      "script_exe": "MAA-v6.19.0-win-x64/MAA.exe",
      "game_exe": "D:/Games/Arknights/launcher.exe",
      "script_procs": ["MAA.EXE"],
      "game_procs": ["ARKNIGHTS.EXE"],
      "download": "https://ak.hypergryph.com/",
      "accent": "#4fc3ff"
    }
  },
  "custom_apps": [
    {
      "key": "custom_1",
      "game": "我的游戏",
      "script": "MyScript",
      "script_exe": "MyScript/run.exe",
      "game_exe": "",
      "detect": {
        "any_of": [
          { "type": "win", "class_re": "^UnrealWindow$",
            "title_re": "^\\s*我的游戏\\s*$", "min_client_size": [200, 120] },
          { "type": "proc", "names": ["MyGame.exe"] }
        ]
      },
      "detect_custom": true,
      "download": "https://example.com/download",
      "accent": "#ff8f7a"
    }
  ],
  "clash": "C:/Program Files/Clash Verge/clash-verge.exe",

  "root": "可选：脚本所在目录（默认是 Hub 的上一级目录）"
}
```

- 路径优先保存为相对路径，因此整个文件夹搬走后依然有效；
- 手动选择过路径会记住，点「重新识别路径」可重新扫描；
- `detect` 是自定义检测规则（可选），`detect_custom: true` 表示不再使用脚本自动规则；
- 配置 v4 起，内置卡片的 `game_procs` 会迁移为游戏本体进程（旧配置里误填的启动器进程会被纠正）；
- 想恢复默认：删除 `config.json` 后重新打开即可。

## 目录结构

```
GameHub/
├─ hub.pyw                 程序入口
├─ gamehub/                主程序
│  ├─ ui.py                窗口、卡片交互、添加/编辑对话框、候选选择框、检测规则
│  ├─ render.py            Pillow 动态绘制界面
│  ├─ store.py             配置、路径识别、版本、进程、更新检查、游戏自动检测
│  ├─ detector.py          游戏运行检测（窗口 / 进程 / ADB 规则）
│  └─ theme.py             尺寸与配色
├─ assets/                 图标资源（4 个内置脚本图标、窗口图标、占位图标）
├─ tools/                  开发工具（运行时不需要）
│  ├─ make_assets.py       生成程序图标 / 占位图标
│  ├─ extract_icons.py     从本地脚本提取图标
│  ├─ build_exe.bat        PyInstaller 打包
│  ├─ create_shortcut.ps1  创建桌面快捷方式（由根目录 bat 调用）
│  ├─ grab_hub.py          后台截取窗口（调试 / 文档截图）
│  ├─ preview.py           截图小工具（调试）
│  ├─ test_detect.py       游戏启动程序自动检测命令行自测
│  ├─ test_detect_game.py  游戏运行状态检测命令行自测
│  ├─ regression_test.py   回归测试（标准库 unittest，107 个用例）
│  └─ verify_exe.ps1       本地打包 exe 验证
├─ docs/                   文档与 GitHub Pages 站点
│  ├─ index.html           项目主页
│  ├─ site.css             主页样式
│  ├─ assets/              主页用图片（截图 / logo）
│  ├─ screenshot.png       界面截图
│  ├─ add-dialog.png       添加游戏对话框截图
│  ├─ qa-report.md         回归测试报告
│  └─ game-detection-research.md  游戏检测机制调研报告
├─ .github/                GitHub 维护配置
│  ├─ workflows/build-exe.yml   自动打包 GameHub.exe / 发布 Release
│  ├─ workflows/pages.yml       自动部署 docs/ 到 GitHub Pages
│  └─ ISSUE_TEMPLATE/bug_report.yml
├─ 启动游戏中心.bat
├─ 创建桌面快捷方式.bat
└─ README.md / CHANGELOG.md / LICENSE / .gitignore / requirements.txt
```

## 二次开发

- 界面是数据驱动的：`gamehub/store.py` 里 `DEFAULT_APPS` 定义内置卡片，
  `gamehub/theme.py` 定义尺寸与配色，`gamehub/render.py` 负责绘制。
- 游戏运行检测规则在 `gamehub/detector.py`（`BUILTIN_RULES` / `read_game_rules`）：
  MaaNTE / MaaEnd 优先读各自 `interface.json`，其余用内置规则；改完可运行
  `python tools/test_detect_game.py` 查看每张卡片当前生效的规则与真实检测结果。
- 换图标：替换 `assets/*.png`（256×256 透明背景），或直接在内置卡片里用「编辑」指定图标。
- 改完代码后重新截图：运行 Hub 后执行 `python tools/grab_hub.py docs/screenshot.png`。

## 常见问题

**Q: 提示缺少 Pillow？**
运行 `python -m pip install pillow`；或使用打包好的 `GameHub.exe`。

**Q: 提示“路径缺失”？**
点卡片按提示选择脚本的 exe，或点右上角「重新识别路径」。选择一次后会写入 `config.json`。

**Q: 游戏自动检测找不到启动程序？**
自动检测只认注册表卸载项与常见安装目录，绿色版 / 便携版 / 自定义安装位置可能扫不到。
先在候选框里点「浏览…」手动选择；或确认游戏已正常安装后，再在「编辑此卡片」里点一次
「自动检测」重试。也可以直接把游戏启动程序的完整路径填进「游戏启动程序」。

**Q: 游戏已经启动，卡片却显示「未运行」？**
1. 先确认不是只有启动器 / 云游戏在跑——它们只显示「启动器已开」「云游戏运行中」，不算游戏运行；
2. 右键卡片 →「编辑此卡片」，在「检测规则（可选）」里补窗口类、窗口标题（正则）、进程名或 ADB 包名；
3. 游戏以管理员权限运行、Hub 是普通权限时，可能读不到进程路径，可尝试以管理员身份运行 Hub；
4. 云游戏客户端的窗口标题通常不是游戏本身，需要自定义窗口标题正则；
5. 终端运行 `python tools/test_detect_game.py` 可查看每张卡片的规则来源与检测结果，便于排查。

**Q: 更新检查显示“无法检查”？**
GitHub / 官方 API 需要网络访问；点右上角打开 Clash Verge 后按 `F5` 重试。
MaaNTE 官方 GitHub 仓库在部分网络下不可访问，此时 Hub 会改为直接打开
MaaNTE 让它自行检查更新。

**Q: 启动游戏选择错了？**
右键卡片 →「编辑此卡片」，重新填写「游戏启动程序」，或删除 `config.json`
里对应字段后重新点击按钮选择。

**Q: 提示需要管理员权限？**
`ok-ww` 自身要求管理员权限，Hub 会自动以管理员方式拉起（可能弹 UAC，点「是」）。

**Q: 访问 / 推送 GitHub 很慢或失败？**
先打开 Clash Verge，再给 git 设置一次本地代理即可：

```bat
git config --local http.proxy http://127.0.0.1:7897
git config --local https.proxy http://127.0.0.1:7897
```

（端口按 Clash Verge 实际设置调整；取消代理用 `--unset`。）

## 参与开发

- 欢迎提交 [Issue](https://github.com/Diaohesi/ALL-MY-MAA/issues) 反馈问题或建议；
- 改动后先跑回归测试（标准库 `unittest`，不需要 pytest，全绿时退出码为 0）：

  ```bat
  python tools/regression_test.py   :: 107 个用例
  python tools/test_detect.py       :: 只验证游戏启动程序自动检测，不打开 GUI
  python tools/test_detect_game.py  :: 只读查看游戏运行状态检测（窗口 / 进程 / ADB）
  ```

  详细结果、已知缺陷与未覆盖点见 [docs/qa-report.md](docs/qa-report.md)；
- Pull Request 前请先跑一遍 Hub，确认添加/编辑卡片、启动脚本、启动游戏等功能正常；
- 提交信息建议使用 `feat:`、`fix:`、`docs:` 等前缀。

## 发布新版本（维护者）

1. 修改 `gamehub/__init__.py` 中的 `VERSION`，并更新 `CHANGELOG.md`；
2. 提交并推送：`git add -A && git commit -m "release: vX.Y.Z" && git push`；
3. 打标签并推送：`git tag -a vX.Y.Z -m "GameHub Lite vX.Y.Z" && git push origin vX.Y.Z`；
4. GitHub Actions 会自动构建 `GameHub.exe` 并创建 / 更新对应的 Release
   （见 [.github/workflows/build-exe.yml](.github/workflows/build-exe.yml)）；
5. 改动了 `docs/` 里的主页内容时，推送后会自动部署到
   [GitHub Pages](https://diaohesi.github.io/ALL-MY-MAA/)
   （见 [.github/workflows/pages.yml](.github/workflows/pages.yml)；
   仓库 Settings → Pages 的 Source 需为「GitHub Actions」）。

发布页：<https://github.com/Diaohesi/ALL-MY-MAA/releases>

## 致谢与声明

本仓库代码使用 MIT License。各脚本软件（MAA / MaaNTE / ok-ww / MaaEnd）
及其图标版权归各自作者所有；本仓库不包含它们的程序文件。
`assets/` 中的图标是从本机已安装的脚本中提取 / 官方 logo，仅作为启动器展示素材，
公开分发前建议替换为自己的图标。
