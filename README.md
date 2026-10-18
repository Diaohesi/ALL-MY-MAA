# 游戏脚本中心 · GameHub Lite v0.4.0

<p align="center">
  <a href="https://github.com/Diaohesi/ALL-MY-MAA/releases/latest"><img alt="release" src="https://img.shields.io/github/v/release/Diaohesi/ALL-MY-MAA?label=release&color=4fc3ff"></a>
  <a href="https://github.com/Diaohesi/ALL-MY-MAA/stargazers"><img alt="stars" src="https://img.shields.io/github/stars/Diaohesi/ALL-MY-MAA?color=b98bff"></a>
  <img alt="license" src="https://img.shields.io/badge/license-MIT-green">
  <img alt="platform" src="https://img.shields.io/badge/platform-Windows-0078D7">
  <img alt="python" src="https://img.shields.io/badge/python-3.10%2B-3776AB">
</p>

一个 Windows 桌面启动器：把 **明日方舟（MAA）**、**异环（MaaNTE）**、
**鸣潮（ok-ww）**、**明日方舟终末地（MaaEnd）** 等游戏脚本收进同一个窗口，
并且可以**可视化添加任意新游戏**。

一键启动脚本、启动游戏、打开游戏下载页、实时运行状态、版本检查与更新入口、
官网 / GitHub 直达、Clash Verge 快捷打开，还能自动识别脚本路径，换电脑、换盘符都能用。

![主界面](docs/screenshot.png)

<p align="center">
  <img src="docs/add-dialog.png" width="640" alt="添加游戏对话框">
</p>

## 下载

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
| 启动游戏 | 每张卡片有「启动游戏」按钮；首次点击时选择游戏的启动程序，之后记住 |
| 下载游戏 | 卡片底部「下载」直接打开对应游戏的官方下载页；可在编辑里改成任意链接 |
| 运行状态 | 同时显示「脚本 / 游戏」两个运行状态；每 1.5 秒检测一次，自动刷新 |
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

### 更新是怎么做的

Hub 只负责**检查和提醒**，真正的文件更新由脚本自己完成（MAA 启动时检查更新、
ok-ww 启动即自动更新、MaaNTE / MaaEnd 启动后自检更新）。点「更新」时，如果检测到
新版本会打开脚本让它更新；已是最新会直接提示，不会白启动。

### 路径与配置

`config.json`（已 gitignore）示例：

```json
{
  "version": 3,
  "apps": {
    "maa": {
      "script_exe": "MAA-v6.19.0-win-x64/MAA.exe",
      "game_exe": "D:/Games/Arknights/launcher.exe",
      "script_procs": ["MAA.EXE"],
      "game_procs": ["LAUNCHER.EXE"],
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
- 想恢复默认：删除 `config.json` 后重新打开即可。

## 目录结构

```
GameHub/
├─ hub.pyw                 程序入口
├─ gamehub/                主程序
│  ├─ ui.py                窗口、卡片交互、添加/编辑对话框
│  ├─ render.py            Pillow 动态绘制界面
│  ├─ store.py             配置、路径识别、版本、进程、更新检查
│  └─ theme.py             尺寸与配色
├─ assets/                 图标资源（4 个内置脚本图标、窗口图标、占位图标）
├─ tools/                  开发工具（运行时不需要）
│  ├─ make_assets.py       生成程序图标 / 占位图标
│  ├─ extract_icons.py     从本地脚本提取图标
│  ├─ build_exe.bat        PyInstaller 打包
│  ├─ create_shortcut.ps1  创建桌面快捷方式（由根目录 bat 调用）
│  ├─ grab_hub.py          后台截取窗口（调试 / 文档截图）
│  └─ preview.py           截图小工具（调试）
├─ .github/                GitHub 维护配置
│  ├─ workflows/build-exe.yml   自动打包 GameHub.exe / 发布 Release
│  └─ ISSUE_TEMPLATE/bug_report.yml
├─ docs/screenshot.png     界面截图
├─ docs/add-dialog.png     添加游戏对话框截图
├─ 启动游戏中心.bat
├─ 创建桌面快捷方式.bat
└─ README.md / CHANGELOG.md / LICENSE / .gitignore / requirements.txt
```

## 二次开发

- 界面是数据驱动的：`gamehub/store.py` 里 `DEFAULT_APPS` 定义内置卡片，
  `gamehub/theme.py` 定义尺寸与配色，`gamehub/render.py` 负责绘制。
- 换图标：替换 `assets/*.png`（256×256 透明背景），或直接在内置卡片里用「编辑」指定图标。
- 改完代码后重新截图：运行 Hub 后执行 `python tools/grab_hub.py docs/screenshot.png`。

## 常见问题

**Q: 提示缺少 Pillow？**
运行 `python -m pip install pillow`；或使用打包好的 `GameHub.exe`。

**Q: 提示“路径缺失”？**
点卡片按提示选择脚本的 exe，或点右上角「重新识别路径」。选择一次后会写入 `config.json`。

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
- Pull Request 前请先跑一遍 Hub，确认添加/编辑卡片、启动脚本、启动游戏等功能正常；
- 提交信息建议使用 `feat:`、`fix:`、`docs:` 等前缀。

## 致谢与声明

本仓库代码使用 MIT License。各脚本软件（MAA / MaaNTE / ok-ww / MaaEnd）
及其图标版权归各自作者所有；本仓库不包含它们的程序文件。
`assets/` 中的图标是从本机已安装的脚本中提取 / 官方 logo，仅作为启动器展示素材，
公开分发前建议替换为自己的图标。
